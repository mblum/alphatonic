import pandas as pd
import pytest
from pydantic import ValidationError

from alphatonic import EvaluationConfig, PersistenceOptions, ReportOptions, TimeSeriesOptions


@pytest.mark.parametrize(
    "model,kwargs",
    [(EvaluationConfig, {"horizons": x}) for x in [(), (0,), (-1,), (True,), (1, 1)]]
    + [
        (EvaluationConfig, {key: value})
        for key, value in [
            ("min_assets", 2),
            ("delay", -1),
            ("quantiles", 1),
            ("hac_lags", -1),
            ("target", "bad"),
            ("vol_span", 1),
            ("vol_min_bars", 1),
            ("start", "NaT"),
            ("end", "NaT"),
        ]
    ]
    + [(PersistenceOptions, {"lags": x}) for x in [(), (0,), (True,), (1, 1)]]
    + [
        (TimeSeriesOptions, {key: value})
        for key, value in [
            ("min_pairs", 2),
            ("min_coverage", 0),
            ("min_coverage", 1.01),
            ("min_horizons", 0),
            ("min_months", 1),
            ("bootstrap_samples", 1),
            ("bootstrap_samples", 99),
            ("seed", -1),
            ("block_bars", True),
            ("target", "bad"),
        ]
    ],
)
def test_invalid_option_rejected(model, kwargs):
    with pytest.raises(ValidationError):
        model(**kwargs)


@pytest.mark.parametrize(
    "model", [EvaluationConfig, PersistenceOptions, ReportOptions, TimeSeriesOptions]
)
def test_options_forbid_extra_and_mutation(model):
    with pytest.raises(ValidationError):
        model(unknown=1)
    value = model()
    key = next(iter(model.model_fields))
    with pytest.raises(ValidationError):
        setattr(value, key, getattr(value, key))


@pytest.mark.parametrize("duration", ["0D", "-1h", "NaT", "1ME", "bad"])
def test_nonpositive_or_nonfixed_durations_rejected(duration):
    with pytest.raises(ValidationError):
        ReportOptions(rolling_window=duration)
    with pytest.raises(ValidationError):
        TimeSeriesOptions(rolling_step=duration)


def test_coercion_utc_window_and_presets():
    assert EvaluationConfig(horizons=["3"]).horizons == (3,)
    assert EvaluationConfig(start="2024-01-01T01:00+01:00").start == pd.Timestamp(
        "2024-01-01", tz="UTC"
    )
    with pytest.raises(ValidationError, match="after start"):
        EvaluationConfig(start="2024-01-01", end="2024-01-01")
    for samples in [0, 100]:
        assert TimeSeriesOptions(bootstrap_samples=samples).bootstrap_samples == samples
    threshold = pd.Timedelta("30D") / 125
    for delta, expected in [(-1, 100), (0, 100), (1, 15)]:
        assert (
            TimeSeriesOptions.for_bars(threshold + pd.Timedelta(delta, "ns")).min_pairs == expected
        )
    assert TimeSeriesOptions.for_bars("1D", min_pairs=77).min_pairs == 77
