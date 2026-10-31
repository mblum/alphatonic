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
    variation in either variable has an undefined (`NaN`) correlation, never zero. `cosine` is
    the uncentred correlation `sum(x * y) / sqrt(sum(x**2) * sum(y**2))`: it needs variation in
    neither variable, only three pairs and a non-zero value on each side. Values within
    `ZERO_TOLERANCE` of zero are returned as exactly zero.

    Args:
        x: Scores with shape `(n, k)`.
        y: Targets with the same shape.
        method: `spearman`, `pearson` or `cosine`.

    Returns:
        The `k` correlations.
    """
    if method == "cosine":
        return cosine_parts(x, y)[0]
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = np.where(valid, x, np.nan), np.where(valid, y, np.nan)
    if method == "spearman":
        x, y = average_ranks(x), average_ranks(y)
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
    return _snap(np.clip(result, -1, 1))


def average_ranks(values: np.ndarray) -> np.ndarray:
    """Rank each column from 1, with ties sharing their average rank and `NaN` staying `NaN`.

    The result equals `pd.DataFrame(values).rank().to_numpy()`, without the cost of building a
    DataFrame, which dominates for the small windows of the time-series evaluation.
    """
    n = len(values)
    # A stable sort puts NaN last, and NaN != NaN, so each NaN is a group of its own.
    order = np.argsort(values, axis=0, kind="stable")
    ordered = np.take_along_axis(values, order, axis=0)
    position = np.arange(n)[:, None]
    starts = np.ones(values.shape, dtype=bool)
    starts[1:] = ordered[1:] != ordered[:-1]
    ends = np.ones(values.shape, dtype=bool)
    ends[:-1] = starts[1:]
    first = np.maximum.accumulate(np.where(starts, position, 0), axis=0)
    last = np.minimum.accumulate(np.where(ends, position, n)[::-1], axis=0)[::-1]
    ranks = np.empty(values.shape)
    np.put_along_axis(ranks, order, (first + last) / 2 + 1, axis=0)
    ranks[np.isnan(values)] = np.nan
    # Column-major, as pandas returns it, so that later column sums add in the same order and
    # correlations agree to the last digit.
    return np.asfortranarray(ranks)


def _snap(values: np.ndarray) -> np.ndarray:
    return np.where(np.abs(values) < ZERO_TOLERANCE, 0.0, values)


def cosine_parts(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Return the cosine of each column pair and the part of it that comes from the means.

    The cosine of the finite pairs splits exactly into a timing and a static part (with population
    moments, and `rms` the root mean square):

        cosine = cov(x, y) / (rms(x) * rms(y)) + mean(x) * mean(y) / (rms(x) * rms(y))

    The static part is what the average position earns from the average target. Both are `NaN`
    without three pairs or with only zeros on one side, and values within `ZERO_TOLERANCE` of zero
    are exactly zero.

    Returns:
        `(cosine, static)`, one value per column each.
    """
    valid = np.isfinite(x) & np.isfinite(y)
    count = valid.sum(axis=0)
    sums = []
    for array in (x, y):
        # Scaling avoids overflow for large finite values; the cosine is scale-invariant.
        scale = np.max(np.where(valid, np.abs(array), 0), axis=0, initial=0)
        sums.append(np.where(valid, array / np.where(scale > 0, scale, 1), 0.0))
    a, b = sums
    denominator = np.sqrt((a * a).sum(axis=0) * (b * b).sum(axis=0))
    defined = (count >= 3) & (denominator > 0)
    cosine = np.divide(
        (a * b).sum(axis=0), denominator, out=np.full(len(count), np.nan), where=defined
    )
    # mean(a) * mean(b) / sqrt(mean(a²) * mean(b²)) = sum(a) * sum(b) / (n * sqrt(...)).
    static = np.divide(
        a.sum(axis=0) * b.sum(axis=0),
        count * denominator,
        out=np.full(len(count), np.nan),
        where=defined,
    )
    return _snap(np.clip(cosine, -1, 1)), _snap(np.clip(static, -1, 1))


class _Ranks:
    """Average ranks of each column's values under any row multiplicities, without re-sorting.

    Rows are sorted once. For multiplicities `m`, the rank of a value is the number of resampled
    rows below it plus half of the rows tied with it (itself included) plus one half, which is
    what ranking the resampled column gives, with ties sharing their average rank. Arrays have
    one row per column of the data (`k` by `n`), so every column is contiguous, and the gathers
    use flat indices computed once.
    """

    def __init__(self, values: np.ndarray, valid: np.ndarray) -> None:
        k, n = values.shape
        masked = np.where(valid, values, np.inf)
        order = np.argsort(masked, axis=1, kind="stable")
        ordered = np.take_along_axis(masked, order, axis=1)
        position = np.arange(n)[None, :]
        starts = np.ones(values.shape, dtype=bool)
        starts[:, 1:] = ordered[:, 1:] != ordered[:, :-1]
        ends = np.ones(values.shape, dtype=bool)
        ends[:, :-1] = starts[:, 1:]
        first = np.maximum.accumulate(np.where(starts, position, 0), axis=1)
        last = np.minimum.accumulate(np.where(ends, position, n)[:, ::-1], axis=1)[:, ::-1]
        offset = (np.arange(k) * n)[:, None]
        self.shape = values.shape
        self.order = (order + offset).ravel()
        self.first = (first + offset).ravel()
        self.last = (last + offset).ravel()

    def __call__(self, weights: np.ndarray) -> np.ndarray:
        """Return the ranks, in the original row order, for `weights` of shape `(k, n)`."""
        by_rank = np.take(weights.ravel(), self.order).reshape(self.shape)
        cumulative = np.cumsum(by_rank, axis=1)
        before = np.take((cumulative - by_rank).ravel(), self.first)
        through = np.take(cumulative.ravel(), self.last)
        ranks = np.empty(weights.size)
        ranks[self.order] = (before + through + 1) / 2
        return ranks.reshape(self.shape)


class ResampledCorrelations:
    """Correlations of resampled rows, from how often each row was drawn.

    `correlations(x[rows], y[rows], method)` for a sample of row indices sorts and copies the data
    on every call. Bootstrapping calls it thousands of times for the same data, so this class
    sorts once and takes the row multiplicities of a sample instead. The result is the same:
    only rows where both values are finite take part, Spearman ranks are those of the resampled
    pairs with ties sharing their average rank, and a column without at least three pairs or without
    variation in either variable is `NaN` (for `cosine`, without three pairs or with only zeros on
    one side).
    """

    def __init__(self, x: np.ndarray, y: np.ndarray) -> None:
        x, y = np.ascontiguousarray(x.T, dtype=float), np.ascontiguousarray(y.T, dtype=float)
        self.valid = np.isfinite(x) & np.isfinite(y)
        self.raw = (x, y)
        scaled = []
        for array in (x, y):
            scale = np.max(np.where(self.valid, np.abs(array), 0), axis=1, initial=0)
            scaled.append(np.where(self.valid, array / np.where(scale > 0, scale, 1)[:, None], 0.0))
        self.x, self.y = scaled
        self._ranks: dict[str, _Ranks] = {}
        self._products: tuple[np.ndarray, ...] | None = None

    def __call__(self, multiplicity: np.ndarray, method: str) -> np.ndarray:
        """Correlate the columns for a sample that draws row `i` `multiplicity[i]` times."""
        if method == "cosine":
            return self._cosine(multiplicity)
        x, y = self.raw
        weights = self.valid * multiplicity[None, :]
        drawn = weights > 0
        if method == "spearman":
            if not self._ranks:
                self._ranks = {"x": _Ranks(x, self.valid), "y": _Ranks(y, self.valid)}
            a, b = self._ranks["x"](weights), self._ranks["y"](weights)
        else:
            a, b = self.x, self.y
        varying = np.ones(len(a), dtype=bool)
        for raw in (x, y):
            high = np.max(np.where(drawn, raw, -np.inf), axis=1, initial=-np.inf)
            low = np.min(np.where(drawn, raw, np.inf), axis=1, initial=np.inf)
            varying &= high > low
        count = weights.sum(axis=1)
        mean_a = np.divide((weights * a).sum(axis=1), count, out=np.zeros(len(a)), where=count > 0)
        mean_b = np.divide((weights * b).sum(axis=1), count, out=np.zeros(len(a)), where=count > 0)
        ac, bc = a - mean_a[:, None], b - mean_b[:, None]
        weighted = weights * ac
        denominator = np.sqrt((weighted * ac).sum(axis=1) * (weights * bc * bc).sum(axis=1))
        result = np.divide(
            (weighted * bc).sum(axis=1),
            denominator,
            out=np.full(len(a), np.nan),
            where=(count >= 3) & varying & (denominator > 0),
        )
        return _snap(np.clip(result, -1, 1))

    def _cosine(self, multiplicity: np.ndarray) -> np.ndarray:
        # The scaled values are zero outside valid rows and fixed across draws, so each sum of
        # the resample is a product of a fixed matrix with the multiplicities.
        if self._products is None:
            a, b = self.x, self.y
            self._products = (a * b, a * a, b * b, self.valid.astype(float))
        ab, aa, bb, valid = self._products
        count = valid @ multiplicity
        denominator = np.sqrt((aa @ multiplicity) * (bb @ multiplicity))
        result = np.divide(
            ab @ multiplicity,
            denominator,
            out=np.full(len(ab), np.nan),
            where=(count >= 3) & (denominator > 0),
        )
        return _snap(np.clip(result, -1, 1))


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
    """Correlate each row of `scores` with the same row of `returns`."""
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

    A single-sample view of `bucket_means`; the result is empty if scores do not vary.
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
