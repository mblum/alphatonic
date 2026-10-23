import itertools
import math

import numpy as np
import pandas as pd
import pytest
import scipy.stats
import statsmodels.api as sm

import reference
from alphatonic import summarize_ic
from alphatonic.stats import (
    ResampledCorrelations,
    bucket_means,
    correlations,
    quantile_rows,
    row_correlations,
)


def test_correlations_rank_finite_pairs_with_ties_inside_each_column():
    x = np.array([[10.0, 1], [10, 3], [30, np.nan], [20, 4], [99, np.inf]])
    y = np.array([[4.0, 7], [1, 3], [2, 8], [3, 6], [np.nan, 1]])
    for method in ("pearson", "spearman"):
        actual = correlations(x, y, method)
        for i in range(2):
            valid = np.isfinite(x[:, i]) & np.isfinite(y[:, i])
            a, b = pd.Series(x[valid, i]), pd.Series(y[valid, i])
            expected = a.rank().corr(b.rank()) if method == "spearman" else a.corr(b)
            assert actual[i] == pytest.approx(expected)


def test_correlation_rejects_floating_constants_and_handles_large_finite_scores():
    constant = np.full((95, 1), 0.1)
    for method in ("spearman", "pearson"):
        assert np.isnan(correlations(constant, constant, method)[0])
    x = np.array([1e308, 5e307, -1e308])[:, None]
    assert correlations(x, -x, "pearson")[0] == pytest.approx(-1)


def test_too_few_pairs_are_undefined_not_zero():
    x = np.array([[1.0], [2.0]])
    assert np.isnan(correlations(x, x, "pearson")[0])


def test_rounding_noise_is_reported_as_exact_zero():
    # Seven ranks whose squared differences sum to 56 have exactly zero correlation, but
    # floating-point evaluation leaves noise of either sign unless it is snapped.
    x = np.arange(1.0, 8)
    zero = [
        np.array(y)
        for y in itertools.permutations(range(1, 8))
        if ((x - np.array(y)) ** 2).sum() == 56
    ]
    assert len(zero) == 184
    for y in zero[::4]:
        for method in ("pearson", "spearman"):
            assert correlations(x[:, None], y[:, None], method)[0] == 0.0


@pytest.mark.parametrize("seed", range(5))
def test_matches_scipy_with_ties_and_missing_values(seed):
    rng = np.random.default_rng(seed)
    x = np.round(rng.normal(size=(60, 4)), 1)
    y = np.round(rng.normal(size=(60, 4)) + 0.3 * x, 1)
    x[rng.random(x.shape) < 0.1] = np.nan
    for column in range(4):
        valid = np.isfinite(x[:, column]) & np.isfinite(y[:, column])
        expected_rank = scipy.stats.spearmanr(x[valid, column], y[valid, column]).statistic
        expected_linear = scipy.stats.pearsonr(x[valid, column], y[valid, column]).statistic
        assert correlations(x, y, "spearman")[column] == pytest.approx(expected_rank)
        assert correlations(x, y, "pearson")[column] == pytest.approx(expected_linear)


def test_row_correlations_agree_with_column_form_across_blocks():
    rng = np.random.default_rng(1)
    x, y = rng.normal(size=(700, 9)), rng.normal(size=(700, 9))
    expected = [correlations(x[i][:, None], y[i][:, None], "spearman")[0] for i in range(700)]
    assert row_correlations(x, y, "spearman") == pytest.approx(expected)


def test_hac_zero_lags_matches_standard_error():
    values = pd.Series([0.1, 0.2, -0.3, 0.4, -0.1])
    result = summarize_ic(values, lags=0)
    assert result["hac_se"] == pytest.approx(values.std() / math.sqrt(len(values)))


def test_hac_keeps_missing_periods_in_time():
    values = pd.Series([0.1, np.nan, 0.4, -0.3, 0.2, -0.1])
    scores = (values - values.mean()).fillna(0).to_numpy()
    n = values.count()
    expected = math.sqrt((scores @ scores + scores[1:] @ scores[:-1]) / (n * (n - 1)))
    assert summarize_ic(values, lags=1)["hac_se"] == pytest.approx(expected)


@pytest.mark.parametrize("lags", [0, 1, 4, 10])
def test_hac_matches_statsmodels_newey_west(lags):
    rng = np.random.default_rng(7)
    noise = rng.normal(size=400)
    series = pd.Series(0.05 + np.convolve(noise, np.ones(4) / 4, mode="same"))
    ours = summarize_ic(series, lags)
    fit = sm.OLS(series.to_numpy(), np.ones(len(series))).fit(
        cov_type="HAC", cov_kwds={"maxlags": lags, "kernel": "bartlett", "use_correction": True}
    )
    assert ours["mean"] == pytest.approx(fit.params[0])
    assert ours["hac_se"] == pytest.approx(fit.bse[0], rel=1e-9)
    assert ours["hac_p_value"] == pytest.approx(
        2 * scipy.stats.norm.sf(abs(fit.params[0] / fit.bse[0]))
    )
    assert ours["ci95_lower"] == pytest.approx(fit.conf_int(alpha=0.05)[0, 0], rel=1e-9)


def test_inference_omitted_for_constant_or_short_series():
    assert "hac_se" not in summarize_ic(pd.Series([0.5] * 10), lags=1)
    assert "ic_ir" not in summarize_ic(pd.Series([0.5] * 10), lags=1)
    assert "hac_se" not in summarize_ic(pd.Series([0.1, 0.2]), lags=4)
    assert summarize_ic(pd.Series([np.nan]), lags=1) == {"n_periods": 0, "hac_lags": 1}
    one = summarize_ic(pd.Series([0.3, np.nan]), lags=1)
    assert one["mean"] == pytest.approx(0.3) and "std" not in one


def test_icir_is_mean_over_sample_std_without_annualization():
    series = pd.Series([0.1, 0.3, -0.1, 0.2, 0.0, 0.4])
    assert summarize_ic(series, 0)["ic_ir"] == pytest.approx(series.mean() / series.std(ddof=1))


def test_buckets_keep_ties_together_and_empty_buckets_visible():
    x = pd.Series([1.0, 1.0, 1.0, 1.0, 2.0])
    y = pd.Series([0.1, 0.2, 0.3, 0.4, 0.5])
    rows = quantile_rows(x, y, quantiles=5)
    by_bucket = {row["quantile"]: row for row in rows}
    # Four tied scores share the average rank 2.5 of 5 (percentile 0.5), which is bucket 3.
    assert by_bucket[3]["n_pairs"] == 4 and by_bucket[3]["mean_return"] == pytest.approx(0.25)
    assert by_bucket[5]["n_pairs"] == 1
    assert by_bucket[1]["n_pairs"] == 0 and np.isnan(by_bucket[1]["mean_return"])


def test_buckets_are_empty_without_variation():
    assert quantile_rows(pd.Series([1.0, 1.0, 1.0]), pd.Series([1.0, 2.0, 3.0])) == []


@pytest.mark.parametrize("quantiles", [2, 5, 10])
def test_bucket_means_match_reference_rows(quantiles):
    rng = np.random.default_rng(quantiles)
    x = np.round(rng.normal(size=(40, 25)), 1)
    y = rng.normal(size=(40, 25))
    x[rng.random(x.shape) < 0.2] = np.nan
    y[rng.random(y.shape) < 0.1] = np.inf
    means, counts, usable = bucket_means(x, y, quantiles)
    for row in range(len(x)):
        expected = reference.quantile_rows(pd.Series(x[row]), pd.Series(y[row]), quantiles)
        assert usable[row] == bool(expected)
        for item in expected:
            q = item["quantile"] - 1
            assert counts[row, q] == item["n_pairs"]
            if item["n_pairs"]:
                assert means[row, q] == pytest.approx(item["mean_return"])
            else:
                assert np.isnan(means[row, q])


def resample_cases():
    rng = np.random.default_rng(99)
    cases = []
    for kind in ("continuous", "ties", "missing", "constant_column", "tiny"):
        n, k = (6, 3) if kind == "tiny" else (80, 7)
        x = rng.normal(size=(n, k))
        y = rng.normal(size=(n, k)) + 0.4 * x
        if kind == "ties":
            x, y = np.round(x), np.round(y)
        if kind == "missing":
            x[rng.random(x.shape) < 0.25] = np.nan
            y[rng.random(y.shape) < 0.25] = np.inf
        if kind == "constant_column":
            x[:, 0] = 2.5
            y[:, 1] = -1.0
            x[:, 2] = np.where(np.arange(n) < n // 2, np.nan, x[:, 2])
        cases.append((kind, x, y))
    return cases


@pytest.mark.parametrize(
    "kind, x, y", resample_cases(), ids=lambda v: v if isinstance(v, str) else ""
)
@pytest.mark.parametrize("method", ["spearman", "pearson"])
def test_resampled_correlations_equal_correlating_the_resampled_rows(kind, x, y, method):
    rng = np.random.default_rng(5)
    n = len(x)
    resampled = ResampledCorrelations(x, y)
    for _ in range(60):
        block = int(rng.integers(1, 6))
        starts = rng.integers(0, n, size=int(np.ceil(n / block)))
        indices = ((starts[:, None] + np.arange(block)) % n).ravel()[:n]
        expected = correlations(x[indices], y[indices], method)
        actual = resampled(np.bincount(indices, minlength=n).astype(float), method)
        np.testing.assert_allclose(actual, expected, atol=1e-12, rtol=0)
        np.testing.assert_array_equal(np.isnan(actual), np.isnan(expected))


def test_resampling_every_row_once_reproduces_the_sample_correlations():
    kind, x, y = resample_cases()[2]
    ones = np.ones(len(x))
    for method in ("spearman", "pearson"):
        np.testing.assert_allclose(
            ResampledCorrelations(x, y)(ones, method), correlations(x, y, method), atol=1e-12
        )
