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
    dict(seed=0, missing=0.0, ties=False, delay=0, quantiles=5, mode="both"),
    dict(seed=1, missing=0.08, ties=False, delay=0, quantiles=5, mode="both"),
    dict(seed=2, missing=0.05, ties=True, delay=2, quantiles=3, mode="both"),
    dict(seed=3, missing=0.2, ties=True, delay=1, quantiles=10, mode="cross_sectional"),
    dict(seed=4, missing=0.0, ties=False, delay=0, quantiles=4, mode="time_series"),
]


TS_CASES = [
    dict(seed=0, missing=0.0, ties=False, delay=0, quantiles=5, mode="both"),
    dict(seed=5, missing=0.01, ties=False, delay=0, quantiles=5, mode="both"),
    dict(seed=6, missing=0.005, ties=True, delay=2, quantiles=3, mode="both"),
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
        mode=case["mode"],
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


@pytest.mark.parametrize("case", CASES, ids=lambda c: f"seed{c['seed']}-{c['mode']}")
def test_cross_section_matches_loop(case):
    panel, config, labels = run(case)
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
