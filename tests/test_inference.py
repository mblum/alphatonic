"""Statistical behaviour of the inference under a true null, with fixed seeds."""

import numpy as np
import pandas as pd
import pytest

from alphatonic import evaluate

BARS, ASSETS = 300, 20
INDEX = pd.date_range("2020-01-01", periods=BARS, freq="D", tz="UTC")
# Time-series options for tests that read neither the bootstrap nor the rolling windows, which
# are most of the cost of an evaluation.
TS = {"bootstrap_samples": 0, "rolling_step": "90D"}


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
            evaluate(scores, prices, horizons=[horizon], time_series=TS)
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
        evaluate(factor, prices, horizons=[1], time_series=TS)
        .summary.query("method == 'spearman'")
        .iloc[0]
    )
    assert row.ci95_lower > 0 and row.hac_p_value < 0.01
    assert 0.04 < row["mean"] < 0.12


def persistent_scores_like(rng, n_bars, n_assets, persistence=0.9):
    z = np.empty((n_bars, n_assets))
    z[0] = rng.normal(size=n_assets)
    for t in range(1, n_bars):
        z[t] = persistence * z[t - 1] + np.sqrt(1 - persistence**2) * rng.normal(size=n_assets)
    return z


def drifting_market(rng, n_assets, n_bars, *, ic, bias, drift_sharpe):
    """Scores with mean `bias` and returns `sigma[t] * (drift + k * score + noise)`.

    Volatility clusters (a log-AR(1) with persistence 0.98) and the skill is in units of risk,
    so the vol-scaled target is the natural one.
    """
    index = pd.date_range("2015-01-01", periods=n_bars, freq="D", tz="UTC")
    log_vol = np.zeros((n_bars, n_assets))
    shocks = rng.normal(0, 0.12, size=(n_bars, n_assets))
    for t in range(1, n_bars):
        log_vol[t] = 0.98 * log_vol[t - 1] + shocks[t]
    sigma = 0.01 * np.exp(log_vol)
    scores = persistent_scores_like(rng, n_bars, n_assets) + bias
    k = ic / np.sqrt(1 - ic**2)
    returns = np.zeros((n_bars, n_assets))
    noise = rng.normal(size=(n_bars, n_assets))
    returns[1:] = sigma[:-1] * (drift_sharpe / np.sqrt(252) + k * (scores[:-1] - bias) + noise[1:])
    prices = 100 * np.cumprod(1 + returns, axis=0)
    columns = [f"A{i}" for i in range(n_assets)]
    return (
        pd.DataFrame(scores, index=index, columns=columns),
        pd.DataFrame(prices, index=index, columns=columns),
    )


def test_a_long_bias_without_timing_skill_is_static_cosine_not_ic():
    # A signal that is long on average earns a rising asset's drift without predicting anything.
    # The rank and linear IC see no skill; the cosine sees the earnings, all in its static part.
    rng = np.random.default_rng(21)
    factor, prices = drifting_market(rng, 12, 2000, ic=0.0, bias=1.0, drift_sharpe=1.0)
    result = evaluate(factor, prices, horizons=[1], time_series=TS)
    summary = result.time_series.summary.set_index("method")
    assert abs(summary.loc["spearman", "mean"]) < 0.015
    assert abs(summary.loc["pearson", "mean"]) < 0.015
    cosine = summary.loc["cosine"]
    assert cosine["mean"] > 0.02
    assert abs(cosine.mean_timing) < 0.015
    assert cosine.mean_static == pytest.approx(cosine["mean"], abs=0.015)


def test_with_vol_scaled_targets_the_cosine_is_close_to_the_per_bar_sharpe_ratio():
    # Holding `score` units of risk earns score * return / volatility each bar.
    rng = np.random.default_rng(22)
    factor, prices = drifting_market(rng, 8, 2500, ic=0.05, bias=0.3, drift_sharpe=0.5)
    result = evaluate(factor, prices, horizons=[1], time_series=TS)
    target = result.forward_returns[1] / result.volatility
    profit = factor * target
    sharpe = profit.mean() / profit.std()
    cosine = result.time_series.assets.query("method == 'cosine'").set_index("asset").ic
    np.testing.assert_allclose(cosine.to_numpy(), sharpe[cosine.index].to_numpy(), atol=0.01)
    assert np.corrcoef(cosine, sharpe[cosine.index])[0, 1] > 0.95
