"""Validated options for an evaluation and for its tearsheet."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Annotated, Any, Literal, Self

import pandas as pd
from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator, model_validator

Target = Literal["return", "vol_scaled"]
"""What scores are correlated with: the forward return, or the forward return divided by the
asset's ex-ante volatility over the horizon."""

METHODS = ("spearman", "pearson")
"""Correlation methods of the cross-sectional evaluation."""

TS_METHODS = ("spearman", "pearson", "cosine")
"""Correlation methods of the time-series evaluation. `cosine` is the uncentred correlation."""


def _reject_bool(value: Any) -> Any:
    # Lax ints accept strings such as "3" but would also turn True into 1.
    if isinstance(value, bool):
        raise ValueError("expected an integer, not a boolean")
    return value


PositiveInt = Annotated[int, Field(gt=0), BeforeValidator(_reject_bool)]

_RELAXED_WINDOWS: dict[str, Any] = {
    "min_pairs": 15,
    "min_horizons": 3,
    "rolling_window": "90D",
    "rolling_step": "5D",
}
"""Time-series windows for bars too long for the defaults, such as 12-hour or daily bars."""


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

    target: Target = "vol_scaled"
    """Label of the time-series IC: `vol_scaled` divides each forward return by the asset's
    ex-ante volatility over the horizon, so periods count by risk rather than by size; `return`
    uses the forward return as it is."""

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

    @classmethod
    def for_bars(cls, bar: str | timedelta, **overrides: Any) -> Self:
        """Return options whose windows suit bars of length `bar`, with `overrides` applied.

        The defaults are kept while their 30-day rolling window holds enough bars for 100 pairs
        at 80% coverage: bars of 5 hours 45 minutes or shorter. Longer bars, such as 12-hour or
        daily ones, get relaxed windows: 15 pairs, 3 horizons, and a 90-day rolling window moved
        in 5-day steps. Relaxed windows buy availability, not accuracy: a monthly IC from 15
        pairs is noisy. With weekly or longer bars even these windows are mostly too short; rely
        on the full-period IC and its bootstrap interval.

        Args:
            bar: Spacing of the price table's rows, such as `"1h"`, `"1D"` or a `timedelta`.
            **overrides: Options that replace the preset's values, such as `bootstrap_samples`.

        Returns:
            Ordinary `TimeSeriesOptions`, saved with an evaluation like any others.

        Raises:
            ValueError: If `bar` is not a positive fixed duration, or an override is invalid.
        """
        duration = pd.Timedelta(_duration(bar))
        defaults = cls.model_fields
        window = pd.Timedelta(defaults["rolling_window"].default)
        needed = defaults["min_pairs"].default / defaults["min_coverage"].default
        preset = {} if window / duration >= needed else _RELAXED_WINDOWS
        return cls(**{**preset, **overrides})


class PersistenceOptions(BaseModel):
    """Signal diagnostics on the original bar grid, independent of return horizons."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    lags: Annotated[tuple[PositiveInt, ...], Field(min_length=1)] = (1, 5, 10)
    """Endpoint comparison distances in bars; never interpreted as holding periods."""

    min_pairs: int = Field(default=2, ge=1)
    """Valid endpoint pairs required for each asset's descriptive statistics."""

    @field_validator("lags")
    @classmethod
    def _unique_lags(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if len(set(value)) != len(value):
            raise ValueError("lags must be unique")
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
    """What to evaluate: horizons, eligibility rules and the evaluation window.

    Every field has a default, so `EvaluationConfig()` is a valid configuration. The object is
    immutable; use `model_copy(update=...)` to derive a variant.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    horizons: Annotated[tuple[PositiveInt, ...], Field(min_length=1)] = (1, 5, 10)
    """Forward-return horizons in bars (rows of the price table)."""

    min_assets: int = Field(default=5, ge=3)
    """Finite score/return pairs a timestamp needs for a cross-sectional IC."""

    delay: int = Field(default=0, ge=0)
    """Extra bars between the observation and the start of the return it is scored against."""

    quantiles: int = Field(default=5, ge=2)
    """Number of score buckets in the quantile response tables."""

    hac_lags: int | None = Field(default=None, ge=0)
    """Newey-West lags for the cross-sectional mean IC. At least `horizon - 1` are always used.
    Default: `floor(4 * (n / 100) ** (2 / 9))`."""

    target: Target = "return"
    """Label of the cross-sectional IC: the forward `return`, or `vol_scaled`, the forward return
    divided by the asset's ex-ante volatility over the horizon (a risk-adjusted IC). The
    time-series evaluation has its own `time_series.target`."""

    vol_span: int = Field(default=60, ge=2)
    """Span, in bars, of the exponentially weighted volatility behind `vol_scaled` targets."""

    vol_min_bars: int = Field(default=20, ge=2)
    """One-bar returns the volatility estimate needs before it is used."""

    start: datetime | None = None
    """First evaluation timestamp (inclusive, UTC). Default: the first timestamp with a score."""

    end: datetime | None = None
    """End of the evaluation window (exclusive, UTC). Prices at or after it are ignored, and a
    label must end before it. Default: one bar after the last price."""

    persistence: PersistenceOptions = Field(default_factory=PersistenceOptions)
    """Signal persistence diagnostics; computed without future-return labels."""

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
