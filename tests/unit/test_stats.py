from math import atan, pi

import numpy as np
import pandas as pd
import pytest
from hypothesis import given
from scipy.stats import t

from alphatonic import stats
from tests.support.assertions import same_numbers
from tests.support.oracles import correlation, ewc, hac, ranks
from tests.support.strategies import paired_vectors


@pytest.mark.parametrize("method", ["pearson", "spearman", "cosine"])
@pytest.mark.parametrize(
    "x,y",
    [
        ([1, 2, 3], [3, 2, 1]),
        ([1, 2, 3], [1, -2, 1]),
        ([0.1] * 4, [1, 2, 3, 4]),
        ([0] * 4, [1, 2, 3, 4]),
        ([1, 2], [2, 3]),
        ([1, np.nan, 2, 2, 4], [2, 9, 1, 1, 3]),
        ([1e300, 2e300, 3e300], [-3e300, 2e300, 1e300]),
        ([np.nan] * 3, [1, 2, 3]),
    ],
)
def test_correlations_scalar_definition(x, y, method):
    same_numbers(
        stats.correlations(np.array(x)[:, None], np.array(y)[:, None], method),
        [correlation(x, y, method)],
    )


@pytest.mark.property
@given(paired_vectors)
def test_correlations_generated_pairs_match_scalar(pairs):
    x, y = np.array(pairs).T
    for method in ("pearson", "spearman", "cosine"):
        expected = correlation(x, y, method)
        same_numbers(stats.correlations(x[:, None], y[:, None], method), [expected])
        same_numbers(stats.correlations((x * 7)[:, None], (y * 3)[:, None], method), [expected])


@pytest.mark.parametrize("n", [1, 255, 256, 257])
def test_ranks_rows_and_strided_chunks_match_scalar(n):
    rng = np.random.default_rng(12)
    x = rng.integers(-3, 4, (n, 8)).astype(float)
    y = rng.normal(size=x.shape)
    x[::7, ::2] = np.nan
    for a, b in [(x, y), (x[:, ::2], y[:, ::2])]:
        expected = np.full(a.shape, np.nan)
        for j in range(a.shape[1]):
            mask = np.isfinite(a[:, j])
            expected[mask, j] = ranks(a[mask, j].tolist())
        same_numbers(stats.average_ranks(a), expected)
        same_numbers(
            stats.row_correlations(a, b, "spearman"),
            [correlation(u, v, "spearman") for u, v in zip(a, b, strict=True)],
        )


@pytest.mark.parametrize("method", ["pearson", "spearman", "cosine"])
def test_resampled_correlations_rerank_repeated_rows(method):
    x = np.array([[1, 0], [2, 1], [2, 2], [4, 3], [np.nan, 4]], float)
    y = np.array([[4, 2], [1, 3], [2, 4], [3, 1], [9, 5]], float)
    resampled = stats.ResampledCorrelations(x, y)
    for weights in ([1, 1, 1, 1, 1], [0, 3, 2, 0, 1], [6, 0, 0, 0, 0], [0] * 5):
        rows = np.repeat(np.arange(5), weights)
        same_numbers(
            resampled(np.array(weights, float), method),
            [correlation(x[rows, j], y[rows, j], method) for j in range(2)],
        )


@pytest.mark.parametrize("method", ["pearson", "spearman", "cosine"])
def test_standardized_products_preserve_positions_and_sum(method):
    x = np.array([[1, 0], [2, 0], [np.nan, 0], [4, 0], [5, 0]], float)
    y = np.array([[2, 1], [1, 2], [3, 4], [4, 3], [3, 5]], float)
    products, count = stats.standardized_products(x, y, method)
    assert count.tolist() == [4, 5]
    assert products[2, 0] == 0
    assert np.all(products[:, 1] == 0)
    assert products[:, 0].sum() == pytest.approx(4 * correlation(x[:, 0], y[:, 0], method))


def test_cosine_population_static_and_timing_split():
    x = np.array([1, 2, 4, 7.0])[:, None]
    y = np.array([2, -1, 3, 5.0])[:, None]
    cosine, static = stats.cosine_parts(x, y)
    denom = np.sqrt(np.mean(x * x) * np.mean(y * y))
    assert static[0] == pytest.approx(np.mean(x) * np.mean(y) / denom)
    assert cosine[0] - static[0] == pytest.approx(np.mean((x - x.mean()) * (y - y.mean())) / denom)


@pytest.mark.parametrize("q", [2, 5, 9])
def test_buckets_paired_ranks_counts_and_empty_means(q):
    x = np.array([[1, 2, 2, 4, np.nan], [0.1, 0.1, 0.1, 0.1, 0.1]])
    y = np.array([[4, 3, 2, np.nan, 1], [1, 2, 3, 4, 5.0]])
    means, counts, usable = stats.bucket_means(x, y, q)
    assert usable.tolist() == [True, False]
    bins = np.ceil(q * np.array(ranks([1, 2, 2])) / 3).astype(int)
    for bucket in range(1, q + 1):
        selected = np.array([4, 3, 2])[bins == bucket]
        assert counts[0, bucket - 1] == len(selected)
        same_numbers([means[0, bucket - 1]], [selected.mean() if len(selected) else np.nan])
    assert counts[1].sum() == 0
    assert np.isnan(means[1]).all()
    assert stats.quantile_rows(pd.Series([1, 1, 1]), pd.Series([2, 3, 4]), q) == []


@pytest.mark.parametrize("values", [[], [0.2], [0.2, 0.2], [1, -1], [1, np.nan, -0.3, 0.2, 0.5, 0]])
@pytest.mark.parametrize("lags", [0, 1, 3, 8])
def test_summary_counts_omissions_and_direct_hac(values, lags):
    result = stats.summarize_ic(pd.Series(values, dtype=float), lags)
    valid = np.array(values)[np.isfinite(values)]
    assert result["n_periods"] == len(valid)
    if not len(valid):
        assert set(result) == {"n_periods", "hac_lags"}
        return
    assert result["mean"] == pytest.approx(valid.mean())
    assert result["positive_fraction"] == pytest.approx((valid > 0).mean())
    if len(valid) > lags + 1 and np.std(valid) > 1e-12:
        assert result["hac_se"] == pytest.approx(hac(values, lags))
    else:
        assert "hac_se" not in result


@pytest.mark.parametrize("n", [3, 8, 31, 256, 257])
@pytest.mark.parametrize("h", [1, 3, 100])
def test_ewc_integer_floor_and_horizon_cap(n, h):
    terms = sum(125 * j**3 <= 8 * n * n for j in range(1, n + 1))
    assert stats.ewc_dof(n, h) == min(terms, n // (2 * h))
    x = np.random.default_rng(n).normal(size=(n, 3))
    same_numbers(stats.ewc_long_run_variance(x, min(n - 1, 3)), ewc(x, min(n - 1, 3)))


@pytest.mark.parametrize("dof", [1, 2, 3, 10, 100, 1000])
def test_student_t_survival_probabilities(dof):
    values = np.array([0, 1e-10, 0.1, 1, 4, 15, 100, np.inf, np.nan])
    actual = stats.t_p_value(values, dof)
    expected = 2 * t.sf(values, dof)
    if dof == 1:
        expected[1] = 1 - 2 * atan(values[1]) / pi
    same_numbers(actual, expected)
    np.testing.assert_allclose(actual[:-1], expected[:-1], rtol=2e-12, atol=0)
    same_numbers(stats.t_p_value(-values, dof), actual)
    assert np.all(np.diff(actual[:-1]) <= 0)
    if dof == 1:
        assert actual[3] == pytest.approx(0.5)
        assert actual[4] == pytest.approx(1 - 2 * atan(4) / pi)


def test_student_cauchy_extreme_tail_analytic_nonzero():
    values = np.array([1e4, 1e10, 1e100])
    expected = np.array([2 * atan(1 / value) / pi for value in values])
    actual = stats.t_p_value(values, 1)
    assert (actual > 0).all()
    np.testing.assert_allclose(actual, expected, rtol=5e-13, atol=0)
