"""Predeclared null regimes; R=2000 gives MC SE .0049 at size .05.

Three gating regimes use a Bonferroni-adjusted 99% binomial interval around .05.
The IID cosine contribution experiment has exact t inference under Gaussianity.
The AR(1) HAC experiment allows at most .03 excess rejection at n=512.
Unavailability is checked separately and is required to be zero in these regimes.
"""

import numpy as np
import pandas as pd
import pytest
from scipy.stats import binom

from alphatonic.stats import ewc_long_run_variance, summarize_ic, t_p_value


@pytest.mark.statistical
@pytest.mark.parametrize("rho", [0, 0.5])
def test_newey_west_null_rejection_predeclared_bound(rho, record_property):
    repetitions = 2000
    rejected = 0
    unavailable = 0
    for rep in range(repetitions):
        rng = np.random.default_rng(np.random.SeedSequence([1093, int(rho * 100), rep]))
        noise = rng.normal(size=612)
        values = np.zeros(612)
        for i in range(1, 612):
            values[i] = rho * values[i - 1] + noise[i]
        result = summarize_ic(pd.Series(values[100:]), 16)
        unavailable += "hac_p_value" not in result
        rejected += result.get("hac_p_value", 1) < 0.05
    record_property("repetitions", repetitions)
    record_property("rejections", rejected)
    record_property("unavailable", unavailable)
    record_property("unavailable_fraction", unavailable / repetitions)
    assert unavailable == 0, {"unavailable": unavailable, "denominator": repetitions}
    # A one-sided family-adjusted binomial bound at size .08.
    assert rejected <= binom.ppf(1 - 0.01 / 3, repetitions, 0.08), {
        "rejected": rejected,
        "denominator": repetitions,
        "rho": rho,
    }


@pytest.mark.statistical
def test_ewc_gaussian_null_exact_t_size(record_property):
    rng = np.random.default_rng(91203)
    values = rng.normal(size=(128, 2000))
    se = np.sqrt(ewc_long_run_variance(values, 8) / 128)
    p = t_p_value(values.mean(axis=0) / se, 8)
    assert np.isfinite(p).all()
    rejected = np.sum(p < 0.05)
    record_property("repetitions", 2000)
    record_property("rejections", int(rejected))
    record_property("unavailable", 0)
    lower, upper = binom.ppf([0.01 / 6, 1 - 0.01 / 6], 2000, 0.05)
    assert lower <= rejected <= upper, {"rejected": int(rejected), "denominator": 2000}


@pytest.mark.statistical
@pytest.mark.slow
def test_expanded_gaussian_ewc_coverage_and_power():
    rng = np.random.default_rng(7201)
    values = rng.normal(size=(512, 10000))
    se = np.sqrt(ewc_long_run_variance(values, 16) / 512)
    null = t_p_value(values.mean(axis=0) / se, 16)
    alternative = t_p_value((values.mean(axis=0) + 0.3) / se, 16)
    assert np.mean(null < 0.05) < 0.065
    assert np.mean(alternative < 0.05) > 0.95


@pytest.mark.statistical
@pytest.mark.slow
@pytest.mark.timeout(600)
def test_paired_block_bootstrap_null_coverage_predeclared(record_property):
    from alphatonic import EvaluationConfig
    from alphatonic.time_series import bootstrap_intervals, window_table

    # 2000 independent replications resolve size near .05 with MC SE about .0049.
    # Finite B=200 percentile intervals permit .04 excess noncoverage; availability
    # must exceed 99%. This does not validate arbitrary dependence or missingness.
    options = EvaluationConfig(
        horizons=(1,),
        time_series={
            "target": "return",
            "min_pairs": 3,
            "min_coverage": 0.5,
            "min_horizons": 1,
            "bootstrap_samples": 200,
            "block_bars": 3,
        },
    )
    rejected = 0
    unavailable = 0
    repetitions = 2000
    index = pd.date_range("2024-01-01", periods=60, tz="UTC")
    for replication in range(repetitions):
        rng = np.random.default_rng(np.random.SeedSequence([42709, replication]))
        x = pd.DataFrame(rng.normal(size=(60, 2)), index=index, columns=["a", "b"])
        common = rng.normal(size=60)
        y = pd.DataFrame(common[:, None] + rng.normal(size=(60, 2)), index=index, columns=x.columns)
        assets = window_table(x, y, options, 1, index[0], index[-1] + pd.Timedelta(1, "D"), index)
        config = options.model_copy(
            update={"time_series": options.time_series.model_copy(update={"seed": replication})}
        )
        _, aggregate = bootstrap_intervals(x, y, assets, config, 1)
        result = aggregate["spearman"]
        unavailable += result["bootstrap_status"] != "valid"
        rejected += result["ci95_lower"] > 0 or result["ci95_upper"] < 0
    record_property("repetitions", repetitions)
    record_property("rejections", rejected)
    record_property("unavailable", unavailable)
    record_property("unavailable_fraction", unavailable / repetitions)
    assert unavailable <= binom.ppf(0.995, repetitions, 0.01), {
        "unavailable": unavailable,
        "denominator": repetitions,
    }
    assert rejected <= binom.ppf(0.995, repetitions, 0.09), {
        "rejected": rejected,
        "denominator": repetitions,
    }
