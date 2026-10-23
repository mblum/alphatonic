import numpy as np
import pandas as pd
import pytest

from alphatonic import EvaluationConfig, evaluate
from alphatonic.returns import label_endpoints
from alphatonic.time_series import (
    bootstrap_intervals,
    evaluate_time_series,
    monthly_statistics,
    window_table,
)


def make_config(**overrides):
    base = dict(
        start="2026-01-01T00:00:00Z",
        end="2026-01-05T00:00:00Z",
        horizons=[1],
        min_assets=3,
        time_series=dict(
            min_pairs=5,
            min_horizons=1,
            bootstrap_samples=100,
            rolling_window="1D",
            rolling_step="1D",
        ),
    )
    return EvaluationConfig(**(base | overrides))


def grid_of(config, freq="h"):
    return pd.date_range(config.start, config.end, freq=freq, inclusive="left")


def panel(config, assets=3, freq="h"):
    grid = grid_of(config, freq)
    rng = np.random.default_rng(42)
    x = pd.DataFrame(
        rng.normal(size=(len(grid), assets)), index=grid, columns=[f"A{i}" for i in range(assets)]
    )
    y = 0.2 * x + pd.DataFrame(rng.normal(size=x.shape), index=grid, columns=x.columns)
    return x, y


def ts(x, labels, config, grid=None, freq="h"):
    grid = x.index if grid is None else grid
    return evaluate_time_series(
        x, labels, config, grid, pd.Timestamp(config.start), pd.Timestamp(config.end)
    )


def test_common_signal_can_predict_time_series_without_cross_section():
    config = make_config()
    grid = grid_of(config)
    signal = np.sin(np.arange(len(grid)) / 3)
    close = 100 * np.cumprod(np.r_[1, 1 + signal[:-1] * 0.01])
    scores = pd.DataFrame({asset: signal for asset in "ABC"}, index=grid)
    prices = pd.DataFrame({asset: close for asset in "ABC"}, index=grid)
    result = evaluate(scores, prices, config)
    assert result.periods.spearman.isna().all()
    assert result.time_series.assets.ic.to_numpy() == pytest.approx(1)
    assert result.time_series.assets.ci95_lower.to_numpy() == pytest.approx(1)
    assert result.time_series.summary.n_assets.tolist() == [3, 3]


def test_static_asset_scores_predict_cross_section_but_not_time_series():
    config = make_config()
    grid = grid_of(config)
    prices = pd.DataFrame(
        {a: 100 * (1 + k / 100) ** np.arange(len(grid)) for k, a in enumerate("ABC", 1)},
        index=grid,
    )
    scores = pd.DataFrame(np.tile([1.0, 2.0, 3.0], (len(grid), 1)), index=grid, columns=list("ABC"))
    result = evaluate(scores, prices, config)
    assert result.periods.spearman.dropna().to_numpy() == pytest.approx(1)
    assert result.time_series.assets.ic.isna().all()
    assert set(result.time_series.assets.status) == {"constant_signal"}


def test_gaps_lower_coverage_and_remain_in_expected_grid():
    config = make_config()
    x, y = panel(config, 1)
    x.iloc[10:40] = np.nan
    result = ts(x.drop(x.index[50:55]), {1: y}, config, grid=x.index)
    asset = result.assets.iloc[0]
    assert asset.n_expected == 95
    assert asset.n_pairs == 60
    assert asset.pair_coverage == pytest.approx(60 / 95)
    assert asset.status == "low_coverage"
    assert np.isnan(asset.ic)


def test_month_boundaries_exclude_delayed_labels_and_partial_months():
    config = make_config(
        start="2026-01-15T00:00:00Z",
        end="2026-03-10T00:00:00Z",
        delay=2,
        time_series=dict(min_pairs=5, min_horizons=1, bootstrap_samples=0),
    )
    x, y = panel(config, 1)
    result = ts(x, {1: y}, config)
    months = result.monthly.query("method == 'spearman'")
    assert months.status.tolist() == ["partial_window", "valid", "partial_window"]
    february = months.iloc[1]
    assert february.n_pairs == 28 * 24 - 3
    assert february.boundary_excluded == 3
    assert february.last_pair == pd.Timestamp("2026-02-28T20:00:00Z")
    # Huge returns at boundary-excluded timestamps cannot affect the monthly IC.
    y.loc["2026-02-28T21:00:00Z":"2026-02-28T23:00:00Z"] = 1e12
    changed = ts(x, {1: y}, config)
    assert changed.monthly.iloc[2].ic == pytest.approx(february.ic)
    assert result.assets.valid_months.tolist() == [1, 1]


def test_rolling_windows_do_not_use_unmatured_labels():
    config = make_config(delay=2)
    x, y = panel(config, 1)
    original = ts(x, {1: y}, config)
    cutoff = pd.Timestamp("2026-01-03T00:00:00Z")
    y.loc[cutoff - pd.Timedelta(hours=3) :] = -1e9
    changed = ts(x, {1: y}, config)
    before = pd.to_datetime(original.rolling.window_end) <= cutoff
    pd.testing.assert_frame_equal(original.rolling.loc[before], changed.rolling.loc[before])
    valid = original.rolling.query("status == 'valid'")
    assert valid.n_expected.tolist() == [21] * len(valid)
    assert (valid.last_pair < valid.window_end - pd.Timedelta(hours=3)).all()


@pytest.mark.parametrize("step", ["1D", "1 days", "0 days 12:00:00", "1W"])
def test_rolling_endpoints_step_from_start_through_end(step):
    config = make_config(
        end="2026-01-15T00:00:00Z",
        time_series=dict(
            min_pairs=5, min_horizons=1, bootstrap_samples=0, rolling_window="1D", rolling_step=step
        ),
    )
    x, y = panel(config, 1)
    rolling = ts(x, {1: y}, config).rolling
    start, end, duration = pd.Timestamp(config.start), pd.Timestamp(config.end), pd.Timedelta(step)
    count = (end - start) // duration
    expected = [start + k * duration for k in range(1, count + 1)]
    assert pd.DatetimeIndex(rolling.window_end.unique()).tolist() == expected
    assert (rolling.n_expected > 0).all()
    # Every step divides the 14-day period, so the final window ends exactly at the boundary.
    assert set(rolling.loc[rolling.window_end == end, "status"]) == {"valid"}


def test_step_longer_than_the_period_leaves_an_empty_rolling_table_with_columns():
    config = make_config(
        time_series=dict(
            min_pairs=5,
            min_horizons=1,
            bootstrap_samples=0,
            rolling_window="1D",
            rolling_step="30D",
        )
    )
    x, y = panel(config, 2)
    rolling = ts(x, {1: y}, config).rolling
    assert rolling.empty and "ic" in rolling.columns and "window_end" in rolling.columns


def test_monthly_ir_requires_months_and_uses_sample_std():
    months = pd.Series([0.2, 0.4, -0.1, 0.3, 0.1, 0.5, np.nan])
    result = monthly_statistics(months, 6)
    assert result["monthly_ic_ir"] == pytest.approx(months.mean() / months.std(ddof=1))
    assert result["valid_months"] == 6 and result["skipped_months"] == 1
    assert result["monthly_ir_status"] == "preliminary"
    assert np.isnan(monthly_statistics(months, 7)["monthly_ic_ir"])
    assert monthly_statistics(months, 7)["monthly_ir_status"] == "insufficient_months"
    constant = monthly_statistics(pd.Series([1.0] * 8), 6)
    assert np.isnan(constant["monthly_ic_ir"]) and constant["monthly_ir_status"] == "constant_ic"
    twelve = monthly_statistics(pd.Series(np.linspace(-0.1, 0.3, 12)), 6)
    assert twelve["monthly_ir_status"] == "available"


def test_bootstrap_is_reproducible_and_preserves_shared_asset_shocks():
    config = make_config()
    x, y = panel(config, 1)
    # Perfectly dependent assets should not gain precision by being counted twice.
    x["A1"], y["A1"] = x.A0, y.A0
    grid = x.index
    assets = window_table(
        x, y, config, 1, grid[0], pd.Timestamp(config.end), label_endpoints(grid, 1)
    )
    first, summary = bootstrap_intervals(x, y, assets, config, 1)
    second, summary2 = bootstrap_intervals(x, y, assets, config, 1)
    assert first == second and summary == summary2
    for method in ("spearman", "pearson"):
        assert first[method, "A0"] == first[method, "A1"]
        assert summary[method]["ci95_lower"] == pytest.approx(first[method, "A0"]["ci95_lower"])
        assert summary[method]["ci95_upper"] == pytest.approx(first[method, "A0"]["ci95_upper"])
        assert summary[method]["bootstrap_valid"] == 100
    other_seed = config.model_copy(
        update={"time_series": config.time_series.model_copy(update={"seed": 1})}
    )
    assert bootstrap_intervals(x, y, assets, other_seed, 1)[1] != summary
    long_blocks = config.model_copy(
        update={"time_series": config.time_series.model_copy(update={"block_bars": 30})}
    )
    _, summary = bootstrap_intervals(x, y, assets, long_blocks, 1)
    assert summary["spearman"]["bootstrap_status"] == "too_few_blocks"


def test_bootstrap_can_be_disabled_and_reports_why_intervals_are_missing():
    config = make_config(
        time_series=dict(min_pairs=5, min_horizons=1, bootstrap_samples=0, rolling_window="1D")
    )
    x, y = panel(config, 2)
    result = ts(x, {1: y}, config)
    assert set(result.assets.bootstrap_status) == {"disabled"}
    assert result.assets.ci95_lower.isna().all()
    assert set(result.summary.bootstrap_status) == {"disabled"}


def test_bootstrap_without_eligible_assets_is_reported():
    config = make_config()
    x, y = panel(config, 2)
    x[:] = 1.0
    result = ts(x, {1: y}, config)
    assert set(result.summary.bootstrap_status) == {"no_eligible_assets"}


def test_six_complete_months_compute_asset_and_universe_ir():
    config = make_config(
        end="2026-07-01T00:00:00Z",
        time_series=dict(min_pairs=5, min_horizons=1, bootstrap_samples=0),
    )
    x, _ = panel(config, 2, freq="D")
    signs = pd.Series([1.0, -1.0, 1.0, -1.0, 1.0, 1.0])
    y = x.mul([signs.iloc[t.month - 1] for t in x.index], axis=0)
    result = ts(x, {1: y}, config)
    expected = signs.mean() / signs.std(ddof=1)
    assert result.assets.valid_months.tolist() == [6] * 4
    assert result.assets.monthly_ic_ir.to_numpy() == pytest.approx(expected)
    assert result.summary.universe_monthly_ic_ir.to_numpy() == pytest.approx(expected)
    assert result.assets.monthly_ir_status.tolist() == ["preliminary"] * 4


def test_short_windows_are_reported_with_their_reason():
    config = make_config(
        time_series=dict(min_pairs=5, min_horizons=200, bootstrap_samples=0, rolling_window="1D")
    )
    x, y = panel(config, 2)
    assert set(ts(x, {1: y}, config).assets.status) == {"short_window"}


def test_tables_are_exposed_by_name():
    config = make_config()
    x, y = panel(config, 2)
    result = ts(x, {1: y}, config)
    assert set(result.tables()) == {"assets", "monthly", "rolling", "summary", "quantiles"}
    assert result.tables()["assets"] is result.assets


def test_cross_sectional_mode_does_not_compute_time_series(monkeypatch):
    config = make_config(mode="cross_sectional")
    x, y = panel(config, 4)
    prices = 100 * np.cumprod(1 + 0.01 * y, axis=0)
    monkeypatch.setattr(
        "alphatonic.evaluation.evaluate_time_series",
        lambda *args: pytest.fail("time-series evaluation is disabled"),
    )
    assert evaluate(x, prices, config).time_series is None
