import numpy as np
import pandas as pd
import pytest

from alphatonic.returns import bar_volatility, forward_returns, label_endpoints, scale_by_volatility
from tests.support.assertions import same_numbers
from tests.support.oracles import returns


@pytest.mark.parametrize("h", [1, 3, 20])
@pytest.mark.parametrize("delay", [0, 2])
def test_forward_returns_irregular_grid_and_every_gap(h, delay):
    index = pd.to_datetime(
        ["2024-01-01", "2024-01-03", "2024-01-04", "2024-02-01", "2024-02-02", "2024-02-09"]
    )
    base = np.array([[10, 20], [11, 21], [9, 23], [12, 25], [14, 24], [16, 28]], float)
    for gap in range(-1, len(base)):
        prices = base.copy()
        if gap >= 0:
            prices[gap, 0] = np.nan
        actual = forward_returns(pd.DataFrame(prices, index=index), h, delay)
        same_numbers(actual, returns(prices, h, delay))
    endpoints = label_endpoints(index, h + delay)
    for i, stamp in enumerate(endpoints):
        assert pd.isna(stamp) if i + h + delay >= len(index) else stamp == index[i + h + delay]


def test_volatility_direct_exponential_weights_and_ex_ante():
    prices = pd.DataFrame({"a": [100.0, 110.0, 99.0, 108.9, 130.0, 120.0]})
    vol = bar_volatility(prices, span=3, min_bars=2)
    assert vol.iloc[:2].isna().all().all()
    observations = [0.1, -0.1, 0.1, 130 / 108.9 - 1, 120 / 130 - 1]
    for t in range(2, len(prices)):
        weights = 0.5 ** np.arange(t - 1, -1, -1)
        values = np.array(observations[:t])
        mean = np.dot(weights, values) / weights.sum()
        variance = np.dot(weights, (values - mean) ** 2) / (
            weights.sum() - np.dot(weights, weights) / weights.sum()
        )
        assert vol.iloc[t, 0] == pytest.approx(np.sqrt(variance))
    changed = prices.copy()
    changed.iloc[4:] *= 2
    same_numbers(bar_volatility(changed, 3, 2).iloc[:4], vol.iloc[:4])
    assert bar_volatility(prices * 0 + 100, 3, 2).isna().all().all()


def test_scaling_missing_zero_and_overflow():
    labels = pd.DataFrame([2.0, 3.0, np.nan, 1e308])
    vol = pd.DataFrame([0.5, 0.0, 1.0, 1e-300])
    same_numbers(scale_by_volatility(labels, vol, 4), [[2], [np.nan], [np.nan], [np.nan]])


def test_volatility_gap_carries_last_estimate_and_overflow_masks():
    prices = pd.DataFrame([100.0, 110.0, 99.0, np.nan, 120.0, 130.0, 125.0])
    vol = bar_volatility(prices, span=3, min_bars=2)
    assert vol.iloc[2, 0] == pytest.approx(vol.iloc[3, 0])
    assert vol.iloc[3, 0] == pytest.approx(vol.iloc[4, 0])
    tiny = pd.DataFrame([1e-300, 1e300, 2e300])
    assert np.isnan(forward_returns(tiny, 1).iloc[0, 0])
    assert bar_volatility(tiny, 3, 2).isna().all().all()
