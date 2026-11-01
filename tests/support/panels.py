import numpy as np
import pandas as pd


def market(n=100, k=5, seed=41):
    rng = np.random.default_rng(seed)
    index = pd.date_range("2024-01-01", periods=n, freq="D", tz="UTC", name="timestamp")
    scores = rng.normal(size=(n, k))
    increments = 0.003 * scores[:-1] + 0.01 * rng.normal(size=(n - 1, k))
    prices = np.vstack([np.full(k, 100.0), 100 * np.cumprod(1 + increments, axis=0)])
    columns = [f"asset{j}" for j in range(k)]
    return pd.DataFrame(scores, index=index, columns=columns), pd.DataFrame(
        prices, index=index, columns=columns
    )
