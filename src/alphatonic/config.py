"""Validated options for an evaluation and for its tearsheet."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Self

import pandas as pd
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

Mode = Literal["both", "cross_sectional", "time_series"]
"""Which relationship to evaluate: across assets at each timestamp, within each asset over time,
or both."""

METHODS = ("spearman", "pearson")
"""Correlation methods reported for every statistic."""


def _reject_bool(value: Any) -> Any:
    # Lax ints accept strings such as "3" but would also turn True into 1.
    if isinstance(value, bool):
        raise ValueError("expected an integer, not a boolean")
    return value


PositiveInt = Annotated[int, Field(gt=0), BeforeValidator(_reject_bool)]


def _duration(value: Any) -> str:
    """Validate a fixed calendar duration such as `7D` or `12h` and return it as text."""
    text = value if isinstance(value, str) else str(pd.Timedelta(value))
    try:
        duration = pd.Timedelta(text)
    except ValueError as error:
        raise ValueError(f"{text!r} is not a duration such as 7D or 12h") from error
    if pd.isna(duration) or duration <= pd.Timedelta(0):
        raise ValueError("must be a positive fixed duration, such as 7D")
    return text


def _utc(value: Any) -> datetime | None:
    """Read a timestamp; naive values are UTC, aware values are converted to UTC."""
    if value is None:
        return None
    stamp = pd.Timestamp(value)
    if pd.isna(stamp):
        raise ValueError("expected a timestamp, not NaT")
    stamp = stamp.tz_localize("UTC") if stamp.tzinfo is None else stamp.tz_convert("UTC")
    return stamp.to_pydatetime()


class TimeSeriesOptions(BaseModel):
    """Eligibility rules, windows and bootstrap settings for time-series IC.

    The eligibility values are sample-size heuristics, not significance thresholds.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    min_pairs: int = Field(default=100, ge=3)
    """Finite score/return pairs a window needs before an asset's IC is computed."""

    min_coverage: float = Field(default=0.8, gt=0, le=1)
    """Fraction of a window's eligible bars that must contribute a finite pair."""

    min_horizons: PositiveInt = 20
    """Minimum window length, in multiples of the return horizon."""

    min_months: int = Field(default=6, ge=2)
    """Complete, valid calendar months needed for a monthly ICIR."""

    rolling_window: str = "30D"
    """Trailing window of the rolling TS IC, as a fixed duration such as `30D`."""

    rolling_step: str = "1D"
    """Spacing of rolling window endpoints, as a fixed duration."""

    bootstrap_samples: int = Field(default=1000, ge=0)
    """Circular block-bootstrap draws for confidence intervals; `0` disables them."""

    block_bars: PositiveInt | None = None
    """Bootstrap block length in bars. Default: `max(horizon, ceil(n ** (1/3)))`."""

    seed: int = Field(default=0, ge=0)
    """Seed of the bootstrap random number generator."""

    @field_validator("rolling_window", "rolling_step", mode="before")
    @classmethod
    def _validate_duration(cls, value: Any) -> str:
        return _duration(value)

    @field_validator("bootstrap_samples")
    @classmethod
    def _validate_samples(cls, value: int) -> int:
        if 0 < value < 100:
            raise ValueError("bootstrap_samples must be zero (disabled) or at least 100")
        return value


class ReportOptions(BaseModel):
    """Display options of the cross-sectional charts in a tearsheet."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    rolling_window: str = "7D"
    """Trailing window of the rolling mean of cross-sectional IC, as a fixed duration."""

    min_periods: PositiveInt = 3
    """Valid IC observations a rolling window needs to draw its mean."""

    @field_validator("rolling_window", mode="before")
    @classmethod
    def _validate_window(cls, value: Any) -> str:
        return _duration(value)


class EvaluationConfig(BaseModel):
    """What to evaluate: horizons, modes, eligibility rules and the evaluation window.

    Every field has a default, so `EvaluationConfig()` is a valid configuration. The object is
    immutable; use `model_copy(update=...)` to derive a variant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizons: Annotated[tuple[PositiveInt, ...], Field(min_length=1)] = (1, 5, 10)
    """Forward-return horizons in bars (rows of the price table)."""

    mode: Mode = "both"
    """`cross_sectional`, `time_series`, or `both`."""

    min_assets: int = Field(default=5, ge=3)
    """Finite score/return pairs a timestamp needs for a cross-sectional IC."""

    delay: int = Field(default=0, ge=0)
    """Extra bars between the observation and the start of the return it is scored against."""

    quantiles: int = Field(default=5, ge=2)
    """Number of score buckets in the quantile response tables."""

    hac_lags: int | None = Field(default=None, ge=0)
    """Newey-West lags for the cross-sectional mean IC. At least `horizon - 1` are always used.
    Default: `floor(4 * (n / 100) ** (2 / 9))`."""

    start: datetime | None = None
    """First evaluation timestamp (inclusive, UTC). Default: the first timestamp with a score."""

    end: datetime | None = None
    """End of the evaluation window (exclusive, UTC). Prices at or after it are ignored, and a
    label must end before it. Default: one bar after the last price."""

    time_series: TimeSeriesOptions = Field(default_factory=TimeSeriesOptions)
    """Options of the time-series evaluation."""

    @field_validator("start", "end", mode="before")
    @classmethod
    def _validate_bound(cls, value: Any) -> datetime | None:
        return _utc(value)

    @model_validator(mode="after")
    def _validate_window(self) -> Self:
        if self.start is not None and self.end is not None and self.end <= self.start:
            raise ValueError("end must be after start")
        if len(set(self.horizons)) != len(self.horizons):
            raise ValueError("horizons must be unique")
        return self
