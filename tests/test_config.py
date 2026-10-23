from datetime import UTC, datetime, timedelta, timezone

import pandas as pd
import pytest
from pydantic import ValidationError

from alphatonic import EvaluationConfig, ReportOptions, TimeSeriesOptions


def test_defaults_are_a_valid_configuration():
    config = EvaluationConfig()
    assert config.horizons == (1, 5, 10)
    assert config.mode == "both"
    assert config.min_assets == 5 and config.delay == 0 and config.quantiles == 5
    assert config.start is None and config.end is None
    assert config.time_series == TimeSeriesOptions()


def test_configuration_is_immutable_and_derivable():
    config = EvaluationConfig(horizons=[2, 3])
    assert config.horizons == (2, 3)
    with pytest.raises(ValidationError):
        config.mode = "time_series"
    variant = config.model_copy(update={"mode": "time_series"})
    assert variant.mode == "time_series" and config.mode == "both"


def test_nested_options_accept_dicts_and_models():
    from_dict = EvaluationConfig(time_series={"bootstrap_samples": 0, "seed": 3})
    from_model = EvaluationConfig(time_series=TimeSeriesOptions(bootstrap_samples=0, seed=3))
    assert from_dict == from_model


@pytest.mark.parametrize(
    "value, expected",
    [
        ("2026-01-02", datetime(2026, 1, 2, tzinfo=UTC)),
        (datetime(2026, 1, 2), datetime(2026, 1, 2, tzinfo=UTC)),
        (pd.Timestamp("2026-01-02 09:00", tz="Europe/Berlin"), datetime(2026, 1, 2, 8, tzinfo=UTC)),
        (
            datetime(2026, 1, 2, 9, tzinfo=timezone(timedelta(hours=1))),
            datetime(2026, 1, 2, 8, tzinfo=UTC),
        ),
    ],
)
def test_window_bounds_are_read_as_utc(value, expected):
    config = EvaluationConfig(start=value)
    assert config.start == expected
    assert config.start.utcoffset() == timedelta(0)


@pytest.mark.parametrize(
    "options",
    [
        {"horizons": []},
        {"horizons": [0]},
        {"horizons": [-1]},
        {"horizons": [True]},
        {"horizons": [1, 1]},
        {"mode": "weekly"},
        {"min_assets": 2},
        {"delay": -1},
        {"quantiles": 1},
        {"hac_lags": -1},
        {"start": "2026-02-01", "end": "2026-01-01"},
        {"start": "2026-02-01", "end": "2026-02-01"},
        {"start": "not a date"},
        {"unknown_option": 1},
    ],
)
def test_invalid_configuration_is_rejected(options):
    with pytest.raises(ValueError):
        EvaluationConfig(**options)


@pytest.mark.parametrize(
    "options",
    [
        {"min_pairs": 2},
        {"min_coverage": 0},
        {"min_coverage": 1.1},
        {"min_months": 1},
        {"rolling_window": "0D"},
        {"rolling_window": "-1h"},
        {"rolling_step": "NaT"},
        {"rolling_step": "soon"},
        {"block_bars": 0},
        {"bootstrap_samples": 12},
        {"seed": -1},
        {"unknown": 1},
    ],
)
def test_invalid_time_series_options(options):
    with pytest.raises(ValueError):
        TimeSeriesOptions(**options)


def test_bootstrap_can_be_disabled_and_durations_accept_timedeltas():
    options = TimeSeriesOptions(bootstrap_samples=0, rolling_window=timedelta(days=14))
    assert options.bootstrap_samples == 0
    assert pd.Timedelta(options.rolling_window) == pd.Timedelta(days=14)


@pytest.mark.parametrize("window", ["0D", "-1h", "NaT", "invalid"])
def test_report_options_reject_invalid_windows(window):
    with pytest.raises(ValueError):
        ReportOptions(rolling_window=window)


def test_report_options_defaults_and_validation():
    assert ReportOptions().model_dump() == {"rolling_window": "7D", "min_periods": 3}
    with pytest.raises(ValueError):
        ReportOptions(min_periods=0)


def test_configuration_round_trips_through_json():
    config = EvaluationConfig(
        horizons=[1, 21],
        start="2026-01-01",
        end="2026-06-01",
        time_series={"bootstrap_samples": 200, "rolling_window": "14D"},
    )
    assert EvaluationConfig.model_validate_json(config.model_dump_json()) == config
