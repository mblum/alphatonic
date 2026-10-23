"""Cross-sectional IC: how well scores rank assets at the same timestamp."""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphatonic.config import METHODS, EvaluationConfig
from alphatonic.progress import ProgressFactory, silent
from alphatonic.stats import BLOCK_ROWS, bucket_means, row_correlations, summarize_ic

QUANTILE_COLUMNS = ["timestamp", "horizon", "quantile", "mean_return", "n_pairs"]


def cross_sectional_ic(
    factor: pd.DataFrame,
    labels: dict[int, pd.DataFrame],
    prices: pd.DataFrame,
    config: EvaluationConfig,
    progress: ProgressFactory = silent,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Compute the IC at every timestamp and horizon, then summarize it per horizon.

    All three frames share the evaluation grid of `factor`; `labels` holds each horizon's
    forward returns and `prices` the prices that decide how many assets are available.

    Returns:
        `(periods, summary, quantiles)`: one row per timestamp and horizon with both
        correlations, pair counts and a status; one row per horizon and method with mean, HAC
        inference and counts; and the mean return of each score bucket per valid timestamp.
    """
    available = prices.notna().sum(axis=1).to_numpy()
    scored = factor.notna().sum(axis=1).to_numpy()
    timestamps = factor.index
    scores = factor.to_numpy(dtype=float)
    periods, buckets = [], []
    with progress("Evaluating IC", len(config.horizons)) as advance:
        for horizon in config.horizons:
            advance(0, description=f"Evaluating IC · h{horizon}")
            period, bucket = _horizon_periods(scores, labels[horizon].to_numpy(dtype=float), config)
            with np.errstate(divide="ignore", invalid="ignore"):
                coverage = np.where(available > 0, period["n_pairs"] / available, np.nan)
            frame = pd.DataFrame(
                {
                    "timestamp": timestamps,
                    "horizon": horizon,
                    "spearman": period["spearman"],
                    "pearson": period["pearson"],
                    "n_available": available,
                    "n_signal": scored,
                    "n_pairs": period["n_pairs"],
                    "pair_coverage": coverage,
                    "status": period["status"],
                }
            )
            periods.append(frame)
            buckets.append(_bucket_frame(bucket, timestamps, horizon, config.quantiles))
            advance()
    periods = pd.concat(periods, ignore_index=True)
    quantiles = pd.concat(buckets, ignore_index=True)
    return periods, _summarize(periods, config), quantiles


def _horizon_periods(
    scores: np.ndarray, targets: np.ndarray, config: EvaluationConfig
) -> tuple[dict, dict]:
    rows = len(scores)
    valid = np.isfinite(scores) & np.isfinite(targets)
    pairs = valid.sum(axis=1)
    spearman = np.full(rows, np.nan)
    pearson = np.full(rows, np.nan)
    status = np.full(rows, "insufficient_assets", dtype=object)
    bucket = {"rows": np.empty(0, dtype=int), "means": None, "counts": None}
    if config.mode == "time_series":
        status[:] = "disabled"
    else:
        eligible = np.flatnonzero(pairs >= config.min_assets)
        done, means, counts = [], [], []
        for start in range(0, len(eligible), BLOCK_ROWS):
            block = eligible[start : start + BLOCK_ROWS]
            x = np.where(valid[block], scores[block], np.nan)
            y = np.where(valid[block], targets[block], np.nan)
            constant_x = ~(np.nanmax(x, axis=1) > np.nanmin(x, axis=1))
            constant_y = ~(np.nanmax(y, axis=1) > np.nanmin(y, axis=1))
            status[block[constant_x]] = "constant_signal"
            status[block[~constant_x & constant_y]] = "constant_returns"
            ok = ~constant_x & ~constant_y
            rows_ok = block[ok]
            if not len(rows_ok):
                continue
            status[rows_ok] = "valid"
            spearman[rows_ok] = row_correlations(x[ok], y[ok], "spearman")
            pearson[rows_ok] = row_correlations(x[ok], y[ok], "pearson")
            block_means, block_counts, _ = bucket_means(x[ok], y[ok], config.quantiles)
            done.append(rows_ok)
            means.append(block_means)
            counts.append(block_counts)
        if done:
            bucket = {
                "rows": np.concatenate(done),
                "means": np.concatenate(means),
                "counts": np.concatenate(counts),
            }
    period = {"spearman": spearman, "pearson": pearson, "n_pairs": pairs, "status": status}
    return period, bucket


def _bucket_frame(
    bucket: dict, timestamps: pd.DatetimeIndex, horizon: int, quantiles: int
) -> pd.DataFrame:
    rows = bucket["rows"]
    if not len(rows):
        return pd.DataFrame(columns=QUANTILE_COLUMNS).astype(
            {"horizon": int, "quantile": int, "n_pairs": int}
        )
    return pd.DataFrame(
        {
            "timestamp": np.repeat(timestamps[rows], quantiles),
            "horizon": horizon,
            "quantile": np.tile(np.arange(1, quantiles + 1), len(rows)),
            "mean_return": bucket["means"].ravel(),
            "n_pairs": bucket["counts"].ravel(),
        }
    )


def _summarize(periods: pd.DataFrame, config: EvaluationConfig) -> pd.DataFrame:
    summaries = []
    for horizon, group in periods.groupby("horizon", sort=True):
        for method in METHODS:
            series = group[method]
            n = int(series.notna().sum())
            automatic = int(np.floor(4 * (n / 100) ** (2 / 9))) if n else 0
            lags = max(
                int(horizon) - 1, config.hac_lags if config.hac_lags is not None else automatic
            )
            summaries.append(
                {
                    "horizon": horizon,
                    "method": method,
                    "total_periods": len(group),
                    "skipped_periods": int(series.isna().sum()),
                    "mean_pair_coverage": float(group["pair_coverage"].mean()),
                    "mean_n_pairs": float(group["n_pairs"].mean()),
                    **summarize_ic(series, lags),
                }
            )
    return pd.DataFrame(summaries)
