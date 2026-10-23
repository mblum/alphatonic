"""Validate and align the factor and price tables an evaluation reads."""

from __future__ import annotations

import warnings
from dataclasses import dataclass

import numpy as np
import pandas as pd

from alphatonic.config import EvaluationConfig


@dataclass(frozen=True)
class Panel:
    """Factor and prices aligned on the evaluation grid."""

    factor: pd.DataFrame
    """Scores, one row per bar of the window and one column per priced asset."""

    prices: pd.DataFrame
    """Prices on the same rows and columns."""

    start: pd.Timestamp
    """Inclusive start of the window (UTC)."""

    end: pd.Timestamp
    """Exclusive end of the window (UTC)."""

    bar: pd.Timedelta | None
    """Spacing of the grid if it is perfectly regular, otherwise `None`."""


def utc_index(index: pd.Index, name: str) -> pd.DatetimeIndex:
    """Return `index` as nanosecond UTC timestamps named `timestamp`, without a frequency.

    Naive timestamps are read as UTC.
    """
    if not isinstance(index, pd.DatetimeIndex):
        raise TypeError(
            f"{name} must be indexed by timestamps (a DatetimeIndex), not {type(index).__name__}"
        )
    if index.hasnans:
        raise ValueError(f"{name} has missing timestamps (NaT) in its index")
    index = index.tz_localize("UTC") if index.tz is None else index.tz_convert("UTC")
    return pd.DatetimeIndex(index.as_unit("ns"), freq=None, name="timestamp")


def _numeric(frame: pd.DataFrame, name: str) -> pd.DataFrame:
    try:
        return frame.astype(float)
    except (TypeError, ValueError) as error:
        raise ValueError(f"{name} must be numeric: {error}") from error


def clean_prices(prices: pd.DataFrame) -> pd.DataFrame:
    """Check a price table and return it with a sorted UTC index and float columns."""
    if not isinstance(prices, pd.DataFrame):
        raise TypeError(
            "prices must be a DataFrame with one row per bar and one column per asset, "
            f"not {type(prices).__name__}"
        )
    if prices.columns.nlevels != 1:
        raise ValueError(
            "prices must have one column level (the asset); select a field first, "
            "e.g. market['close']"
        )
    index = utc_index(prices.index, "prices")
    if prices.columns.has_duplicates:
        raise ValueError("prices has duplicate asset columns")
    if index.has_duplicates:
        raise ValueError("prices has duplicate timestamps; each bar needs exactly one row")
    if not index.is_monotonic_increasing:
        raise ValueError("prices must be sorted by time; call sort_index() first")
    frame = _numeric(prices, "prices").set_axis(index, axis=0)
    values = frame.to_numpy()
    if np.isinf(values).any():
        raise ValueError("prices must be finite; use NaN for a missing price")
    if (values <= 0).any():
        raise ValueError(
            "prices must be positive because returns are ratios; "
            "mask other values with NaN, e.g. prices.where(prices > 0)"
        )
    return frame


def clean_factor(factor: pd.DataFrame | pd.Series) -> pd.DataFrame:
    """Return scores as a wide table: a sorted UTC index, one column per asset, `NaN` for none.

    A `Series` with a two-level `(timestamp, asset)` index (the alphalens layout, in either level
    order) is unstacked. Infinities are treated as missing scores.
    """
    if isinstance(factor, pd.Series):
        index = factor.index
        if index.nlevels != 2:
            raise ValueError(
                "a factor Series needs a two-level (timestamp, asset) MultiIndex; "
                "pass a wide DataFrame (timestamps by assets) otherwise"
            )
        time_level = next(
            (
                level
                for level in (0, 1)
                if pd.api.types.is_datetime64_any_dtype(index.get_level_values(level))
            ),
            None,
        )
        if time_level is None:
            raise TypeError("neither level of the factor's MultiIndex holds timestamps")
        if index.has_duplicates:
            raise ValueError("factor has duplicate (timestamp, asset) entries")
        wide = _numeric(factor.to_frame("factor"), "factor")["factor"].unstack(level=1 - time_level)
        wide.columns.name = None
    elif isinstance(factor, pd.DataFrame):
        if factor.index.nlevels != 1 or factor.columns.nlevels != 1:
            raise ValueError(
                "a factor DataFrame must be wide: one index level (timestamps) and one column "
                "level (assets). Pass a (timestamp, asset) Series for long data"
            )
        wide = _numeric(factor, "factor")
    else:
        raise TypeError(
            f"factor must be a wide DataFrame or a (timestamp, asset) Series, not "
            f"{type(factor).__name__}"
        )
    index = utc_index(wide.index, "factor")
    if wide.columns.has_duplicates:
        raise ValueError("factor has duplicate asset columns")
    if index.has_duplicates:
        raise ValueError("factor has duplicate timestamps; each bar needs exactly one row")
    wide = wide.set_axis(index, axis=0).sort_index()
    return wide.where(np.isfinite(wide))


def prepare(
    factor: pd.DataFrame | pd.Series, prices: pd.DataFrame, config: EvaluationConfig
) -> Panel:
    """Align `factor` with `prices` on the evaluation window of `config`.

    The grid is the rows of `prices` inside `[start, end)`. Prices at or after `end` are dropped,
    so no label can end beyond the window, and factor rows outside the window are ignored.
    Assets without prices are dropped with a warning.

    Raises:
        ValueError: If a table is malformed, the factor has scores on timestamps without prices,
            or the window contains no bars.
    """
    prices = clean_prices(prices)
    wide = clean_factor(factor)
    unpriced = ~wide.columns.isin(prices.columns)
    if unpriced.any():
        names = ", ".join(map(str, wide.columns[unpriced][:5]))
        warnings.warn(
            f"{int(unpriced.sum())} factor assets have no prices and are ignored: {names}"
            + (", ..." if unpriced.sum() > 5 else ""),
            UserWarning,
            stacklevel=3,
        )
        wide = wide.loc[:, ~unpriced]
    if len(prices) < 2:
        raise ValueError("prices need at least two rows to define a horizon")

    if config.start is not None:
        start = pd.Timestamp(config.start)
    else:
        scored = wide.index[wide.notna().any(axis=1)]
        if not len(scored):
            raise ValueError("the factor has no finite scores for any priced asset")
        start = max(scored[0], prices.index[0])
    if config.end is not None:
        end = pd.Timestamp(config.end)
    else:
        end = prices.index[-1] + prices.index.to_series().diff().median()
    if end <= start:
        raise ValueError(f"the window is empty: start {start} is not before end {end}")
    start, end = start.as_unit("ns"), end.as_unit("ns")

    grid = prices.index[(prices.index >= start) & (prices.index < end)]
    if not len(grid):
        raise ValueError(f"prices have no rows in the window [{start}, {end})")
    in_window = wide.index[(wide.index >= start) & (wide.index < end)]
    stray = in_window[~in_window.isin(grid)]
    if len(stray) and wide.loc[stray].notna().any(axis=None):
        raise ValueError(
            f"the factor has scores at {int(wide.loc[stray].notna().any(axis=1).sum())} "
            f"timestamps that are not in prices, the first at {stray[0]}. Align both tables to "
            "the same bars, or narrow start and end."
        )
    steps = grid.to_series().diff().dropna()
    bar = steps.iloc[0] if len(steps) and steps.nunique() == 1 else None
    return Panel(
        factor=wide.reindex(index=grid, columns=prices.columns),
        prices=prices.loc[grid],
        start=start,
        end=end,
        bar=bar,
    )
