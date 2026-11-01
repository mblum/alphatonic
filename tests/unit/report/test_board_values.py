import pytest

from alphatonic.report.board import _bar, _chosen, _number, _p_value, _ranks, _when


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
