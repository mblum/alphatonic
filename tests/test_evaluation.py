from contextlib import contextmanager

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from alphatonic import Evaluation, EvaluationConfig, evaluate
from conftest import perfect_market, regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 100, "rolling_window": "5D"}


@pytest.fixture
def result():
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 20, seed=11)
    return evaluate(factor, prices, horizons=[1, 4], time_series=FAST)


def test_options_come_as_keywords_or_as_a_config_but_not_both():
    factor, prices = regular_panel(n_bars=60, freq="D")
    from_keywords = evaluate(factor, prices, horizons=[2], mode="cross_sectional")
    from_config = evaluate(factor, prices, EvaluationConfig(horizons=[2], mode="cross_sectional"))
    pd.testing.assert_frame_equal(from_keywords.periods, from_config.periods)
    assert from_keywords.config == from_config.config
    with pytest.raises(TypeError, match="either a config or keyword options"):
        evaluate(factor, prices, EvaluationConfig(), horizons=[2])
    with pytest.raises(ValidationError):
        evaluate(factor, prices, horizons=[0])
    with pytest.raises(ValidationError):
        evaluate(factor, prices, horizon=[1])


def test_result_describes_the_window_and_grid(result):
    assert result.start == pd.Timestamp("2026-01-01", tz="UTC")
    assert result.end == pd.Timestamp("2026-01-21", tz="UTC")
    assert result.bar == pd.Timedelta(hours=1)
    assert set(result.forward_returns) == {1, 4}
    labels = result.forward_returns[4]
    assert labels.index.equals(pd.DatetimeIndex(result.periods.timestamp.unique()))
    assert labels.iloc[-4:].isna().all().all() and labels.iloc[:-4].notna().all().all()
    assert result.config.horizons == (1, 4)


def test_repr_does_not_print_tables(result):
    text = repr(result)
    assert text.startswith("Evaluation(mode='both', horizons=[1, 4]")
    assert "2026-01-01 00:00" in text and "\n" not in text


def test_ic_is_a_timestamp_by_horizon_table(result):
    table = result.ic()
    assert list(table.columns) == [1, 4]
    assert len(table) == 24 * 20 and table.index.is_monotonic_increasing
    assert (
        table[1].dropna().tolist()
        == result.periods.query("horizon == 1").spearman.dropna().tolist()
    )
    pearson = result.ic("pearson")
    assert not pearson.equals(table)
    with pytest.raises(ValueError, match="spearman"):
        result.ic("kendall")


def test_monthly_ic_counts_valid_periods(result):
    monthly = result.monthly_ic()
    assert monthly.index.names == ["horizon", "timestamp"]
    counts = monthly[("spearman", "count")].groupby("horizon").sum()
    assert counts.tolist() == result.summary.query("method == 'spearman'").n_periods.tolist()


def test_metrics_are_finite_scalars_with_documented_names(result):
    metrics = result.metrics()
    assert all(isinstance(v, float) and np.isfinite(v) for v in metrics.values())
    assert metrics["cs.h1.spearman.mean"] == pytest.approx(
        result.summary.query("horizon == 1 and method == 'spearman'")["mean"].iloc[0]
    )
    assert "cs.h4.pearson.hac_p_value" in metrics
    assert "ts.h4.spearman.mean" in metrics and "ts.h4.spearman.n_assets" in metrics
    assert not any("status" in name or "method" in name for name in metrics)
    # Undefined statistics are omitted rather than reported as zero.
    flat = evaluate(*perfect_market(), horizons=[1], time_series={"bootstrap_samples": 0})
    assert "cs.h1.spearman.hac_se" not in flat.metrics()


def test_metrics_follow_the_mode():
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 20, seed=2)
    cs = evaluate(factor, prices, horizons=[1], mode="cross_sectional").metrics()
    ts = evaluate(factor, prices, horizons=[1], mode="time_series", time_series=FAST).metrics()
    assert all(name.startswith("cs.") for name in cs)
    assert all(name.startswith("ts.") for name in ts) and ts


def test_a_single_asset_is_a_time_series_problem():
    factor, prices = regular_panel(n_assets=1, n_bars=24 * 20, seed=1)
    result = evaluate(factor, prices, horizons=[1], time_series=FAST)
    assert set(result.periods.status) == {"insufficient_assets"}
    assert result.time_series.summary.n_assets.tolist() == [1, 1]
    assert result.metrics()["ts.h1.spearman.n_assets"] == 1


def test_results_do_not_depend_on_the_datetime_resolution_of_the_index():
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 20, seed=8)
    reference = evaluate(factor, prices, horizons=[2], time_series=FAST)
    for unit in ("s", "ms", "us"):
        resampled = evaluate(
            factor.set_axis(factor.index.as_unit(unit)),
            prices.set_axis(prices.index.as_unit(unit)),
            horizons=[2],
            time_series=FAST,
        )
        pd.testing.assert_frame_equal(resampled.periods, reference.periods)
        pd.testing.assert_frame_equal(resampled.time_series.assets, reference.time_series.assets)
        pd.testing.assert_frame_equal(resampled.time_series.rolling, reference.time_series.rolling)


def test_evaluation_is_deterministic_and_the_seed_only_moves_bootstrap_intervals():
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 20, seed=9)
    a = evaluate(factor, prices, horizons=[1], time_series=FAST)
    b = evaluate(factor, prices, horizons=[1], time_series=FAST)
    c = evaluate(factor, prices, horizons=[1], time_series=FAST | {"seed": 5})
    pd.testing.assert_frame_equal(a.time_series.assets, b.time_series.assets)
    assert a.time_series.assets.ic.tolist() == c.time_series.assets.ic.tolist()
    assert a.time_series.assets.ci95_lower.tolist() != c.time_series.assets.ci95_lower.tolist()


def test_prices_after_the_window_cannot_leak_into_any_statistic():
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 30, seed=3)
    end = prices.index[24 * 20]
    before = evaluate(factor, prices, horizons=[4], end=end, time_series=FAST)
    shocked = prices.copy()
    shocked.loc[end:] *= 50
    after = evaluate(factor, shocked, horizons=[4], end=end, time_series=FAST)
    pd.testing.assert_frame_equal(before.periods, after.periods)
    for name, table in before.time_series.tables().items():
        pd.testing.assert_frame_equal(table, after.time_series.tables()[name])


def test_a_horizon_without_any_valid_ic_is_visible_in_every_table():
    factor, prices = regular_panel(n_assets=4, n_bars=60, freq="D")
    result = evaluate(factor, prices, horizons=[1, 500], min_assets=3, time_series=FAST)
    long = result.summary.query("horizon == 500")
    assert long.n_periods.eq(0).all() and long["mean"].isna().all()
    assert set(result.periods.query("horizon == 500").status) == {"insufficient_assets"}
    assert result.time_series.summary.query("horizon == 500").n_assets.eq(0).all()


@contextmanager
def recording(events):
    def factory(description, total=None):
        @contextmanager
        def task():
            events.append(("start", description, total))

            def advance(steps=1, *, description=None):
                events.append(("advance", steps, description))

            try:
                yield advance
            finally:
                events.append(("stop", description))

        return task()

    yield factory


def test_progress_is_reported_to_the_given_display():
    factor, prices = regular_panel(n_assets=4, n_bars=24 * 10)
    events = []
    with recording(events) as progress:
        evaluate(
            factor,
            prices,
            horizons=[1, 2],
            progress=progress,
            time_series=FAST,
        )
    starts = [e for e in events if e[0] == "start"]
    assert ("start", "Evaluating IC", 2) in starts
    assert ("start", "TS bootstrap · h1", 100) in starts and (
        "start",
        "TS bootstrap · h2",
        100,
    ) in starts
    assert sum(e[1] for e in events if e[0] == "advance" and e[2] is None) >= 2 + 200
    assert len([e for e in events if e[0] == "stop"]) == len(starts)


def test_evaluation_can_be_constructed_and_copied_by_users():
    factor, prices = regular_panel(n_bars=40, freq="D")
    result = evaluate(factor, prices, horizons=[1], mode="cross_sectional")
    assert isinstance(result, Evaluation) and result.time_series is None
