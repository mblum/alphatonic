import json
import re
from datetime import UTC, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from alphatonic import EvaluationConfig, HoldoutError, Study, Trial, UnknownTrialError
from alphatonic.study import BOARD_COLUMNS, IDENTIFIER, RECORD, TABLES, TEARSHEET, _assets_line
from conftest import regular_panel

QUICK = {"horizons": [1], "min_assets": 3, "time_series": {"bootstrap_samples": 0}}
"""Options that evaluate the small panel in about a second."""

CREATED = datetime(2026, 1, 1, tzinfo=UTC)


@pytest.fixture(scope="module")
def market():
    return regular_panel(n_assets=6, n_bars=240, seed=5)


@pytest.fixture
def boundary(market):
    return market[1].index[180].to_pydatetime()


@pytest.fixture
def study(tmp_path, boundary):
    return Study(tmp_path / "study", holdout_start=boundary, name="demo")


def record(identifier, *, signal="momentum", hours=0, cs_ic=0.01, p=0.2, **fields):
    """A trial record created `hours` after `CREATED`, with headline statistics at horizon 1."""
    metrics = {"ts.h1.spearman.mean": 0.02, "ts.h1.cosine.mean": 0.03}
    if cs_ic is not None:
        metrics["cs.h1.spearman.mean"] = cs_ic
    if p is not None:
        metrics["cs.h1.spearman.hac_p_value"] = p
    values = {
        "id": identifier,
        "created_at": CREATED + timedelta(hours=hours),
        "signal": signal,
        "sample": "in_sample",
        "start": datetime(2025, 1, 1, tzinfo=UTC),
        "end": datetime(2025, 6, 1, tzinfo=UTC),
        "horizons": [1, 4],
        "metrics": metrics,
    }
    values.update(fields)
    return Trial(**values)


def saved(study, *trials):
    """Write each record into its directory, as a finished trial."""
    for trial in trials:
        directory = study.directory / trial.id
        directory.mkdir(parents=True, exist_ok=True)
        (directory / RECORD).write_text(trial.model_dump_json(), encoding="utf-8")


def test_an_in_sample_window_ends_at_the_holdout_by_default(study, boundary):
    assert study.window() == (None, boundary)
    with pytest.raises(HoldoutError, match="pass holdout=True"):
        study.window(end=boundary + timedelta(hours=1))


def test_a_holdout_window_starts_at_the_holdout_and_not_before(study, boundary):
    assert study.window(holdout=True) == (boundary, None)
    with pytest.raises(HoldoutError, match="starts at or after"):
        study.window(start=boundary - timedelta(hours=1), holdout=True)


def test_a_holdout_cannot_be_asked_for_without_one(tmp_path):
    study = Study(tmp_path)
    assert study.window() == (None, None)
    with pytest.raises(HoldoutError, match="no holdout"):
        study.window(holdout=True)


def test_an_empty_window_is_refused(study, boundary):
    with pytest.raises(HoldoutError, match="empty"):
        study.window(start=boundary, end=boundary)


def test_naive_bounds_are_utc(tmp_path):
    study = Study(tmp_path, holdout_start="2026-01-08")
    assert study.holdout_start == datetime(2026, 1, 8, tzinfo=UTC)
    assert study.window(end="2026-01-02")[1] == datetime(2026, 1, 2, tzinfo=UTC)


def test_an_evaluation_saves_its_tables_and_record(study, market, boundary):
    factor, prices = market

    trial = study.evaluate(
        factor,
        prices,
        signal="Momentum 20/5",
        summary="Recent winners keep winning.",
        parameters={"window": 20},
        context={"Returns": "price only"},
        versions={"research": "1.2.3", "commit": None},
        note="first look",
        **QUICK,
    )

    assert IDENTIFIER.match(trial.id) and "-Momentum-20-5-" in trial.id
    directory = study.directory / trial.id
    assert (directory / TABLES / "ic_summary.csv.gz").is_file()
    assert not (directory / TEARSHEET).exists()
    stored = json.loads((directory / RECORD).read_text(encoding="utf-8"))
    assert Trial.model_validate(stored) == trial
    assert (trial.signal, trial.family, trial.sample) == (
        "Momentum 20/5",
        "Momentum 20/5",
        "in_sample",
    )
    assert trial.end == boundary
    assert trial.holdout_start == boundary
    assert trial.assets == list(prices.columns)
    assert trial.bar_seconds == 3600
    assert trial.versions["alphatonic"] and trial.versions["research"] == "1.2.3"
    assert len(trial.data_fingerprint) == 64
    assert "cs.h1.spearman.mean" in trial.metrics
    assert study.trials() == [trial]
    assert study.evaluation(trial.id).metrics() == pytest.approx(trial.metrics)


def test_a_tearsheet_is_stored_only_when_asked_for(study, market):
    factor, prices = market

    stored = study.evaluate(factor, prices, signal="momentum", report=True, **QUICK)
    default = study.evaluate(factor * 2, prices, signal="momentum", **QUICK)

    page = (study.directory / stored.id / TEARSHEET).read_text(encoding="utf-8")
    for text in ("<dt>Study</dt><dd>demo</dd>", "1 of momentum, this one included"):
        assert text in page
    assert not (study.directory / default.id / TEARSHEET).exists()


class _LaterClock:
    """Stands in for `datetime` in the report module, so a redraw happens at a later time."""

    @staticmethod
    def now(tz):
        return datetime(2030, 1, 1, tzinfo=tz)


def _without_the_clock(page):
    """The page without the time it was generated, which is the one thing a redraw changes."""
    return re.sub(r"Generated \S+", "Generated", page)


def test_a_drawn_tearsheet_is_the_page_the_evaluation_would_have_stored(study, market, monkeypatch):
    factor, prices = market
    trial = study.evaluate(
        factor,
        prices,
        signal="Momentum 20/5",
        parameters={"window": 20},
        context={"Returns": "price only"},
        note="first look",
        report=True,
        **QUICK,
    )

    stored = (study.directory / trial.id / TEARSHEET).read_text(encoding="utf-8")
    monkeypatch.setattr("alphatonic.report.datetime", _LaterClock)
    drawn = study.render_tearsheet(trial.id)

    assert "Generated 2030-01-01T00:00:00+00:00" in drawn
    assert _without_the_clock(drawn) == _without_the_clock(stored)
    for text in ("<dt>Study</dt><dd>demo</dd>", "price only", "window=20", "first look"):
        assert text in drawn


def test_the_trial_count_in_a_drawn_tearsheet_is_the_trials_place_in_its_family(study, market):
    factor, prices = market

    first = study.evaluate(factor, prices, signal="momentum", **QUICK)
    other = study.evaluate(factor, prices, signal="bollinger", **QUICK)
    second = study.evaluate(factor * 2, prices, signal="momentum", **QUICK)

    assert "1 of momentum, this one included" in study.render_tearsheet(first.id)
    assert "1 of bollinger, this one included" in study.render_tearsheet(other.id)
    assert "2 of momentum, this one included" in study.render_tearsheet(second.id)


def test_a_tearsheet_needs_a_finished_trial_with_tables(study):
    saved(study, record("tableless"))

    with pytest.raises(FileNotFoundError, match="no saved tables"):
        study.render_tearsheet("tableless")
    for identifier in ("missing", "../study"):
        with pytest.raises(UnknownTrialError):
            study.render_tearsheet(identifier)


def test_the_tearsheet_names_at_most_twenty_assets():
    assets = [f"A{i:02d}" for i in range(25)]

    assert _assets_line(assets[:2]) == "2: A00, A01"
    assert _assets_line(assets).endswith("A18, A19, and 5 more")
    assert _assets_line(assets).startswith("25: A00, ")


def test_a_window_ends_where_the_prices_do(tmp_path, market):
    factor, prices = market
    study = Study(tmp_path, holdout_start=prices.index[-1] + pd.Timedelta(days=30))

    trial = study.evaluate(factor, prices, signal="momentum", report=False, **QUICK)

    assert trial.end == prices.index[-1] + pd.Timedelta(hours=1)


def test_a_holdout_evaluation_starts_at_the_boundary_and_is_counted(study, market, boundary):
    factor, prices = market

    trial = study.evaluate(factor, prices, signal="momentum", holdout=True, report=False, **QUICK)

    assert trial.sample == "holdout"
    assert trial.start == boundary
    assert study.board()["holdout_uses"].tolist() == [1]


def test_a_refused_window_saves_nothing(study, market, boundary):
    factor, prices = market

    with pytest.raises(HoldoutError):
        study.evaluate(factor, prices, signal="momentum", end=boundary + timedelta(days=1), **QUICK)
    with pytest.raises(ValueError, match="prices end"):
        Study(study.directory, holdout_start=prices.index[-1] + pd.Timedelta(days=2)).evaluate(
            factor, prices, signal="momentum", holdout=True, **QUICK
        )

    assert not study.directory.exists()


def test_options_come_as_a_config_or_as_keywords(study, market):
    factor, prices = market

    with pytest.raises(TypeError, match="not both"):
        study.evaluate(factor, prices, EvaluationConfig(), signal="momentum", horizons=[1])


def test_context_keys_may_not_shadow_board_columns(study, market):
    factor, prices = market

    with pytest.raises(ValueError, match=r"\['cs_ic', 'note'\]"):
        study.evaluate(factor, prices, signal="x", context={"note": "a", "cs_ic": "b"}, **QUICK)


def test_trials_are_listed_newest_first_and_broken_records_reported(study):
    saved(study, record("a", hours=1), record("b", hours=3), record("c", hours=2))
    (study.directory / "unfinished").mkdir()
    (study.directory / "broken").mkdir()
    (study.directory / "broken" / RECORD).write_text("{", encoding="utf-8")

    assert [trial.id for trial in study.trials()] == ["b", "c", "a"]
    assert study.unreadable() == [study.directory / "broken" / RECORD]


def test_a_study_without_a_directory_has_no_trials(tmp_path):
    study = Study(tmp_path / "absent")

    assert study.trials() == [] and study.unreadable() == []
    assert study.board().empty
    assert list(study.board().columns) == list(BOARD_COLUMNS)


@pytest.mark.parametrize("identifier", ["../a", "..", ".hidden", "nope", "a/../a"])
def test_identifiers_cannot_leave_the_study(study, identifier):
    saved(study, record("a"))

    assert study.trial("a").id == "a"
    with pytest.raises(UnknownTrialError, match="no finished trial"):
        study.trial(identifier)


def test_the_board_counts_trials_per_family_and_scales_p_values(study):
    saved(
        study,
        record("a", p=0.02),
        record("b", p=0.4),
        record("c", p=0.3, sample="holdout"),
        record("d", signal="bollinger", p=0.02),
    )

    board = study.board()

    assert board.loc["a", "trials"] == 3
    assert board.loc["a", "adjusted_p"] == pytest.approx(0.06)
    assert board.loc["b", "adjusted_p"] == 1.0
    assert board.loc["a", "holdout_uses"] == 1
    assert board.loc["d", "trials"] == 1
    assert board.loc["d", "adjusted_p"] == pytest.approx(0.02)


def test_a_family_pools_signals_that_test_one_idea(study):
    saved(
        study,
        record("a", signal="momentum_20", family="momentum", p=0.01),
        record("b", signal="momentum_60", family="momentum", p=0.5),
    )

    board = study.board()

    assert board["trials"].tolist() == [2, 2]
    assert board.loc["a", "adjusted_p"] == pytest.approx(0.02)


def test_a_statistic_missing_at_the_horizon_is_nan(study):
    saved(study, record("a", hours=1), record("b", cs_ic=None, p=None))

    assert study.board().loc["a", "horizon"] == 1
    four = study.board(horizon=4)
    assert np.isnan(four.loc["a", "cs_ic"]) and np.isnan(four.loc["a", "adjusted_p"])
    assert np.isnan(study.board().loc["b", "adjusted_p"])


def test_context_keys_become_board_columns(study):
    saved(
        study,
        record("a", hours=1, context={"Returns": "net of funding"}),
        record("b", context={"Checks": "passed"}),
    )

    board = study.board()

    assert list(board.columns[len(BOARD_COLUMNS) :]) == ["Returns", "Checks"]
    assert board.loc["a", "Returns"] == "net of funding"
    assert pd.isna(board.loc["b", "Returns"])


def test_a_record_with_unknown_fields_still_counts(study):
    fields = record("a").model_dump(mode="json", exclude={"family"})
    fields |= {"interval": "1h", "checks": {"causal": True}, "candles": 1000}
    (study.directory / "a").mkdir(parents=True)
    (study.directory / "a" / RECORD).write_text(json.dumps(fields), encoding="utf-8")

    (trial,) = study.trials()

    assert trial.family == "momentum"
    assert study.board().loc["a", "trials"] == 1


def test_a_record_of_a_newer_format_is_unreadable(study):
    fields = record("a").model_dump(mode="json") | {"format_version": 2}
    (study.directory / "a").mkdir(parents=True)
    (study.directory / "a" / RECORD).write_text(json.dumps(fields), encoding="utf-8")

    assert study.trials() == []
    assert study.unreadable() == [study.directory / "a" / RECORD]


def test_the_board_sorts_by_a_column_with_undefined_values_last(study):
    saved(
        study,
        record("low", hours=1, cs_ic=-0.01, p=0.01),
        record("none", hours=2, cs_ic=None, p=None),
        record("high", hours=3, cs_ic=0.05, p=0.1),
    )

    assert study.board(sort="cs_ic").index.tolist() == ["high", "low", "none"]
    assert study.board(sort="cs_ic", descending=False).index.tolist() == ["low", "high", "none"]
    assert study.board(sort="adjusted_p").index.tolist() == ["low", "high", "none"]


def test_the_board_sorts_by_a_context_key(study):
    saved(
        study,
        record("a", hours=1, context={"Returns": "price only"}),
        record("b", hours=2, context={"Returns": "net of funding"}),
    )

    assert study.board(sort="Returns").index.tolist() == ["b", "a"]


@pytest.mark.parametrize("key", ["sharpe", "parameters"])
def test_sorting_by_an_unknown_column_lists_the_known_ones(study, key):
    saved(study, record("a"))

    with pytest.raises(ValueError, match=r"sort by one of created_at, signal"):
        study.board(sort=key)


def test_to_dict_lists_the_trials_in_board_order_as_plain_json(study, boundary):
    saved(
        study,
        record("low", hours=1, cs_ic=-0.01, p=0.01, context={"Returns": "price only"}),
        record("none", hours=2, cs_ic=None, p=None, note="smoothed", parameters={"window": 5}),
        record("high", hours=3, signal="bollinger", cs_ic=0.05, p=0.1, sample="holdout"),
    )
    (study.directory / "low" / TEARSHEET).write_text("<html></html>", encoding="utf-8")
    (study.directory / "broken").mkdir()
    (study.directory / "broken" / RECORD).write_text("{", encoding="utf-8")

    document = study.to_dict(sort="cs_ic")

    json.dumps(document, allow_nan=False)
    assert (document["format"], document["format_version"]) == ("alphatonic.study", 1)
    assert (document["name"], document["holdout_start"]) == ("demo", boundary.isoformat())
    assert (document["horizon"], document["horizons"]) == (1, [1, 4])
    assert (document["sort"], document["descending"]) == ("cs_ic", True)
    assert [trial["id"] for trial in document["trials"]] == list(study.board(sort="cs_ic").index)
    assert document["families"] == {
        "momentum": {"trials": 2, "holdout_uses": 0},
        "bollinger": {"trials": 1, "holdout_uses": 1},
    }
    assert document["context_keys"] == ["Returns"]
    assert document["unreadable"] == ["broken/record.json"]
    low, none = (next(t for t in document["trials"] if t["id"] == i) for i in ("low", "none"))
    assert low["cs_ic"] == -0.01 and low["adjusted_p"] == pytest.approx(0.02)
    assert low["trials"] == 2 and low["context"] == {"Returns": "price only"}
    assert low["created_at"] == "2026-01-01T01:00:00+00:00"
    assert low["files"] == {"record": "low/record.json", "tearsheet": "low/tearsheet.html"}
    assert none["cs_ic"] is None and none["adjusted_p"] is None
    assert none["files"]["tearsheet"] is None  # No stored page and no tables to draw one from.
    assert (none["note"], none["parameters"], none["context"]) == ("smoothed", {"window": 5}, {})


def test_to_dict_takes_the_boards_horizon_and_order(study):
    saved(study, record("a", hours=1), record("b", hours=2))

    assert study.to_dict()["sort"] == "created_at" and study.to_dict()["descending"] is True
    assert [t["id"] for t in study.to_dict()["trials"]] == ["b", "a"]
    assert [t["id"] for t in study.to_dict(descending=False)["trials"]] == ["a", "b"]
    four = study.to_dict(4)
    assert four["horizon"] == 4 and four["trials"][0]["cs_ic"] is None
    with pytest.raises(ValueError, match="sort by one of"):
        study.to_dict(sort="sharpe")


def test_an_empty_study_is_an_empty_document(tmp_path):
    document = Study(tmp_path / "absent").to_dict()

    assert document["trials"] == [] and document["families"] == {}
    assert document["horizon"] is None and document["horizons"] == []


def test_to_dict_links_the_tearsheet_of_a_trial_that_can_be_drawn(study, market):
    factor, prices = market
    trial = study.evaluate(factor, prices, signal="momentum", **QUICK)

    (row,) = study.to_dict()["trials"]

    assert not (study.directory / trial.id / TEARSHEET).exists()
    assert row["files"] == {
        "record": f"{trial.id}/record.json",
        "tearsheet": f"{trial.id}/tearsheet.html",
    }
