"""Forward-return labels on a bar grid."""

from __future__ import annotations

import numpy as np
import pandas as pd


def forward_returns(prices: pd.DataFrame, horizon: int, delay: int = 0) -> pd.DataFrame:
    """Compute exact-horizon simple returns, requiring an unbroken path of prices.

    For the bar at row `t`, the label is `prices[t + delay + horizon] / prices[t + delay] - 1`.
    Rows are bars, so `horizon` and `delay` count rows, not clock time. The label is missing
    unless every row from `t` through `t + delay + horizon` has a price, so a gap never turns an
    h-bar label into a longer return, and the last `delay + horizon` rows have no label.
    Non-finite returns, such as a jump from a vanishing price, are missing too.

    Args:
        prices: Prices with one row per bar and one column per asset. `NaN` marks a missing price.
        horizon: Number of bars the return spans.
        delay: Bars between the observation and the start of the return.

    Returns:
        A frame shaped like `prices` holding the forward return of each bar.
    """
    span = delay + horizon
    continuous = prices.notna().rolling(span + 1).sum().shift(-span).eq(span + 1)
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        returns = prices.shift(-span) / prices.shift(-delay) - 1
    return returns.where(continuous & np.isfinite(returns))


def bar_volatility(prices: pd.DataFrame, span: int = 60, min_bars: int = 20) -> pd.DataFrame:
    """Estimate each asset's ex-ante volatility of a one-bar return, at every bar.

    The estimate at row `t` is the exponentially weighted standard deviation of the one-bar
    returns ending at or before `t`, so it is known when the score at `t` is observed. A
    one-bar return needs prices on two consecutive rows; across a gap the last estimate carries
    forward. The estimate is missing until `min_bars` returns have been seen, and where it is
    zero (prices constant over the whole lookback).

    Args:
        prices: Prices with one row per bar and one column per asset. Rows before the
            evaluation window are welcome: they warm the estimate up.
        span: Span of the exponential weights, in bars.
        min_bars: One-bar returns needed before the first estimate.

    Returns:
        A frame shaped like `prices` holding the standard deviation of a one-bar return.
    """
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        returns = prices / prices.shift(1) - 1
    volatility = returns.where(np.isfinite(returns)).ewm(span=span, min_periods=min_bars).std()
    return volatility.where(volatility > 0)


def scale_by_volatility(
    labels: pd.DataFrame, volatility: pd.DataFrame, horizon: int
) -> pd.DataFrame:
    """Divide `horizon`-bar labels by the volatility of a `horizon`-bar return.

    The divisor is `volatility * sqrt(horizon)`, so the scaled label has roughly unit variance
    at every horizon. Labels without a volatility estimate are missing.
    """
    with np.errstate(over="ignore", divide="ignore", invalid="ignore"):
        scaled = labels / (volatility * np.sqrt(horizon))
    return scaled.where(np.isfinite(scaled))


def label_endpoints(index: pd.DatetimeIndex, span: int) -> pd.DatetimeIndex:
    """Return the timestamp at which each bar's label ends: `span` rows later, or `NaT`."""
    return pd.DatetimeIndex(index.to_series().shift(-span))
