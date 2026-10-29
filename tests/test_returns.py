import numpy as np
import pandas as pd
import pytest

from alphatonic import bar_volatility, forward_returns
from alphatonic.returns import label_endpoints, scale_by_volatility


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


def test_volatility_is_the_ewm_standard_deviation_of_one_bar_returns():
    rng = np.random.default_rng(0)
    close = pd.DataFrame(100 * np.cumprod(1 + rng.normal(0, 0.01, (300, 2)), axis=0))
    expected = (close / close.shift(1) - 1).ewm(span=30, min_periods=10).std()
    pd.testing.assert_frame_equal(bar_volatility(close, span=30, min_bars=10), expected)
    assert bar_volatility(close, span=30, min_bars=10).iloc[:10].isna().all().all()


def test_volatility_does_not_look_ahead():
    rng = np.random.default_rng(1)
    close = pd.DataFrame({"A": 100 * np.cumprod(1 + rng.normal(0, 0.01, 200))})
    shocked = close.copy()
    shocked.iloc[120:] *= 3
    before, after = bar_volatility(close), bar_volatility(shocked)
    pd.testing.assert_frame_equal(before.iloc[:120], after.iloc[:120])
    assert after.iloc[120, 0] > before.iloc[120, 0]


def test_volatility_carries_over_gaps_and_is_missing_for_constant_prices():
    rng = np.random.default_rng(2)
    close = pd.DataFrame(
        {"A": 100 * np.cumprod(1 + rng.normal(0, 0.01, 80)), "B": np.full(80, 50.0)}
    )
    close.iloc[40:43, 0] = np.nan
    volatility = bar_volatility(close, span=20, min_bars=5)
    # The returns into and out of the gap are missing; the estimate carries forward.
    assert volatility.iloc[40:44, 0].nunique() == 1 and volatility.iloc[40:44, 0].notna().all()
    assert volatility["B"].isna().all()


def test_scaling_divides_by_the_volatility_of_the_horizon_return():
    labels = pd.DataFrame({"A": [0.04, -0.02, np.nan, 0.01]})
    volatility = pd.DataFrame({"A": [0.01, 0.02, 0.01, np.nan]})
    scaled = scale_by_volatility(labels, volatility, horizon=4)
    assert scaled["A"].tolist()[:2] == pytest.approx([2.0, -0.5])
    assert scaled["A"].iloc[2:].isna().all()
