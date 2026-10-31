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


def _rows(page):
    """The HTML of each trial's row, by identifier."""
    rows = {}
    for chunk in page.split("<tr>")[1:]:
        found = re.search(r'href="([^/"?]+)/record.json"', chunk)
        if found:
            rows[found.group(1)] = chunk
    return rows


def _ranks(page):
    return {
        identifier: re.search(r'class="rank"[^>]*>([^<]*)<', row).group(1)
        for identifier, row in _rows(page).items()
        if 'class="rank"' in row
    }


def _tiles(page):
    """The label of each summary tile with its figure and its text, without markup."""
    found = re.findall(
        r'<dt>([^<]+)</dt>\s*<dd class="figure">([^<]+)</dd>\s*<dd class="context">(.*?)</dd>',
        page,
        re.S,
    )
    return {
        label: (figure, " ".join(re.sub(r"<[^>]+>", "", text).split()))
        for label, figure, text in found
    }


def _interval(identifier, ic, lower, upper, **fields):
    """A trial with a rank IC and its 95% interval at horizon 1."""
    metrics = {
        "cs.h1.spearman.mean": ic,
        "cs.h1.spearman.hac_p_value": 0.2,
        "cs.h1.spearman.ci95_lower": lower,
        "cs.h1.spearman.ci95_upper": upper,
    }
    return record(identifier, metrics=metrics, **fields)


def test_the_tiles_name_the_best_evidence_and_the_best_rank_ic_with_its_cost(study):
    tiles = _tiles(_page(study))

    # old-momentum: p 0.01 across the three trials of its family.
    assert tiles["Lowest p × trials"] == ("0.030", "momentum · p 0.010 · 3 trials in its family")
    # The highest rank IC comes with the adjusted p-value that it has to be read against.
    assert tiles["Highest rank IC"] == ("0.0500", "bollinger · p × trials 0.300")
    assert tiles["Largest family"] == ("3 trials", "family momentum")
    assert tiles["Holdout looks"] == ("1", "no holdout set")


def test_the_tiles_link_a_trial_with_a_tearsheet_and_flag_a_reused_holdout(study):
    saved(study, record("second-look", hours=5, sample="holdout"))
    (study.directory / "second-look" / TEARSHEET).write_text("<html></html>", encoding="utf-8")

    page = _page(study)

    tiles = _tiles(page)
    assert tiles["Holdout looks"][0] == "2"
    assert "1 family looked more than once" in tiles["Holdout looks"][1]
    assert "re-used" in tiles["Holdout looks"][1]
    assert re.search(r'<dd class="context">\s*<a href="old-momentum/tearsheet.html">', page)


def test_a_tile_without_a_value_is_a_dash_that_says_why(tmp_path):
    study = Study(tmp_path / "study")
    saved(study, record("a", cs_ic=None, p=None))

    tiles = _tiles(_page(study))

    assert tiles["Lowest p × trials"] == ("–", "no p-value at this horizon")
    assert tiles["Highest rank IC"] == ("–", "no rank IC at this horizon")


def test_the_tiles_follow_the_signal_filter(study):
    tiles = _tiles(_page(study, "/?signal=bollinger"))

    assert tiles["Lowest p × trials"][1].startswith("bollinger · p 0.300")
    assert tiles["Largest family"] == ("1 trial", "family bollinger")


def test_rows_are_ranked_from_the_best_value_of_the_column_they_are_sorted_by(study):
    descending = _ranks(_page(study, "/?sort=cs_ic&order=desc"))
    ascending = _page(study, "/?sort=cs_ic&order=asc")

    assert descending == {
        "bollinger-run": "#1",
        "old-momentum": "#2",
        "holdout-run": "#3",
        "new-momentum": "–",  # Undefined: no rank, and never the last place.
    }
    assert _ranks(ascending) == descending  # The other order reverses the rows, not the ranks.
    assert _ids(ascending) == ["holdout-run", "old-momentum", "bollinger-run", "new-momentum"]


def test_a_p_value_is_ranked_from_its_smallest_value(study):
    assert _ranks(_page(study, "/?sort=cs_p&order=asc")) == {
        "old-momentum": "#1",
        "bollinger-run": "#2",
        "holdout-run": "#3",
        "new-momentum": "–",
    }


def test_equal_values_share_a_rank_and_the_next_one_skips(tmp_path):
    study = Study(tmp_path / "study")
    saved(
        study,
        record("a", hours=1, cs_ic=0.03),
        record("b", hours=2, cs_ic=0.02),
        record("c", hours=3, cs_ic=0.02),
        record("d", hours=4, cs_ic=0.01),
    )

    assert _ranks(_page(study, "/?sort=cs_ic")) == {"a": "#1", "b": "#2", "c": "#2", "d": "#4"}


@pytest.mark.parametrize("target", ["/", "/?sort=trials", "/?sort=signal", "/?sort=assets"])
def test_a_column_that_is_not_better_or_worse_gives_no_ranks(study, target):
    page = _page(study, target)

    assert 'class="rank"' not in page and "# ranks by" not in page


def test_the_key_says_which_column_the_ranks_follow(study):
    assert "# ranks by Rank IC (cross-sectional): 1 is the largest" in _page(study, "/?sort=cs_ic")
    assert "# ranks by p × trials (multiple testing): 1 is the smallest" in _page(
        study, "/?sort=adjusted_p"
    )


def test_the_rank_ic_is_drawn_with_its_interval_on_an_axis_shared_by_every_row(tmp_path):
    study = Study(tmp_path / "study")
    saved(
        study,
        _interval("up", 0.03, 0.01, 0.05, hours=1),
        _interval("down", -0.02, -0.04, 0.0, hours=2),
    )

    page = _page(study)
    rows = _rows(page)

    # The widest interval reaches 0.05, so the axis runs from -0.05 to 0.05 and zero is at 50%.
    assert "<span>−0.05</span><span>0</span><span>0.05</span>" in page
    assert 'class="whisker" style="left: 60.0%; width: 40.0%"' in rows["up"]
    assert 'class="dot" style="left: 80.0%"' in rows["up"]
    assert 'class="whisker" style="left: 10.0%; width: 40.0%"' in rows["down"]
    assert 'class="dot" style="left: 30.0%"' in rows["down"]
    assert "Rank IC 0.0300, 95% interval 0.0100 to 0.0500" in rows["up"]


def test_choosing_a_signal_moves_no_mark(tmp_path):
    study = Study(tmp_path / "study")
    saved(
        study,
        _interval("wide", 0.03, -0.03, 0.09, hours=1, signal="noisy"),
        _interval("narrow", 0.03, 0.02, 0.04, hours=2, signal="precise"),
    )

    both = _rows(_page(study))["narrow"]
    only = _rows(_page(study, "/?signal=precise"))["narrow"]

    assert "<span>−0.1</span><span>0</span><span>0.1</span>" in _page(study, "/?signal=precise")
    assert re.findall(r'style="([^"]*)"', only) == re.findall(r'style="([^"]*)"', both)


def test_an_estimate_without_an_interval_is_drawn_hollow_and_alone(study):
    # The fixture's records have a rank IC but no interval; one has no rank IC at all.
    page = _page(study)
    rows = _rows(page)

    assert 'class="whisker"' not in page
    assert 'class="dot open"' in rows["old-momentum"]
    assert "the 95% interval is undefined at this horizon" in rows["old-momentum"]
    assert "dot" not in rows["new-momentum"] and 'class="forest empty"' in rows["new-momentum"]


def test_a_study_without_a_rank_ic_has_no_axis(tmp_path):
    study = Study(tmp_path / "study")
    saved(study, record("a", cs_ic=None, p=None))

    page = _page(study)

    assert 'class="axis"' not in page and 'class="swatch dot"' not in page


def test_the_horizon_is_chosen_from_links_that_keep_the_rest_of_the_view(study):
    page = _page(study, "/?sort=cs_ic&order=asc&signal=momentum")

    assert 'href="?sort=cs_ic&amp;order=asc&amp;horizon=4&amp;signal=momentum"' in page
    assert re.search(r'<a href="[^"]*horizon=1[^"]*" aria-current="true">1 bar</a>', page)
    assert 'name="horizon" value="4"' in _page(study, "/?horizon=4")


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
