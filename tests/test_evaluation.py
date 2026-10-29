import json
from contextlib import contextmanager

import numpy as np
import pandas as pd
import pytest
from pydantic import ValidationError

from alphatonic import Evaluation, EvaluationConfig, evaluate
from conftest import perfect_market, regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 100, "rolling_window": "5D"}
FAST_RETURN = FAST | {"target": "return"}


@pytest.fixture
def result():
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 20, seed=11)
    return evaluate(factor, prices, horizons=[1, 4], time_series=FAST)


def test_options_come_as_keywords_or_as_a_config_but_not_both():
    factor, prices = regular_panel(n_bars=60, freq="D")
    from_keywords = evaluate(factor, prices, horizons=[2], time_series={"bootstrap_samples": 0})
    from_config = evaluate(
        factor, prices, EvaluationConfig(horizons=[2], time_series={"bootstrap_samples": 0})
    )
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
    assert text.startswith("Evaluation(horizons=[1, 4]")
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
    assert {"ts.h4.cosine.mean", "ts.h4.cosine.mean_timing", "ts.h4.cosine.mean_static"} <= set(
        metrics
    )
    assert "ts.h4.spearman.mean_timing" not in metrics
    assert "cs.h4.cosine.mean" not in metrics
    assert not any("status" in name or "method" in name for name in metrics)
    # Undefined statistics are omitted rather than reported as zero.
    flat = evaluate(*perfect_market(), horizons=[1], time_series={"bootstrap_samples": 0})
    assert "cs.h1.spearman.hac_se" not in flat.metrics()


def test_to_dict_holds_every_table_as_plain_json(result):
    document = result.to_dict()

    json.dumps(document, allow_nan=False)
    assert (document["format"], document["format_version"]) == ("alphatonic.evaluation", 1)
    assert EvaluationConfig.model_validate(document["config"]) == result.config
    assert document["start"] == "2026-01-01T00:00:00+00:00"
    assert document["end"] == "2026-01-21T00:00:00+00:00"
    assert document["bar_seconds"] == 3600
    assert document["metrics"] == result.metrics()
    analyses = {
        "cross_section": {
            "summary": result.summary,
            "periods": result.periods,
            "quantiles": result.quantiles,
        },
        "time_series": result.time_series.tables(),
        "persistence": result.persistence.tables(),
    }
    for analysis, tables in analyses.items():
        assert list(document[analysis]) == list(tables)
        for name, table in tables.items():
            stored = document[analysis][name]
            assert list(stored) == list(table.columns), (analysis, name)
            # Rebuilding the table gives back its values, with null where they are missing.
            rebuilt = pd.DataFrame(stored).reindex(columns=table.columns)
            for column in table:
                if pd.api.types.is_datetime64_any_dtype(table[column]):
                    stamps = pd.to_datetime(rebuilt[column], utc=True, format="ISO8601")
                    rebuilt[column] = stamps.dt.as_unit(table[column].dt.unit)
                elif pd.api.types.is_float_dtype(table[column]):
                    rebuilt[column] = rebuilt[column].astype(float)
            pd.testing.assert_frame_equal(
                rebuilt, table.reset_index(drop=True), check_dtype=False, obj=name
            )


def test_to_dict_marks_absent_analyses_as_null(result):
    result.time_series = None
    result.persistence = None

    document = result.to_dict()

    assert document["time_series"] is None and document["persistence"] is None
    assert document["cross_section"]["periods"]["spearman"]


def test_disabling_bootstrap_keeps_both_analyses(result):
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 20, seed=11)
    fast = evaluate(factor, prices, horizons=[1, 4], time_series=FAST | {"bootstrap_samples": 0})
    pd.testing.assert_frame_equal(fast.summary, result.summary)
    pd.testing.assert_series_equal(fast.time_series.assets.ic, result.time_series.assets.ic)
    assert fast.time_series.summary.ci95_lower.isna().all()
    assert fast.time_series.summary.bootstrap_status.eq("disabled").all()
    assert {"cs.h1.spearman.mean", "ts.h1.spearman.mean"} <= fast.metrics().keys()


def test_a_single_asset_is_a_time_series_problem():
    factor, prices = regular_panel(n_assets=1, n_bars=24 * 20, seed=1)
    result = evaluate(factor, prices, horizons=[1], time_series=FAST)
    assert set(result.periods.status) == {"insufficient_assets"}
    assert result.time_series.summary.n_assets.tolist() == [1, 1, 1]
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
    result = evaluate(factor, prices, horizons=[1], time_series={"bootstrap_samples": 0})
    assert isinstance(result, Evaluation) and result.time_series is not None


def test_time_series_targets_are_returns_over_their_ex_ante_volatility():
    from alphatonic.inputs import prepare
    from alphatonic.returns import scale_by_volatility
    from alphatonic.time_series import evaluate_time_series

    factor, prices = regular_panel(n_assets=5, n_bars=24 * 20, seed=12)
    config = EvaluationConfig(horizons=[1, 3], time_series=FAST)
    result = evaluate(factor, prices, config)
    assert result.volatility is not None
    panel = prepare(factor, prices, config)
    targets = {
        h: scale_by_volatility(label, result.volatility, h)
        for h, label in result.forward_returns.items()
    }
    expected = evaluate_time_series(
        panel.factor, targets, config, panel.factor.index, panel.start, panel.end
    )
    for name, table in expected.tables().items():
        pd.testing.assert_frame_equal(result.time_series.tables()[name], table)
    raw = evaluate(factor, prices, horizons=[1, 3], time_series=FAST_RETURN)
    assert raw.volatility is None
    assert not np.allclose(raw.time_series.assets.ic, result.time_series.assets.ic, equal_nan=True)


def test_cross_sectional_target_can_be_risk_adjusted():
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 10, seed=13)
    raw = evaluate(factor, prices, horizons=[1], time_series=FAST_RETURN)
    risk = evaluate(factor, prices, horizons=[1], time_series=FAST_RETURN, target="vol_scaled")
    assert raw.volatility is None and risk.volatility is not None
    # The first bars wait for a volatility estimate, so they lose their pairs.
    assert risk.periods.n_pairs.iloc[:20].eq(0).all()
    assert risk.summary.n_periods.iloc[0] < raw.summary.n_periods.iloc[0]
    assert risk.summary["mean"].iloc[0] != pytest.approx(raw.summary["mean"].iloc[0])


def test_prices_before_the_window_warm_up_the_volatility_only():
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 25, seed=14)
    start = prices.index[24 * 5]
    options = {"horizons": [1], "start": start, "time_series": FAST}
    result = evaluate(factor, prices, **options)
    assert result.volatility.iloc[0].notna().all()
    calm = prices.copy()
    calm.loc[: start - pd.Timedelta(hours=1)] = calm.loc[start].to_numpy()
    changed = evaluate(factor, calm, **options)
    # Raw cross-sectional labels never read earlier prices; the volatility warm-up does.
    pd.testing.assert_frame_equal(result.periods, changed.periods)
    assert changed.volatility.iloc[0].isna().all()
    assert not result.time_series.assets.n_pairs.equals(changed.time_series.assets.n_pairs)
