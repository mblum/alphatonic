import numpy as np
import pandas as pd
import pytest

from alphatonic import evaluate
from alphatonic.demo import synthetic_market


def test_shapes_index_and_determinism():
    factor, prices = synthetic_market(n_assets=7, n_bars=120, seed=3)
    assert factor.shape == prices.shape == (120, 7)
    assert factor.index.equals(prices.index) and factor.index.tz is None
    assert list(prices.columns) == [f"A{i:03d}" for i in range(7)]
    assert (prices > 0).all().all() and (prices.iloc[0] == 100).all()
    again = synthetic_market(n_assets=7, n_bars=120, seed=3)
    pd.testing.assert_frame_equal(factor, again[0])
    pd.testing.assert_frame_equal(prices, again[1])
    assert not factor.equals(synthetic_market(n_assets=7, n_bars=120, seed=4)[0])


def test_business_day_calendar_is_the_default():
    factor, _ = synthetic_market(n_bars=30)
    assert factor.index.day_of_week.max() <= 4
    hourly, _ = synthetic_market(n_bars=30, freq="h")
    assert hourly.index[1] - hourly.index[0] == pd.Timedelta(hours=1)


def test_missing_fraction_masks_prices_only():
    factor, prices = synthetic_market(n_assets=20, n_bars=200, missing_fraction=0.1, seed=1)
    assert prices.isna().to_numpy().mean() == pytest.approx(0.1, abs=0.02)
    assert factor.notna().all().all()


def test_population_ic_matches_the_request():
    for target in (0.0, 0.05, 0.15):
        factor, prices = synthetic_market(n_assets=60, n_bars=500, ic=target, seed=2)
        result = evaluate(factor, prices, horizons=[1], mode="cross_sectional")
        assert result.summary.query("method == 'pearson'")["mean"].iloc[0] == pytest.approx(
            target, abs=0.015
        )


@pytest.mark.parametrize("option", ["ic", "persistence", "missing_fraction"])
@pytest.mark.parametrize("value", [-0.1, 1.0])
def test_invalid_fractions_are_rejected(option, value):
    with pytest.raises(ValueError, match=r"\[0, 1\)"):
        synthetic_market(**{option: value})


def test_no_nonfinite_values_without_missing_fraction():
    factor, prices = synthetic_market(seed=5)
    assert np.isfinite(factor.to_numpy()).all() and np.isfinite(prices.to_numpy()).all()
