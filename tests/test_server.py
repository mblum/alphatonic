import json
import re
import threading
import urllib.error
import urllib.request

import pytest

from alphatonic import Evaluation, Study
from alphatonic.server import _KEPT, make_server, respond
from alphatonic.study import RECORD, TEARSHEET
from conftest import regular_panel
from test_study import QUICK, record, saved


@pytest.fixture
def study(tmp_path):
    study = Study(tmp_path / "study", name="demo")
    saved(
        study,
        record("old-momentum", hours=1, cs_ic=0.02, p=0.01, context={"Returns": "price only"}),
        record("new-momentum", hours=3, cs_ic=None, p=None),
        record("bollinger-run", signal="bollinger", hours=2, cs_ic=0.05, p=0.3),
        record("holdout-run", hours=4, cs_ic=0.01, p=0.5, sample="holdout"),
    )
    for identifier in ("old-momentum", "new-momentum", "bollinger-run", "holdout-run"):
        page = f"<html>{identifier}</html>"
        (study.directory / identifier / TEARSHEET).write_text(page, encoding="utf-8")
    return study


@pytest.fixture(scope="module")
def evaluated(tmp_path_factory):
    """A study with two evaluated trials of one family, neither with a stored tearsheet."""
    factor, prices = regular_panel(n_assets=6, n_bars=240, seed=5)
    study = Study(tmp_path_factory.mktemp("evaluated") / "study", name="demo")
    first = study.evaluate(factor, prices, signal="momentum", **QUICK)
    second = study.evaluate(factor * 2, prices, signal="momentum", **QUICK)
    return study, first, second


def _page(study, target="/"):
    response = respond(study, target)
    assert response.status == 200
    assert response.content_type.startswith("text/html")
    return response.body.decode("utf-8")


def _ids(page):
    return re.findall(r'href="([^/"?]+)/record.json"', page)


def test_the_list_shows_every_trial_newest_first(study):
    page = _page(study)

    assert _ids(page) == ["holdout-run", "new-momentum", "bollinger-run", "old-momentum"]
    assert "4 trials saved" in page
    assert "<title>Trials · demo</title>" in page


def test_sorting_by_a_statistic_puts_undefined_values_last(study):
    descending = _page(study, "/?sort=cs_ic&order=desc")
    ascending = _page(study, "/?sort=cs_ic&order=asc")

    assert _ids(descending) == ["bollinger-run", "old-momentum", "holdout-run", "new-momentum"]
    assert _ids(ascending) == ["holdout-run", "old-momentum", "bollinger-run", "new-momentum"]


def test_an_unknown_sort_falls_back_to_the_newest_first(study):
    assert _ids(_page(study, "/?sort=sharpe&order=sideways"))[0] == "holdout-run"


def test_a_heading_links_to_the_opposite_order_of_the_current_sort(study):
    assert "sort=cs_ic&amp;order=asc" in _page(study, "/?sort=cs_ic&order=desc")


def test_the_list_counts_trials_and_scales_p_values(study):
    page = _page(study, "/?signal=momentum")

    assert _ids(page) == ["holdout-run", "new-momentum", "old-momentum"]
    # Three momentum trials: 0.01 × 3.
    assert ">0.030<" in page


def test_context_keys_are_columns(study):
    page = _page(study)

    assert ">Returns" in page and "price only" in page


def test_the_horizon_choice_changes_the_statistics_shown(study):
    assert "horizon of 4 bars" in _page(study, "/?horizon=4")
    assert "horizon of 1 bar." in _page(study, "/?horizon=7")


def test_a_trial_without_a_tearsheet_links_only_its_record(study):
    (study.directory / "old-momentum" / TEARSHEET).unlink()

    page = _page(study)

    assert 'href="old-momentum/tearsheet.html"' not in page
    assert 'href="old-momentum/record.json"' in page


def test_a_tearsheet_and_a_record_are_served_from_their_trial(study):
    tearsheet = respond(study, "/bollinger-run/tearsheet.html")
    stored = respond(study, "/bollinger-run/record.json")

    assert tearsheet.body == b"<html>bollinger-run</html>"
    assert stored.content_type == "application/json"
    assert json.loads(stored.body)["signal"] == "bollinger"


def test_a_tearsheet_that_was_not_stored_is_drawn_from_the_tables(evaluated):
    study, first, second = evaluated
    assert not (study.directory / second.id / TEARSHEET).exists()

    response = respond(study, f"/{second.id}/tearsheet.html?render")

    assert response.status == 200 and response.content_type.startswith("text/html")
    page = response.body.decode("utf-8")
    assert "<dt>Study</dt><dd>demo</dd>" in page
    assert "2 of momentum, this one included" in page
    assert "1 of momentum, this one included" in _page(study, f"/{first.id}/tearsheet.html?render")


def test_a_drawn_tearsheet_is_kept_for_the_next_request(evaluated, monkeypatch):
    study, _, second = evaluated
    _KEPT.clear()
    drawn = []
    original = Evaluation.render_tearsheet
    monkeypatch.setattr(
        Evaluation, "render_tearsheet", lambda *a, **k: drawn.append(1) or original(*a, **k)
    )

    first = respond(study, f"/{second.id}/tearsheet.html?render")
    again = respond(study, f"/{second.id}/tearsheet.html")

    assert len(drawn) == 1
    assert first.body == again.body


def test_the_list_links_a_tearsheet_that_can_be_drawn(evaluated):
    study, first, second = evaluated

    page = _page(study)

    for trial in (first, second):
        assert f'href="{trial.id}/tearsheet.html"' in page


def test_a_stored_tearsheet_is_served_instead_of_a_drawn_one(evaluated):
    study, first, _ = evaluated
    stored = study.directory / first.id / TEARSHEET
    stored.write_text("<html>stored</html>", encoding="utf-8")
    try:
        assert respond(study, f"/{first.id}/tearsheet.html").body == b"<html>stored</html>"
    finally:
        stored.unlink()


def test_a_trial_with_neither_a_stored_tearsheet_nor_tables_has_none(study):
    (study.directory / "old-momentum" / TEARSHEET).unlink()

    response = respond(study, "/old-momentum/tearsheet.html")

    assert response.status == 404
    assert b"no saved tables" in response.body


@pytest.mark.parametrize(
    "target",
    [
        "/missing/tearsheet.html",
        "/../study/old-momentum/record.json",
        "/..%2Fold-momentum/record.json",
        "/.hidden/record.json",
        "/old-momentum/tables/ic_summary.csv",
        "/old-momentum",
        "/favicon.ico",
    ],
)
def test_anything_but_a_finished_trials_files_is_not_found(study, target):
    assert respond(study, target).status == 404


def test_a_trial_without_a_record_is_not_served(study):
    (study.directory / "holdout-run" / RECORD).unlink()

    assert respond(study, "/holdout-run/tearsheet.html").status == 404


def test_an_empty_study_says_where_trials_come_from(tmp_path):
    page = _page(Study(tmp_path / "empty"))

    assert "No trials yet" in page and "Study.evaluate" in page


def test_the_server_answers_over_http(study):
    server = make_server(study, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_address[1]}"
    try:
        with urllib.request.urlopen(f"{base}/?sort=trials") as response:
            assert response.status == 200
            assert "holdout-run" in response.read().decode("utf-8")
        head = urllib.request.Request(f"{base}/bollinger-run/record.json", method="HEAD")
        with urllib.request.urlopen(head) as response:
            assert response.headers["Content-Type"] == "application/json"
            assert response.read() == b""
        with pytest.raises(urllib.error.HTTPError, match="404") as missing:
            urllib.request.urlopen(f"{base}/nope")
        missing.value.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_a_trial_finished_while_the_page_renders_waits_for_a_reload(study, monkeypatch):
    trials, unreadable = study._scan()
    scans = iter([(trials[1:], unreadable)])
    original = Study._scan
    monkeypatch.setattr(study, "_scan", lambda: next(scans, None) or original(study))

    first, second = _page(study), _page(study)

    assert _ids(first) == ["new-momentum", "bollinger-run", "old-momentum"]
    assert "3 trials saved" in first
    assert _ids(second)[0] == "holdout-run"


def test_the_list_is_served_as_json_with_the_pages_parameters(study):
    response = respond(study, "/study.json?sort=cs_ic&order=asc&horizon=4")

    assert response.status == 200 and response.content_type == "application/json"
    document = json.loads(response.body)
    assert document == json.loads(json.dumps(study.to_dict(4, sort="cs_ic", descending=False)))
    assert "study.json" in _page(study)


def test_an_unknown_sort_in_the_json_is_a_bad_request(study):
    response = respond(study, "/study.json?sort=sharpe")

    assert response.status == 400
    assert b"sort by one of" in response.body


def test_the_signal_filter_keeps_every_signal_selectable(study):
    page = _page(study, "/?signal=bollinger")

    assert _ids(page) == ["bollinger-run"]
    assert '<option value="bollinger" selected>' in page
    assert '<option value="momentum">' in page
    assert "No trials of sharpe" in _page(study, "/?signal=sharpe")


def test_a_repeated_look_at_the_holdout_is_flagged(study):
    saved(study, record("second-look", hours=5, sample="holdout"))

    page = _page(study)

    assert "holdout · 2 looks" in page
    assert "2 holdout evaluations" in page


def test_only_adjusted_p_values_of_five_percent_or_less_are_bold(study):
    page = _page(study, "/?signal=momentum")

    # 0.01 × 3 trials is bold; 0.5 × 3, capped at 1, is not.
    assert "<strong>0.030</strong>" in page
    assert "<strong>1.000</strong>" not in page and ">1.000<" in page


def test_an_error_while_answering_is_a_500(study, monkeypatch):
    def broken(study, target):
        raise RuntimeError("record unreadable")

    monkeypatch.setattr("alphatonic.server.respond", broken)
    server = make_server(study, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError, match="500") as failed:
            urllib.request.urlopen(f"http://127.0.0.1:{server.server_address[1]}/")
        assert failed.value.read() == b"RuntimeError: record unreadable\n"
        failed.value.close()
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_statistics_keep_their_decimals_however_small(study):
    saved(study, record("tiny", hours=6, cs_ic=0.00004, p=0.0000002))

    page = _page(study)

    assert ">0.0000<" in page and "e-0" not in page
    assert "&lt; 0.001" in page


def test_a_download_request_names_the_file_after_its_trial(study):
    shown = respond(study, "/bollinger-run/tearsheet.html")
    saved = respond(study, "/bollinger-run/tearsheet.html?download")
    record = respond(study, "/bollinger-run/record.json?download")

    assert shown.filename is None
    assert saved.filename == "bollinger-run-tearsheet.html" and saved.body == shown.body
    assert record.filename == "bollinger-run-record.json"


def test_a_drawn_tearsheet_can_be_downloaded(evaluated):
    study, _, second = evaluated

    response = respond(study, f"/{second.id}/tearsheet.html?download")

    assert response.filename == f"{second.id}-tearsheet.html"
    assert b"<dt>Study</dt>" in response.body


def test_the_server_sends_a_download_as_an_attachment(study):
    import threading
    from urllib.request import urlopen

    server = make_server(study, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        url = f"http://127.0.0.1:{server.server_port}/bollinger-run/tearsheet.html"
        with urlopen(url + "?download") as saved, urlopen(url) as shown:
            disposition = saved.headers["Content-Disposition"]
            plain = shown.headers["Content-Disposition"]
    finally:
        server.shutdown()
        server.server_close()
        thread.join()

    assert disposition == 'attachment; filename="bollinger-run-tearsheet.html"'
    assert plain is None


def test_a_tearsheet_that_has_to_be_drawn_is_answered_at_once_with_a_page_that_waits(
    evaluated, monkeypatch
):
    study, _, second = evaluated
    _KEPT.clear()
    monkeypatch.setattr(
        Evaluation, "render_tearsheet", lambda *a, **k: pytest.fail("drew the tearsheet")
    )

    response = respond(study, f"/{second.id}/tearsheet.html")

    assert response.status == 200 and response.filename is None
    page = response.body.decode("utf-8")
    assert "<h1>momentum</h1>" in page and "<title>momentum · demo</title>" in page
    assert 'aria-busy="true"' in page and "Drawing the tearsheet" in page
    assert "fetch('?render')" in page
    assert 'href="../"' in page


def test_the_page_that_waits_is_not_sent_for_a_tearsheet_that_is_kept(evaluated):
    study, _, second = evaluated
    _KEPT.clear()
    respond(study, f"/{second.id}/tearsheet.html?render")

    page = _page(study, f"/{second.id}/tearsheet.html")

    assert "<dt>Study</dt><dd>demo</dd>" in page and "fetch('?render')" not in page


def test_a_trial_without_tables_gets_no_page_that_waits(study):
    (study.directory / "old-momentum" / TEARSHEET).unlink()

    assert respond(study, "/old-momentum/tearsheet.html").status == 404


def test_the_server_keeps_only_the_last_few_drawn_tearsheets(evaluated, monkeypatch):
    study, first, second = evaluated
    _KEPT.clear()
    monkeypatch.setattr("alphatonic.server._KEPT_PAGES", 1)

    respond(study, f"/{first.id}/tearsheet.html?render")
    respond(study, f"/{second.id}/tearsheet.html?render")

    assert [identifier for _, identifier in _KEPT] == [second.id]


def test_the_list_does_not_announce_a_tearsheet_being_drawn(study):
    assert "Drawing the tearsheet" not in _page(study)
