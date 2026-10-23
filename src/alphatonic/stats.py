"""Correlations, dependence-aware inference, and score buckets."""

from __future__ import annotations

from math import erfc, sqrt

import numpy as np
import pandas as pd

BLOCK_ROWS = 256
"""Rows processed at once by the matrix routines, which bounds their temporary arrays."""

_Z95 = 1.959963984540054

ZERO_TOLERANCE = 1e-12
"""Correlations smaller than this in magnitude are floating-point noise and are reported as 0.

Rank correlations of small samples take discrete values, and some are exactly zero. Without this,
the sign of rounding error would decide whether such a period counts as a positive IC."""


def correlations(x: np.ndarray, y: np.ndarray, method: str) -> np.ndarray:
    """Correlate the columns of `x` with the columns of `y`.

    Only rows where both values are finite take part, and Spearman ranks are recomputed on those
    pairs, with ties sharing their average rank. A column with fewer than three pairs or without
    variation in either variable has an undefined (`NaN`) correlation, never zero. Values within
    `ZERO_TOLERANCE` of zero are returned as exactly zero.

    Args:
        x: Scores with shape `(n, k)`.
        y: Targets with the same shape.
        method: `spearman` or `pearson`.

    Returns:
        The `k` correlations.
    """
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = np.where(valid, x, np.nan), np.where(valid, y, np.nan)
    if method == "spearman":
        x, y = pd.DataFrame(x).rank().to_numpy(), pd.DataFrame(y).rank().to_numpy()
    # Scaling avoids overflow for finite large scores; exact range checks reject constants
    # even when floating-point centering leaves tiny nonzero residuals (e.g. repeated 0.1).
    varying = np.ones(x.shape[1], dtype=bool)
    scaled = []
    for array in (x, y):
        high = np.max(np.where(valid, array, -np.inf), axis=0, initial=-np.inf)
        low = np.min(np.where(valid, array, np.inf), axis=0, initial=np.inf)
        varying &= high > low
        scale = np.max(np.where(valid, np.abs(array), 0), axis=0, initial=0)
        scaled.append(array / np.where(scale > 0, scale, 1))
    x, y = scaled
    count = valid.sum(axis=0)
    xm = np.divide(np.nansum(x, axis=0), count, out=np.zeros(x.shape[1]), where=count > 0)
    ym = np.divide(np.nansum(y, axis=0), count, out=np.zeros(y.shape[1]), where=count > 0)
    xc, yc = np.where(valid, x - xm, 0), np.where(valid, y - ym, 0)
    denominator = np.sqrt((xc * xc).sum(axis=0) * (yc * yc).sum(axis=0))
    result = np.divide(
        (xc * yc).sum(axis=0),
        denominator,
        out=np.full(x.shape[1], np.nan),
        where=(count >= 3) & varying & (denominator > 0),
    )
    result = np.clip(result, -1, 1)
    return np.where(np.abs(result) < ZERO_TOLERANCE, 0.0, result)


def summarize_ic(series: pd.Series, lags: int) -> dict[str, float | int]:
    """Summarize a series of ICs with a Newey-West standard error of its mean.

    The standard error uses Bartlett weights and an `n / (n - 1)` correction. Missing periods
    contribute zero scores but keep their time positions, so lag `k` always means `k` bars, and
    the denominator is the number of valid observations, not the length of the series. The
    p-value and 95% interval use the asymptotic normal approximation. Statistics that cannot be
    computed are omitted from the result: no spread below two observations, no ratio for a
    constant series, and no inference unless there are more observations than `lags + 1`.

    Args:
        series: ICs in time order, with `NaN` for periods without a valid IC.
        lags: Number of autocovariance lags in the standard error.

    Returns:
        `n_periods`, `hac_lags` and, when defined, `mean`, `positive_fraction`, `std`, `ic_ir`
        (mean / std, not annualized), `hac_se`, `hac_z`, `hac_p_value`, `ci95_lower` and
        `ci95_upper`.
    """
    valid = series.dropna()
    n = len(valid)
    result: dict[str, float | int] = {"n_periods": n, "hac_lags": lags}
    if not n:
        return result
    mean = float(valid.mean())
    result.update(mean=mean, positive_fraction=float((valid > 0).mean()))
    if n < 2:
        return result
    std = float(valid.std(ddof=1))
    result["std"] = std
    if std <= 1e-12:
        return result
    result["ic_ir"] = mean / std  # Deliberately not annualized.
    if n <= lags + 1:
        return result
    scores = (series - mean).fillna(0).to_numpy(dtype=float)
    meat = float(scores @ scores)
    for lag in range(1, lags + 1):
        meat += 2 * (1 - lag / (lags + 1)) * float(scores[lag:] @ scores[:-lag])
    se = sqrt(max(meat, 0) / (n * (n - 1)))
    if se > 1e-12:
        z = mean / se
        result.update(
            hac_se=se,
            hac_z=z,
            hac_p_value=erfc(abs(z) / sqrt(2)),
            ci95_lower=mean - _Z95 * se,
            ci95_upper=mean + _Z95 * se,
        )
    return result


def row_correlations(scores: np.ndarray, returns: np.ndarray, method: str) -> np.ndarray:
    """Correlate each row of `scores` with the same row of `returns`, as [`correlations`][]."""
    out = np.empty(len(scores))
    for start in range(0, len(scores), BLOCK_ROWS):
        block = slice(start, start + BLOCK_ROWS)
        out[block] = correlations(scores[block].T, returns[block].T, method)
    return out


def bucket_means(
    scores: np.ndarray, returns: np.ndarray, quantiles: int
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Average return by score bucket, row by row.

    Within each row, pairs where both values are finite are ranked by score (ties share their
    average rank and therefore their bucket) and split into `quantiles` buckets of equal rank
    width, `1` holding the lowest scores. Buckets are retrospective: they describe the sample and
    are not thresholds a strategy could have used. A bucket without pairs has a missing mean.

    Args:
        scores: Scores with shape `(rows, assets)`.
        returns: Targets with the same shape.
        quantiles: Number of buckets.

    Returns:
        `(means, counts, usable)`: the mean return and pair count per row and bucket, with shapes
        `(rows, quantiles)`, and which rows have at least two distinct finite scores. Rows that
        are not usable have undefined means and zero counts.
    """
    rows = len(scores)
    means = np.full((rows, quantiles), np.nan)
    counts = np.zeros((rows, quantiles), dtype=int)
    usable = np.zeros(rows, dtype=bool)
    for start in range(0, rows, BLOCK_ROWS):
        block = slice(start, start + BLOCK_ROWS)
        valid = np.isfinite(scores[block]) & np.isfinite(returns[block])
        x = np.where(valid, scores[block], np.nan)
        y = np.where(valid, returns[block], 0.0)
        high = np.max(np.where(valid, x, -np.inf), axis=1, initial=-np.inf)
        low = np.min(np.where(valid, x, np.inf), axis=1, initial=np.inf)
        varying = high > low
        pairs = valid.sum(axis=1)
        ranks = pd.DataFrame(x).rank(axis=1, method="average").to_numpy()
        percentile = np.divide(ranks, pairs[:, None], out=np.zeros_like(ranks), where=valid)
        bucket = np.where(valid, np.ceil(percentile * quantiles), 0).astype(int)
        for q in range(1, quantiles + 1):
            member = bucket == q
            n = member.sum(axis=1)
            counts[block, q - 1] = np.where(varying, n, 0)
            means[block, q - 1] = np.divide(
                (y * member).sum(axis=1), n, out=np.full(len(n), np.nan), where=(n > 0) & varying
            )
        usable[block] = varying
    return means, counts, usable


def quantile_rows(x: pd.Series, y: pd.Series, quantiles: int = 5) -> list[dict]:
    """Return the score-bucket rows of one sample, keeping ties together and empty bins visible.

    A single-sample view of [`bucket_means`][]; the sample is empty if scores do not vary.
    """
    means, counts, usable = bucket_means(
        x.to_numpy(dtype=float)[None, :], y.to_numpy(dtype=float)[None, :], quantiles
    )
    if not usable[0]:
        return []
    return [
        {"quantile": q + 1, "mean_return": float(means[0, q]), "n_pairs": int(counts[0, q])}
        for q in range(quantiles)
    ]
