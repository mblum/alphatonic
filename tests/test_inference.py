"""Statistical behaviour of the inference under a true null, with fixed seeds."""

import numpy as np
import pandas as pd
import pytest

from alphatonic import evaluate
from alphatonic.config import TS_METHODS
from alphatonic.returns import scale_by_volatility
from alphatonic.time_series import hac_tests

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
    """Shares of null evaluations (scores independent of returns) that reject at the 5% level.

    `cs_hac` and `cs_naive` test the mean cross-sectional rank IC with the Newey-West and with the
    plain standard error. `ts_mean` and `ts_assets` hold, per method, the time-series t-tests of
    the mean IC over assets and of each asset's IC; `ts_naive` tests each asset's rank IC as if
    its bars were independent.
    """
    rng = np.random.default_rng(seed)
    cs_hac = cs_naive = ts_naive = 0.0
    ts_mean, ts_assets = dict.fromkeys(TS_METHODS, 0.0), dict.fromkeys(TS_METHODS, 0.0)
    for _ in range(repetitions):
        prices = pd.DataFrame(
            100 * np.cumprod(1 + rng.normal(0, 0.01, size=(BARS, ASSETS)), axis=0), index=INDEX
        )
        scores = persistent_scores(rng, persistence)
        result = evaluate(scores, prices, horizons=[horizon], time_series=TS)
        row = result.summary.query("method == 'spearman'").iloc[0]
        cs_hac += row.hac_p_value < 0.05
        cs_naive += abs(row["mean"] / (row["std"] / np.sqrt(row.n_periods))) > 1.96
        summary, assets = result.time_series.summary.set_index("method"), result.time_series.assets
        for method in TS_METHODS:
            ts_mean[method] += summary.loc[method, "hac_p_value"] < 0.05
            ts_assets[method] += (assets.loc[assets.method == method, "hac_p_value"] < 0.05).mean()
        rank = assets.loc[assets.method == "spearman"]
        t = rank.ic * np.sqrt((rank.n_pairs - 2) / (1 - rank.ic**2))
        ts_naive += (t.abs() > 1.96).mean()
    return {
        "cs_hac": cs_hac / repetitions,
        "cs_naive": cs_naive / repetitions,
        "ts_naive": ts_naive / repetitions,
        "ts_mean": {method: count / repetitions for method, count in ts_mean.items()},
        "ts_assets": {method: count / repetitions for method, count in ts_assets.items()},
    }


def test_one_bar_horizon_is_calibrated():
    rates = rejection_rates(horizon=1, persistence=0.9)
    assert 0.02 <= rates["cs_hac"] <= 0.12
    assert 0.02 <= rates["cs_naive"] <= 0.12
    for method in TS_METHODS:
        assert 0.02 <= rates["ts_mean"][method] <= 0.1
        assert 0.03 <= rates["ts_assets"][method] <= 0.08


def test_hac_corrects_the_overconfidence_of_overlapping_labels_with_persistent_scores():
    rates = rejection_rates(horizon=5, persistence=0.9)
    # Persistent scores and overlapping returns make adjacent ICs dependent, so ignoring the
    # dependence rejects a true null far too often; the Newey-West p-value stays near 5%.
    assert rates["cs_naive"] > 0.25
    assert rates["cs_hac"] < 0.14
    assert rates["cs_hac"] < rates["cs_naive"] / 2
    # Over time it is the same: an asset's IC tested as if its bars were independent rejects far
    # too often, and the time-series t-tests stay near 5%.
    assert rates["ts_naive"] > 0.25
    for method in TS_METHODS:
        assert 0.02 <= rates["ts_mean"][method] <= 0.1
        assert 0.03 <= rates["ts_assets"][method] <= 0.08


def shared_market(rng, n_bars, persistence, share=0.5):
    """Scores independent of returns, each with a part common to all assets.

    `share` of the variance of the scores, which are AR(1) with `persistence`, and of the
    returns comes from one series that every asset has: a market-wide signal and a market factor.
    """
    index = pd.date_range("2020-01-01", periods=n_bars, freq="D", tz="UTC")
    scores = np.sqrt(share) * persistent_scores_like(rng, n_bars, 1, persistence)
    scores = scores + np.sqrt(1 - share) * persistent_scores_like(rng, n_bars, ASSETS, persistence)
    shocks = np.sqrt(share) * rng.normal(size=(n_bars, 1))
    shocks = shocks + np.sqrt(1 - share) * rng.normal(size=(n_bars, ASSETS))
    prices = 100 * np.cumprod(1 + 0.01 * shocks, axis=0)
    return pd.DataFrame(scores, index=index), pd.DataFrame(prices, index=index)


def test_assets_that_share_a_signal_and_a_market_are_tested_together():
    # A market-wide part in both scores and returns makes the assets' ICs move together, so a
    # t-test across assets takes one common draw for twenty. Adding the assets' contributions bar
    # by bar keeps the test of the mean IC near 5%. And 400 bars hold few independent 20-bar
    # labels: with Lazarus et al.'s 0.4 * n ** (2/3) cosine terms each asset's test rejects too
    # often, and capping the terms so that each spans four horizons brings it back near 5%.
    rng = np.random.default_rng(31)
    repetitions, horizon = 200, 20
    across = 0.0
    pooled = dict.fromkeys(TS_METHODS, 0.0)
    capped, uncapped = dict.fromkeys(TS_METHODS, 0.0), dict.fromkeys(TS_METHODS, 0.0)
    for _ in range(repetitions):
        scores, prices = shared_market(rng, 400, persistence=0.98)
        result = evaluate(scores, prices, horizons=[horizon], time_series=TS)
        mean = result.time_series.summary.set_index("method").hac_p_value
        assets = result.time_series.assets
        rank = assets.loc[assets.method == "spearman", "ic"]
        across += abs(rank.mean() / (rank.std() / np.sqrt(len(rank)))) > 2.093  # t, 19 dof, 5%
        target = scale_by_volatility(result.forward_returns[horizon], result.volatility, horizon)
        # The bars whose label ends inside the window.
        x, y = scores.iloc[:-horizon], target.iloc[:-horizon]
        tests, _ = hac_tests(x, y, assets, horizon, dof=int(0.4 * len(x) ** (2 / 3)))
        for method in TS_METHODS:
            pooled[method] += mean[method] < 0.05
            rows = assets.loc[assets.method == method].set_index("asset")
            capped[method] += (rows.hac_p_value < 0.05).mean()
            uncapped[method] += np.mean(
                [tests[method, a]["hac_p_value"] < 0.05 for a in rows.index]
            )
    assert across / repetitions > 0.3
    for method in TS_METHODS:
        assert pooled[method] / repetitions <= 0.1
        assert capped[method] / repetitions <= 0.08
        assert uncapped[method] / repetitions > capped[method] / repetitions + 0.015


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
    # The cosine's test asks whether the position earns anything, and it earns the drift; the
    # rank and linear ICs' tests ask about timing, and find none.
    assert cosine.hac_p_value < 0.001
    assert (summary.loc[["spearman", "pearson"], "hac_p_value"] > 0.05).all()


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
