import numpy as np
import pandas as pd
import pytest

from alphatonic import forward_returns
from alphatonic.returns import label_endpoints


def test_return_alignment_delay_and_trailing_labels():
    close = pd.DataFrame({"A": [10.0, 20, 30, 60, 120]})
    result = forward_returns(close, 2, delay=1)
    assert result.iloc[0, 0] == 2.0  # 60 / 20 - 1
    assert result.iloc[1, 0] == 3.0  # 120 / 30 - 1
    assert result.iloc[2:].isna().all().all()


def test_label_is_simple_return_over_horizon():
    close = pd.DataFrame({"A": [100.0, 110, 121], "B": [50.0, 25, 50]})
    result = forward_returns(close, 1)
    assert result["A"].iloc[:2].tolist() == pytest.approx([0.10, 0.10])
    assert result["B"].iloc[:2].tolist() == pytest.approx([-0.5, 1.0])
    assert result.iloc[-1].isna().all()


def test_missing_price_does_not_shorten_horizon():
    close = pd.DataFrame({"A": [10.0, np.nan, 30, 60, 120]})
    result = forward_returns(close, 2)
    assert result.iloc[:2].isna().all().all()
    assert result.iloc[2, 0] == 3.0


def test_gap_inside_the_path_removes_the_label_even_if_both_ends_exist():
    close = pd.DataFrame({"A": [10.0, 11, np.nan, 13, 14, 15]})
    result = forward_returns(close, 3)
    assert result["A"].isna().all()


def test_nonfinite_returns_are_excluded():
    close = pd.DataFrame({"A": [1e-300, 1e300]})
    assert forward_returns(close, 1).isna().all().all()


def test_columns_are_independent():
    close = pd.DataFrame({"A": [1.0, 2, 3, 4], "B": [1.0, np.nan, 3, 4]})
    result = forward_returns(close, 1)
    assert result["A"].iloc[:3].notna().all()
    assert result["B"].isna().tolist() == [True, True, False, True]


def test_label_endpoints_count_rows_not_clock_time():
    index = pd.DatetimeIndex(["2026-01-02", "2026-01-05", "2026-01-06", "2026-01-07"], tz="UTC")
    ends = label_endpoints(index, 2)
    assert ends[0] == pd.Timestamp("2026-01-06", tz="UTC")
    assert ends[1] == pd.Timestamp("2026-01-07", tz="UTC")
    assert ends[2:].isna().all()
    assert ends.tz is not None
