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


def label_endpoints(index: pd.DatetimeIndex, span: int) -> pd.DatetimeIndex:
    """Return the timestamp at which each bar's label ends: `span` rows later, or `NaT`."""
    return pd.DatetimeIndex(index.to_series().shift(-span))
