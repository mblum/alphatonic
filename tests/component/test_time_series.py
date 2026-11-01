import numpy as np
import pandas as pd
import pytest

from alphatonic.time_series import bootstrap_intervals, hac_tests, monthly_statistics, window_table
from tests.support.assertions import same_numbers
from tests.support.oracles import correlation, ewc


def test_window_exact_end_counts_and_method_degeneracy(panel, config):
    x, y = panel
    x = x.iloc[:12].copy()
    y = y.iloc[:12].copy()
    x.iloc[:, 0] = 0.1
    x.iloc[:, 1] = 0
    y.iloc[:, 2] = 0
    y.iloc[2, 3] = np.nan
    endpoints = pd.DatetimeIndex([*x.index[2:], pd.NaT, pd.NaT])
    end = x.index[10]
    table = window_table(x, y, config, 2, x.index[0], end, endpoints)
    for row in table.itertuples():
        a = x[row.asset].iloc[:8].to_numpy()
        b = y[row.asset].iloc[:8].to_numpy()
        count = (np.isfinite(a) & np.isfinite(b)).sum()
        assert row.n_expected == 8 and row.boundary_excluded == 2
        assert row.n_pairs == count
        assert row.first_pair == x.index[0] and row.last_pair == x.index[7]
        assert row.pair_coverage == pytest.approx(count / 8)
        same_numbers([row.ic], [correlation(a, b, row.method)])
        if row.method == "cosine" and np.isfinite(row.ic):
            assert row.ic_timing + row.ic_static == pytest.approx(row.ic)
    assert (
        table.loc[(table.asset == x.columns[0]) & (table.method == "pearson"), "status"].item()
        == "constant_signal"
    )
    assert (
        table.loc[(table.asset == x.columns[1]) & (table.method == "cosine"), "status"].item()
        == "zero_signal"
    )


@pytest.mark.parametrize(
    "complete,min_horizons,min_pairs,coverage,reason",
    [
        (False, 100, 100, 1, "partial_window"),
        (True, 100, 100, 1, "short_window"),
        (True, 1, 100, 1, "insufficient_pairs"),
        (True, 1, 3, 1, "low_coverage"),
    ],
)
def test_window_status_precedence(
    panel, config, complete, min_horizons, min_pairs, coverage, reason
):
    x, y = panel
    x = x.iloc[:12].copy()
    y = y.iloc[:12].copy()
    x.iloc[0] = np.nan
    opts = config.time_series.model_copy(
        update={"min_horizons": min_horizons, "min_pairs": min_pairs, "min_coverage": coverage}
    )
    table = window_table(
        x,
        y,
        config.model_copy(update={"time_series": opts}),
        1,
        x.index[0],
        x.index[-1],
        x.index,
        complete=complete,
    )
    assert set(table.status) == {reason}
    assert table.ic.isna().all()


def test_bootstrap_shared_circular_draws_match_explicit_resampling(panel, config):
    x, y = (t.iloc[:30, :2] for t in panel)
    assets = window_table(x, y, config, 1, x.index[0], x.index[-1] + pd.Timedelta("1D"), x.index)
    options = config.time_series.model_copy(
        update={"bootstrap_samples": 100, "block_bars": 3, "seed": 18}
    )
    actual, aggregate = bootstrap_intervals(
        x, y, assets, config.model_copy(update={"time_series": options}), 1
    )
    rng = np.random.default_rng(np.random.SeedSequence([18, 1]))
    draws = {m: [] for m in ["pearson", "spearman", "cosine"]}
    for _ in range(100):
        starts = rng.integers(0, 30, 10)
        indices = [(int(start) + offset) % 30 for start in starts for offset in range(3)][:30]
        for method in draws:
            draws[method].append(
                [correlation(x.iloc[indices, j], y.iloc[indices, j], method) for j in range(2)]
            )
    for method, samples in draws.items():
        samples = np.array(samples)
        for j, asset in enumerate(x):
            result = actual[method, asset]
            assert result["bootstrap_valid"] == 100
            same_numbers(
                [result["ci95_lower"], result["ci95_upper"]],
                np.quantile(samples[:, j], [0.025, 0.975]),
            )
        same_numbers(
            [aggregate[method]["ci95_lower"], aggregate[method]["ci95_upper"]],
            np.quantile(samples.mean(axis=1), [0.025, 0.975]),
        )


def test_hac_aggregate_keeps_cross_asset_covariance(panel, config):
    x, y = panel
    x = x.iloc[:40, :2]
    y = y.iloc[:40, :2]
    assets = window_table(x, y, config, 1, x.index[0], x.index[-1] + pd.Timedelta("1D"), x.index)
    per_asset, aggregate = hac_tests(x, y, assets, 1, dof=3)
    a = x.to_numpy()
    b = y.to_numpy()
    products = (a / np.sqrt(np.mean(a * a, axis=0))) * (b / np.sqrt(np.mean(b * b, axis=0)))
    contributions = products / len(x)
    expected = np.sqrt(
        len(x) * ewc(np.column_stack([contributions, contributions.mean(axis=1)]), 3)
    )
    assert aggregate["cosine"]["hac_se"] == pytest.approx(expected[-1])
    for j, asset in enumerate(x):
        assert per_asset["cosine", asset]["hac_se"] == pytest.approx(expected[j])


def test_monthly_icir_missing_and_constant():
    result = monthly_statistics(pd.Series([0.1, np.nan, 0.3, 0.2]), 3)
    assert result["valid_months"] == 3 and result["skipped_months"] == 1
    assert result["monthly_ic_ir"] == pytest.approx(2)
    assert np.isnan(monthly_statistics(pd.Series([0.1, 0.1, 0.1]), 3)["monthly_ic_ir"])


@pytest.mark.parametrize(
    "samples,n,block,all_missing,status",
    [
        (0, 30, 3, False, "disabled"),
        (100, 14, 3, False, "too_few_blocks"),
        (100, 30, 3, True, "no_eligible_assets"),
        (100, 30, 3, False, "valid"),
    ],
)
def test_bootstrap_eligibility_decisions(panel, config, samples, n, block, all_missing, status):
    x, y = (table.iloc[:n] for table in panel)
    assets = window_table(x, y, config, 1, x.index[0], x.index[-1] + pd.Timedelta("1D"), x.index)
    if all_missing:
        assets["ic"] = np.nan
    options = config.time_series.model_copy(
        update={"bootstrap_samples": samples, "block_bars": block}
    )
    per_asset, aggregate = bootstrap_intervals(
        x, y, assets, config.model_copy(update={"time_series": options}), 1
    )
    assert {r["bootstrap_status"] for r in aggregate.values()} == {status}
    if status != "valid":
        assert all(np.isnan(r["ci95_lower"]) for r in aggregate.values())


def test_bootstrap_constant_resamples_fail_minimum_valid_draws(config):
    # The sole nonzero observation is absent from some circular draws: no 100 valid draws.
    x = pd.DataFrame({"a": [0.0] * 29 + [1.0]})
    y = pd.DataFrame({"a": np.arange(30, dtype=float)})
    assets = pd.DataFrame(
        {"asset": ["a"] * 3, "method": ["pearson", "spearman", "cosine"], "ic": [0.1] * 3}
    )
    options = config.time_series.model_copy(update={"bootstrap_samples": 100, "block_bars": 3})
    per_asset, aggregate = bootstrap_intervals(
        x, y, assets, config.model_copy(update={"time_series": options}), 1
    )
    for method, result in aggregate.items():
        assert result["bootstrap_status"] == "insufficient_draws"
        assert result["bootstrap_valid"] < 100
        assert np.isnan(result["ci95_lower"])
        assert per_asset[method, "a"]["bootstrap_status"] == "insufficient_draws"


def test_no_eligible_label_end_and_no_ewc_dof(panel, config):
    x, y = (table.iloc[:5] for table in panel)
    table = window_table(x, y, config, 1, x.index[0], x.index[-1], pd.DatetimeIndex([pd.NaT] * 5))
    assert table.n_expected.eq(0).all() and table.first_pair.isna().all()
    assert table.status.eq("insufficient_pairs").all()
    _, aggregate = hac_tests(x, y, table, 100)
    assert all(v["hac_dof"] == 0 and np.isnan(v["hac_p_value"]) for v in aggregate.values())


def test_leap_months_rolling_membership_and_equal_asset_summary(config):
    from alphatonic.time_series import evaluate_time_series

    index = pd.date_range("2024-01-15", "2024-04-10", tz="UTC")
    rng = np.random.default_rng(12)
    x = pd.DataFrame(rng.normal(size=(len(index), 2)), index=index, columns=["a", "b"])
    y = pd.DataFrame(rng.normal(size=x.shape), index=index, columns=x.columns)
    y.loc[y.index[::2], "b"] = np.nan
    start = index[0]
    end = index[-1] + pd.Timedelta("1D")
    result = evaluate_time_series(x, {1: y}, config, index, start, end)
    for row in result.monthly.itertuples():
        in_window = (index >= row.window_start) & (index < row.window_end)
        ends = pd.Series(index).shift(-1)
        eligible = in_window & (ends < row.window_end).to_numpy()
        assert row.n_expected == eligible.sum()
        if row.window_start.month == 2:
            assert row.complete and row.n_expected == 28 and row.boundary_excluded == 1
        if row.status == "valid":
            assert row.ic == pytest.approx(
                correlation(x.loc[eligible, row.asset], y.loc[eligible, row.asset], row.method)
            )
    for row in result.rolling.itertuples():
        assert row.window_start == max(
            start, row.window_end - pd.Timedelta(config.time_series.rolling_window)
        )
    for row in result.summary.itertuples():
        values = result.assets.loc[result.assets.method == row.method, "ic"].dropna()
        assert row.mean == pytest.approx(values.mean())
        assert row.n_assets == len(values)
