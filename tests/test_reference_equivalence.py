"""The vectorized implementations must compute what the original loops computed."""

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

import reference
from alphatonic.config import EvaluationConfig
from alphatonic.cross_section import cross_sectional_ic
from alphatonic.inputs import prepare
from alphatonic.returns import forward_returns
from alphatonic.time_series import evaluate_time_series
from conftest import regular_panel

CASES = [
    dict(seed=0, missing=0.0, ties=False, delay=0, quantiles=5),
    dict(seed=1, missing=0.08, ties=False, delay=0, quantiles=5),
    dict(seed=2, missing=0.05, ties=True, delay=2, quantiles=3),
    dict(seed=3, missing=0.2, ties=True, delay=1, quantiles=10),
    dict(seed=4, missing=0.0, ties=False, delay=0, quantiles=4),
]


TS_CASES = [
    dict(seed=0, missing=0.0, ties=False, delay=0, quantiles=5),
    dict(seed=5, missing=0.01, ties=False, delay=0, quantiles=5),
    dict(seed=6, missing=0.005, ties=True, delay=2, quantiles=3),
]


def run(case, n_bars=24 * 50):
    factor, prices = regular_panel(
        n_assets=7, n_bars=n_bars, seed=case["seed"], missing=case["missing"], ties=case["ties"]
    )
    config = EvaluationConfig(
        horizons=[4, 1, 12],
        min_assets=3,
        delay=case["delay"],
        quantiles=case["quantiles"],
        time_series={
            "min_pairs": 30,
            "min_horizons": 3,
            "bootstrap_samples": 100,
            "rolling_window": "5D",
            "rolling_step": "1D",
        },
    )
    panel = prepare(factor, prices, config)
    labels = {h: forward_returns(panel.prices, h, config.delay) for h in config.horizons}
    return panel, config, labels


def assert_same(actual, expected):
    assert_frame_equal(
        actual.reset_index(drop=True),
        expected.reset_index(drop=True),
        check_dtype=False,
        check_exact=False,
        rtol=1e-9,
        atol=1e-12,
    )


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"seed{c['seed']}")
def test_cross_section_matches_loop(case):
    panel, config, labels = run(case, n_bars=24 * 12)
    periods, summary, quantiles = cross_sectional_ic(panel.factor, labels, panel.prices, config)
    ref_periods, ref_summary, ref_quantiles = reference.cross_sectional(
        panel.factor, labels, panel.prices, config
    )
    assert_same(periods, ref_periods)
    assert_same(summary, ref_summary)
    assert_same(quantiles, ref_quantiles)


@pytest.mark.parametrize("case", TS_CASES, ids=lambda c: f"seed{c['seed']}")
def test_time_series_matches_loop(case):
    panel, config, labels = run(case)
    actual = evaluate_time_series(
        panel.factor, labels, config, panel.factor.index, panel.start, panel.end
    ).tables()
    expected = reference.time_series(
        panel.factor, labels, config, pd.Timedelta(hours=1), panel.start, panel.end
    )
    for name in actual:
        assert len(actual[name]) or name == "quantiles", name
        assert_same(actual[name], expected[name])
    assert len(actual["quantiles"])


def test_sparse_assets_and_constant_scores_match_loop():
    # Constant and fully missing assets hit every eligibility branch.
    case = TS_CASES[1]
    panel, config, labels = run(case, n_bars=24 * 40)
    factor = panel.factor.copy()
    factor["A0"] = 1.0
    factor.loc[:, "A1"] = np.nan
    factor.iloc[: len(factor) // 2, 2] = np.nan
    actual = evaluate_time_series(
        factor, labels, config, factor.index, panel.start, panel.end
    ).tables()
    expected = reference.time_series(
        factor, labels, config, pd.Timedelta(hours=1), panel.start, panel.end
    )
    for name in actual:
        assert_same(actual[name], expected[name])
    statuses = set(actual["assets"].status)
    assert {"constant_signal", "insufficient_pairs"} <= statuses


@pytest.mark.parametrize("case", TS_CASES, ids=lambda c: f"seed{c['seed']}")
def test_bootstrap_matches_resampling_the_rows(case):
    from alphatonic.returns import label_endpoints
    from alphatonic.time_series import bootstrap_intervals, window_table

    panel, config, labels = run(case, n_bars=24 * 20)
    grid = panel.factor.index
    for horizon in (1, 4):
        y = labels[horizon].reindex(grid)
        ends = label_endpoints(grid, horizon + config.delay)
        assets = window_table(panel.factor, y, config, horizon, panel.start, panel.end, ends)
        mature = np.asarray(ends < panel.end)
        x_m, y_m = panel.factor.loc[mature], y.loc[mature]
        fast = bootstrap_intervals(x_m, y_m, assets, config, horizon)
        slow = reference.bootstrap_intervals(x_m, y_m, assets, config, horizon)
        assert fast[0].keys() == slow[0].keys()
        for key, value in fast[0].items():
            assert value["bootstrap_status"] == slow[0][key]["bootstrap_status"]
            assert value["bootstrap_valid"] == slow[0][key]["bootstrap_valid"]
            for bound in ("ci95_lower", "ci95_upper"):
                np.testing.assert_allclose(value[bound], slow[0][key][bound], atol=1e-12)
        for method, value in fast[1].items():
            for name, expected in slow[1][method].items():
                if isinstance(expected, float):
                    np.testing.assert_allclose(value[name], expected, atol=1e-12)
                else:
                    assert value[name] == expected


@pytest.mark.parametrize("unit", ["s", "ms", "us"])
def test_cross_section_does_not_depend_on_the_index_resolution(unit):
    panel, config, labels = run(CASES[2], n_bars=24 * 6)
    coarse = panel.factor.copy()
    coarse.index = coarse.index.as_unit(unit)
    expected = cross_sectional_ic(panel.factor, labels, panel.prices, config)
    actual = cross_sectional_ic(coarse, labels, panel.prices, config)
    for table_a, table_b in zip(actual, expected, strict=True):
        assert_same(table_a, table_b)
    assert actual[0].timestamp.iloc[0] == panel.factor.index[0]
