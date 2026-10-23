import numpy as np
import pandas as pd
import pytest

from alphatonic.config import EvaluationConfig


def regular_panel(
    n_assets: int = 6,
    n_bars: int = 240,
    *,
    freq: str = "h",
    start: str = "2026-01-01",
    seed: int = 0,
    missing: float = 0.0,
    ties: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """A random factor/price panel on a regular grid (tz-aware, UTC)."""
    rng = np.random.default_rng(seed)
    index = pd.date_range(start, periods=n_bars, freq=freq, tz="UTC")
    columns = [f"A{i}" for i in range(n_assets)]
    score = rng.normal(size=(n_bars, n_assets))
    if ties:
        score = np.round(score)
    returns = 0.01 * (
        0.3 * np.vstack([np.zeros((1, n_assets)), score[:-1]]) + rng.normal(size=score.shape)
    )
    prices = 100 * np.cumprod(1 + returns, axis=0)
    if missing:
        prices[rng.random(prices.shape) < missing] = np.nan
        score[rng.random(score.shape) < missing] = np.nan
    return (
        pd.DataFrame(score, index=index, columns=columns),
        pd.DataFrame(prices, index=index, columns=columns),
    )


@pytest.fixture
def panel():
    return regular_panel()


@pytest.fixture
def config():
    return EvaluationConfig(
        horizons=[1, 4],
        min_assets=3,
        time_series={
            "min_pairs": 20,
            "min_horizons": 2,
            "bootstrap_samples": 100,
            "rolling_window": "2D",
            "rolling_step": "1D",
        },
    )


def perfect_market(n_assets: int = 5, n_bars: int = 48, freq: str = "h"):
    """Assets grow at different constant rates, so growth ranks are a perfect cross-sectional factor."""
    index = pd.date_range("2026-01-01", periods=n_bars, freq=freq, tz="UTC")
    rates = 1 + (np.arange(n_assets) + 1) / 100
    prices = pd.DataFrame(
        100 * rates[None, :] ** np.arange(n_bars)[:, None],
        index=index,
        columns=[f"A{i}" for i in range(n_assets)],
    )
    factor = pd.DataFrame(np.tile(rates, (n_bars, 1)), index=index, columns=prices.columns)
    return factor, prices
