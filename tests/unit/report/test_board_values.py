import pytest

from alphatonic.report.board import (
    _bar,
    _chosen,
    _matches,
    _number,
    _p_value,
    _ranks,
    _varying,
    _when,
)


@pytest.mark.parametrize(
    "values,larger,expected",
    [
        ([0.2, None, 0.4, 0.4], True, [3, None, 1, 1]),
        ([0.2, None, 0.4, 0.4], False, [1, None, 2, 2]),
        ([None, None], True, [None, None]),
    ],
)
def test_board_ranks_ties_and_missing(values, larger, expected):
    assert _ranks(values, larger) == expected


def test_board_missing_and_group_display():
    assert _number(None) == "–" and _p_value(None) == "–"
    assert _when(None) == "–" and _bar(None) == "–"
    assert _chosen(None) is None


def _trial(signal, parameters, note=None):
    return {
        "id": f"20240101-000000-{signal}-abc123",
        "signal": signal,
        "family": signal,
        "note": note,
        "sample": "in_sample",
        "parameters": parameters,
        "context": {"Returns": "net of funding"},
    }


def test_board_names_the_parameters_that_tell_a_signals_trials_apart():
    trials = [
        _trial("trend", {"length": 5, "scale": "atr"}),
        _trial("trend", {"length": 20, "scale": "atr", "cap": 2.0}),
        _trial("carry", {"length": 5}),
    ]
    assert _varying(trials) == {"trend": {"length", "cap"}, "carry": set()}


@pytest.mark.parametrize(
    "terms,expected",
    [
        ([], True),
        (["length=20"], True),
        (["trend", "neighbour"], True),
        (["net", "funding", "in sample"], True),
        (["abc123"], True),
        (["length=2", "carry"], False),
    ],
)
def test_board_search_needs_every_term_in_what_the_row_says(terms, expected):
    trial = _trial("Trend", {"length": 20}, note="Neighbour of the first")
    assert _matches(trial, terms) is expected


@pytest.mark.parametrize(
    "kind,expected",
    [
        ("business", True),
        ("regular", False),
        ("missing_weekday", False),
        ("corrupt", False),
        ("absent", False),
    ],
)
def test_business_day_grid_requires_complete_weekdays(tmp_path, kind, expected):
    import pandas as pd

    from alphatonic.report.board import _business_day

    if kind == "business":
        index = pd.date_range("2024-01-01", periods=10, freq="B", tz="UTC")
    elif kind == "missing_weekday":
        index = pd.date_range("2024-01-01", periods=10, freq="B", tz="UTC").delete(2)
    else:
        index = pd.date_range("2024-01-01", periods=10, freq="D", tz="UTC")
    if kind == "corrupt":
        (tmp_path / "ic_by_timestamp.csv").write_text("bad\n1\n")
    elif kind != "absent":
        pd.DataFrame({"timestamp": index}).to_csv(tmp_path / "ic_by_timestamp.csv", index=False)
    assert _business_day(tmp_path) is expected
