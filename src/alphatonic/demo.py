"""Synthetic data for tutorials, tests and trying the library without a data vendor."""

from __future__ import annotations

import numpy as np
import pandas as pd


def synthetic_market(
    n_assets: int = 50,
    n_bars: int = 500,
    *,
    freq: str = "B",
    start: str = "2020-01-01",
    ic: float = 0.05,
    persistence: float = 0.9,
    missing_fraction: float = 0.0,
    seed: int = 0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Simulate prices and a factor that predicts their next-bar returns.

    Each asset has a latent score that evolves as an AR(1) process with unit variance. The return
    over the next bar is a fixed multiple of the score plus independent noise, scaled so that the
    population correlation between the score and the next-bar return is `ic`. Longer horizons
    inherit part of that relationship through `persistence`. Prices are positive and
    start at 100.

    Args:
        n_assets: Number of assets.
        n_bars: Number of bars (rows).
        freq: A pandas frequency alias for the bars, such as `B` (business days), `D` or `h`.
        start: First timestamp. The index is timezone-naive.
        ic: Target correlation between the score and the next-bar return, in `[0, 1)`.
        persistence: Autocorrelation of each asset's score from one bar to the next, in `[0, 1)`.
        missing_fraction: Fraction of prices set to `NaN` at random.
        seed: Seed of the random number generator.

    Returns:
        `(factor, prices)`: two tables of the same shape, indexed by timestamp, with the assets
        `A000`, `A001`, ... as columns.
    """
    if not 0 <= ic < 1 or not 0 <= persistence < 1 or not 0 <= missing_fraction < 1:
        raise ValueError("ic, persistence and missing_fraction must be in [0, 1)")
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=n_bars, freq=freq)
    columns = [f"A{i:03d}" for i in range(n_assets)]
    score = np.empty((n_bars, n_assets))
    score[0] = rng.normal(size=n_assets)
    shocks = rng.normal(size=(n_bars, n_assets)) * np.sqrt(1 - persistence**2)
    for t in range(1, n_bars):
        score[t] = persistence * score[t - 1] + shocks[t]
    slope = ic / np.sqrt(1 - ic**2)
    noise = rng.normal(size=(n_bars, n_assets))
    returns = np.zeros((n_bars, n_assets))
    returns[1:] = 0.01 * (slope * score[:-1] + noise[1:])
    prices = 100 * np.cumprod(1 + np.clip(returns, -0.5, None), axis=0)
    if missing_fraction:
        prices[rng.random(prices.shape) < missing_fraction] = np.nan
    return (
        pd.DataFrame(score, index=index, columns=columns),
        pd.DataFrame(prices, index=index, columns=columns),
    )
