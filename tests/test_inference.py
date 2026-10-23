"""Statistical behaviour of the inference under a true null, with fixed seeds."""

import numpy as np
import pandas as pd

from alphatonic import evaluate

BARS, ASSETS = 300, 20
INDEX = pd.date_range("2020-01-01", periods=BARS, freq="D", tz="UTC")


def persistent_scores(rng, persistence):
    z = np.empty((BARS, ASSETS))
    z[0] = rng.normal(size=ASSETS)
    for t in range(1, BARS):
        z[t] = persistence * z[t - 1] + np.sqrt(1 - persistence**2) * rng.normal(size=ASSETS)
    return pd.DataFrame(z, index=INDEX)


def rejection_rates(horizon, persistence, repetitions=200, seed=123):
    """Share of null evaluations (scores independent of returns) that reject at the 5% level."""
    rng = np.random.default_rng(seed)
    hac = naive = 0
    for _ in range(repetitions):
        prices = pd.DataFrame(
            100 * np.cumprod(1 + rng.normal(0, 0.01, size=(BARS, ASSETS)), axis=0), index=INDEX
        )
        scores = persistent_scores(rng, persistence)
        row = (
            evaluate(scores, prices, horizons=[horizon], mode="cross_sectional")
            .summary.query("method == 'spearman'")
            .iloc[0]
        )
        hac += row.hac_p_value < 0.05
        naive += abs(row["mean"] / (row["std"] / np.sqrt(row.n_periods))) > 1.96
    return hac / repetitions, naive / repetitions


def test_one_bar_horizon_is_calibrated():
    hac, naive = rejection_rates(horizon=1, persistence=0.9)
    assert 0.02 <= hac <= 0.12
    assert 0.02 <= naive <= 0.12


def test_hac_corrects_the_overconfidence_of_overlapping_labels_with_persistent_scores():
    hac, naive = rejection_rates(horizon=5, persistence=0.9)
    # Persistent scores and overlapping returns make adjacent ICs dependent, so ignoring the
    # dependence rejects a true null far too often; the Newey-West p-value stays near 5%.
    assert naive > 0.25
    assert hac < 0.14
    assert hac < naive / 2


def test_an_informative_factor_is_detected():
    from alphatonic.demo import synthetic_market

    factor, prices = synthetic_market(n_assets=40, n_bars=400, ic=0.08, seed=4)
    row = (
        evaluate(factor, prices, horizons=[1], mode="cross_sectional")
        .summary.query("method == 'spearman'")
        .iloc[0]
    )
    assert row.ci95_lower > 0 and row.hac_p_value < 0.01
    assert 0.04 < row["mean"] < 0.12
