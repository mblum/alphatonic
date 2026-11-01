import pandas as pd
import pytest
from pydantic import ValidationError

from alphatonic import EvaluationConfig, PersistenceOptions, ReportOptions, TimeSeriesOptions
from alphatonic.config import parse_duration

DAY = 86_400 * 10**9
HOUR = 3_600 * 10**9


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


@pytest.mark.parametrize(
    ("text", "nanoseconds"),
    [
        ("7D", 7 * DAY),
        ("1W", 7 * DAY),
        ("12h", 12 * HOUR),
        ("1.5h", 3 * HOUR // 2),
        ("90min", 90 * 60 * 10**9),
        ("250ms", 250 * 10**6),
        ("1 days", DAY),
        ("1 days 00:00:00", DAY),
        ("00:30:00", HOUR // 2),
        ("-1h", -HOUR),
        ("-1 days +23:00:00", -HOUR),
        ("P1D", DAY),
    ],
)
def test_duration_text_is_read_to_the_nanosecond(text, nanoseconds):
    # Hand-written values: the grammar users may write in rolling_window, rolling_step and
    # for_bars must not narrow when the parser changes.
    assert parse_duration(text) == pd.Timedelta(nanoseconds, "ns")


@pytest.mark.parametrize("text", ["NaT", "nat", ""])
def test_missing_duration_text_is_nat(text):
    assert pd.isna(parse_duration(text))


@pytest.mark.parametrize("text", ["bad", "1ME", " ", "2 weeks"])
def test_malformed_duration_text_raises(text):
    with pytest.raises(ValueError):
        parse_duration(text)


def test_accepted_spellings_validate_and_are_kept_as_written():
    for text in ["1 days", "00:30:00", "P1D", "90min"]:
        assert ReportOptions(rolling_window=text).rolling_window == text
        assert TimeSeriesOptions(rolling_step=text).rolling_step == text
    # Durations given as objects are stored as text that reads back to the same length.
    stored = TimeSeriesOptions(rolling_window=pd.Timedelta(12, "h")).rolling_window
    assert parse_duration(stored) == pd.Timedelta(12 * HOUR, "ns")


def test_coercion_utc_window_and_presets():
    assert EvaluationConfig(horizons=["3"]).horizons == (3,)
    assert EvaluationConfig(start="2024-01-01T01:00+01:00").start == pd.Timestamp(
        "2024-01-01", tz="UTC"
    )
    with pytest.raises(ValidationError, match="after start"):
        EvaluationConfig(start="2024-01-01", end="2024-01-01")
    for samples in [0, 100]:
        assert TimeSeriesOptions(bootstrap_samples=samples).bootstrap_samples == samples
    threshold = pd.Timedelta(30, "D") / 125
    for delta, expected in [(-1, 100), (0, 100), (1, 15)]:
        assert (
            TimeSeriesOptions.for_bars(threshold + pd.Timedelta(delta, "ns")).min_pairs == expected
        )
    assert TimeSeriesOptions.for_bars("1D", min_pairs=77).min_pairs == 77
