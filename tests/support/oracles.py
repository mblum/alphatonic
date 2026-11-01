"""Scalar mathematical references, deliberately independent of package helpers."""

from math import fsum, sqrt

import numpy as np


def ranks(values):
    return [1 + sum(w < v for w in values) + (sum(w == v for w in values) - 1) / 2 for v in values]


def correlation(x, y, method="pearson"):
    pairs = [
        (float(a), float(b)) for a, b in zip(x, y, strict=True) if np.isfinite(a) and np.isfinite(b)
    ]
    if len(pairs) < 3:
        return np.nan
    a, b = map(list, zip(*pairs, strict=True))
    if method == "spearman":
        a, b = ranks(a), ranks(b)
    a = [v / max(map(abs, a), default=1) if any(a) else 0 for v in a]
    b = [v / max(map(abs, b), default=1) if any(b) else 0 for v in b]
    if method != "cosine":
        if len(set(a)) == 1 or len(set(b)) == 1:
            return np.nan
        ma, mb = fsum(a) / len(a), fsum(b) / len(b)
        a, b = [v - ma for v in a], [v - mb for v in b]
    denominator = sqrt(fsum(v * v for v in a) * fsum(v * v for v in b))
    return fsum(v * w for v, w in zip(a, b, strict=True)) / denominator if denominator else np.nan


def returns(prices, horizon, delay=0):
    result = np.full(prices.shape, np.nan)
    for t in range(len(prices) - horizon - delay):
        for j in range(prices.shape[1]):
            if all(np.isfinite(prices[k, j]) for k in range(t, t + delay + horizon + 1)):
                result[t, j] = prices[t + delay + horizon, j] / prices[t + delay, j] - 1
    return result


def hac(values, lags):
    valid = [v for v in values if np.isfinite(v)]
    n = len(valid)
    mean = fsum(valid) / n
    scores = [v - mean if np.isfinite(v) else 0 for v in values]
    meat = fsum(v * v for v in scores)
    for lag in range(1, lags + 1):
        meat += (
            2
            * (1 - lag / (lags + 1))
            * fsum(scores[t] * scores[t - lag] for t in range(lag, len(scores)))
        )
    return sqrt(max(0, meat) / (n * (n - 1)))


def ewc(values, dof):
    n, k = values.shape
    return np.array(
        [
            sum(
                (
                    sqrt(2 / n)
                    * sum(np.cos(np.pi * j * (t + 0.5) / n) * values[t, c] for t in range(n))
                )
                ** 2
                for j in range(1, dof + 1)
            )
            / dof
            for c in range(k)
        ]
    )
