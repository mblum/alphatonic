"""Time-series IC: how well an asset's scores predict its own returns over time."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from alphatonic.config import METHODS, EvaluationConfig
from alphatonic.progress import ProgressFactory, silent, track
from alphatonic.returns import label_endpoints
from alphatonic.stats import bucket_means, correlations

TABLES = ("assets", "monthly", "rolling", "summary", "quantiles")


@dataclass
class TimeSeriesEvaluation:
    """Time-series results, one table per view.

    Every table except `summary` and `quantiles` has one row per asset, horizon and method (and
    window, for `monthly` and `rolling`); see the results reference for the columns.
    """

    assets: pd.DataFrame
    """Full-period IC per asset with eligibility, monthly statistics and bootstrap intervals."""

    monthly: pd.DataFrame
    """IC recomputed inside each UTC calendar month."""

    rolling: pd.DataFrame
    """IC recomputed inside trailing windows."""

    summary: pd.DataFrame
    """Equal-asset summaries per horizon and method."""

    quantiles: pd.DataFrame
    """Mean return by score bucket within each eligible asset."""

    def tables(self) -> dict[str, pd.DataFrame]:
        """Return the tables by name."""
        return {name: getattr(self, name) for name in TABLES}


WINDOW_COLUMNS = [
    "asset",
    "horizon",
    "method",
    "window_start",
    "window_end",
    "complete",
    "n_expected",
    "n_pairs",
    "boundary_excluded",
    "pair_coverage",
    "status",
    "first_pair",
    "last_pair",
    "ic",
]


def _varies(values: np.ndarray, finite: np.ndarray) -> np.ndarray:
    """Whether each column has at least two distinct values among its finite pairs."""
    high = np.max(np.where(finite, values, -np.inf), axis=0, initial=-np.inf)
    low = np.min(np.where(finite, values, np.inf), axis=0, initial=np.inf)
    return high > low


def window_arrays(
    x: pd.DataFrame,
    y: pd.DataFrame,
    config: EvaluationConfig,
    horizon: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
    endpoints: pd.DatetimeIndex,
    *,
    complete: bool = True,
) -> dict[str, np.ndarray]:
    """Compute each asset's IC inside the half-open window `[start, end)`, as column arrays.

    A bar takes part only if its label also ends inside the window: `endpoints` holds the
    timestamp at which each row of `x` has its label end (`NaT` where it has none). Rows that
    are in the window but whose label ends outside it are counted in `boundary_excluded`.
    The arrays hold one entry per asset and method, assets first, in the order of
    `WINDOW_COLUMNS`; timestamps are `datetime64[ns]` in UTC.
    """
    options = config.time_series
    in_window = (x.index >= start) & (x.index < end)
    eligible = in_window & np.asarray(endpoints < end)
    stamps = x.index.as_unit("ns").asi8[eligible]
    scores, returns = x.to_numpy(float)[eligible], y.to_numpy(float)[eligible]
    finite = np.isfinite(scores) & np.isfinite(returns)
    counts = finite.sum(axis=0)
    expected = int(eligible.sum())
    coverage = counts / expected if expected else np.zeros(len(counts))
    duration_ok = int(in_window.sum()) >= options.min_horizons * horizon
    status = np.select(
        [
            np.full(len(counts), not complete),
            np.full(len(counts), not duration_ok),
            counts < options.min_pairs,
            coverage < options.min_coverage,
            ~_varies(scores, finite),
            ~_varies(returns, finite),
        ],
        [
            "partial_window",
            "short_window",
            "insufficient_pairs",
            "low_coverage",
            "constant_signal",
            "constant_returns",
        ],
        default="valid",
    )
    valid = status == "valid"
    ic = np.column_stack(
        [np.where(valid, correlations(scores, returns, m), np.nan) for m in METHODS]
    )
    missing = np.iinfo(np.int64).min
    if expected:
        first = np.where(counts > 0, stamps[finite.argmax(axis=0)], missing)
        last = np.where(counts > 0, stamps[expected - 1 - finite[::-1].argmax(axis=0)], missing)
    else:
        first = last = np.full(len(counts), missing)
    each = len(METHODS)
    rows = len(counts) * each
    return {
        "asset": np.repeat(x.columns.to_numpy(), each),
        "horizon": np.full(rows, horizon),
        "method": np.tile(METHODS, len(counts)),
        "window_start": np.full(rows, start.value, dtype="int64"),
        "window_end": np.full(rows, end.value, dtype="int64"),
        "complete": np.full(rows, complete),
        "n_expected": np.full(rows, expected),
        "n_pairs": np.repeat(counts, each),
        "boundary_excluded": np.full(rows, int(in_window.sum()) - expected),
        "pair_coverage": np.repeat(coverage, each),
        "status": np.repeat(status, each),
        "first_pair": np.repeat(first, each),
        "last_pair": np.repeat(last, each),
        "ic": ic.ravel(),
    }


def window_table(*args, **kwargs) -> pd.DataFrame:
    """Compute one window as a table; the arguments of `window_arrays`."""
    return _table([window_arrays(*args, **kwargs)])


def _table(windows: list[dict[str, np.ndarray]]) -> pd.DataFrame:
    """Stack windows into one table with timezone-aware timestamp columns."""
    if not windows:
        return pd.DataFrame(columns=WINDOW_COLUMNS)
    table = pd.DataFrame(
        {name: np.concatenate([w[name] for w in windows]) for name in WINDOW_COLUMNS}
    )
    for name in ("window_start", "window_end", "first_pair", "last_pair"):
        table[name] = pd.to_datetime(table[name].astype("int64"), utc=True).dt.as_unit("ns")
    return table


def bootstrap_intervals(
    x: pd.DataFrame,
    y: pd.DataFrame,
    assets: pd.DataFrame,
    config: EvaluationConfig,
    horizon: int,
    progress: ProgressFactory = silent,
) -> tuple[dict, dict]:
    """Bootstrap percentile intervals with circular paired blocks.

    The same sampled time indices serve every asset and both methods, so cross-asset dependence
    is preserved, and the set of eligible assets is fixed across draws.

    Returns:
        Per-asset results keyed by `(method, asset)` and aggregate results keyed by method.
    """
    options = config.time_series
    n = len(x)
    block = max(horizon, options.block_bars or int(np.ceil(n ** (1 / 3))))
    asset_results, aggregate_results = {}, {}
    for method in METHODS:
        aggregate_results[method] = {
            "bootstrap_block_bars": block,
            "bootstrap_samples": options.bootstrap_samples,
            "bootstrap_valid": 0,
            "bootstrap_status": "disabled",
            "ci95_lower": np.nan,
            "ci95_upper": np.nan,
        }
    if not options.bootstrap_samples:
        return asset_results, aggregate_results
    if n < 5 * block:
        for result in aggregate_results.values():
            result["bootstrap_status"] = "too_few_blocks"
        return asset_results, aggregate_results
    masks = {
        m: assets.loc[assets.method == m]
        .set_index("asset")
        .reindex(x.columns)
        .ic.notna()
        .to_numpy()
        for m in METHODS
    }
    if not any(mask.any() for mask in masks.values()):
        for result in aggregate_results.values():
            result["bootstrap_status"] = "no_eligible_assets"
        return asset_results, aggregate_results
    rng = np.random.default_rng(np.random.SeedSequence([options.seed, horizon]))
    draws = {m: np.full((options.bootstrap_samples, x.shape[1]), np.nan) for m in METHODS}
    xv, yv = x.to_numpy(), y.to_numpy()
    for b in track(range(options.bootstrap_samples), f"TS bootstrap · h{horizon}", progress):
        starts = rng.integers(0, n, size=int(np.ceil(n / block)))
        indices = ((starts[:, None] + np.arange(block)) % n).ravel()[:n]
        for method in METHODS:
            draws[method][b] = correlations(xv[indices], yv[indices], method)
    minimum = max(100, int(np.ceil(0.8 * options.bootstrap_samples)))
    for method in METHODS:
        mask = masks[method]
        for i, asset in enumerate(x.columns):
            sample = draws[method][:, i]
            sample = sample[np.isfinite(sample)] if mask[i] else np.array([])
            lo, hi = (
                np.quantile(sample, [0.025, 0.975]) if len(sample) >= minimum else (np.nan, np.nan)
            )
            asset_results[method, asset] = {
                "ci95_lower": lo,
                "ci95_upper": hi,
                "bootstrap_valid": len(sample),
                "bootstrap_status": "valid" if len(sample) >= minimum else "insufficient_draws",
            }
        selected = draws[method][:, mask]
        # Do not let the asset composition change between bootstrap draws.
        good = np.isfinite(selected).all(axis=1)
        sample = selected[good].mean(axis=1) if mask.any() else np.array([])
        result = aggregate_results[method]
        result["bootstrap_valid"] = len(sample)
        result["bootstrap_status"] = "valid" if len(sample) >= minimum else "insufficient_draws"
        if len(sample) >= minimum:
            result["ci95_lower"], result["ci95_upper"] = np.quantile(sample, [0.025, 0.975])
    return asset_results, aggregate_results


def monthly_statistics(series: pd.Series, minimum: int) -> dict:
    """Summarize monthly ICs, with an ICIR (mean / std) once `minimum` months are valid."""
    valid = series.dropna()
    n = len(valid)
    std = float(valid.std()) if n > 1 else np.nan
    return {
        "valid_months": n,
        "skipped_months": len(series) - n,
        "monthly_mean_ic": float(valid.mean()),
        "monthly_std_ic": std,
        "monthly_ic_ir": float(valid.mean() / std) if n >= minimum and std > 1e-12 else np.nan,
        "monthly_ir_status": (
            "insufficient_months"
            if n < minimum
            else "constant_ic"
            if not std > 1e-12
            else "preliminary"
            if n < 12
            else "available"
        ),
    }


def evaluate_time_series(
    factor: pd.DataFrame,
    labels: dict[int, pd.DataFrame],
    config: EvaluationConfig,
    grid: pd.DatetimeIndex,
    start: pd.Timestamp,
    end: pd.Timestamp,
    progress: ProgressFactory = silent,
) -> TimeSeriesEvaluation:
    """Evaluate every asset over time for each horizon in `labels`.

    Args:
        factor: Scores. Rows missing from `grid` are treated as missing scores.
        labels: Forward returns by horizon.
        config: Evaluation options.
        grid: The bars of the evaluation window, in time order. Horizons count its rows.
        start: Inclusive start of the window.
        end: Exclusive end of the window.
        progress: Progress display for the bootstrap.

    Returns:
        The full-period, monthly, rolling and summary tables and the quantile response.
    """
    x = factor.reindex(grid)
    options = config.time_series
    month_starts = pd.date_range(start.normalize().replace(day=1), end, freq="MS", inclusive="left")
    window = pd.Timedelta(options.rolling_window)
    # Fixed steps after start, through end. A string freq would be read as a pandas offset alias,
    # which rejects durations such as "1 days" and anchors "1W" to Sundays.
    step = pd.Timedelta(options.rolling_step)
    endpoints = pd.date_range(start, end, freq=step, inclusive="right")
    positions = {asset: i for i, asset in enumerate(x.columns)}
    assets_all, monthly_all, rolling_all, summaries, quantiles = [], [], [], [], []
    for horizon, target in labels.items():
        y = target.reindex(index=grid, columns=x.columns)
        ends = label_endpoints(grid, horizon + config.delay)
        assets = _table([window_arrays(x, y, config, horizon, start, end, ends)])
        months, rolling = [], []
        for month in month_starts:
            boundary = month + pd.offsets.MonthBegin(1)
            months.append(
                window_arrays(
                    x,
                    y,
                    config,
                    horizon,
                    max(month, start),
                    min(boundary, end),
                    ends,
                    complete=month >= start and boundary <= end,
                )
            )
        for endpoint in endpoints:
            rolling.append(
                window_arrays(
                    x,
                    y,
                    config,
                    horizon,
                    max(start, endpoint - window),
                    endpoint,
                    ends,
                    complete=endpoint - window >= start,
                )
            )
        monthly = _table(months)
        monthly_all.extend(months)
        rolling_all.extend(rolling)
        # Remove only deterministic end-of-evaluation label exclusions, preserving interior gaps.
        mature = np.asarray(ends < end)
        intervals, aggregate = bootstrap_intervals(
            x.loc[mature], y.loc[mature], assets, config, horizon, progress
        )
        monthly_ic = {
            key: group.ic for key, group in monthly.groupby(["asset", "method"], sort=False)
        }
        # Original grid positions are kept in this dependence diagnostic.
        current = x.loc[mature].to_numpy(float)
        lagged = np.vstack([np.full((1, current.shape[1]), np.nan), current[:-1]])
        autocorrelation = {m: correlations(current, lagged, m) for m in METHODS}
        for row in assets.to_dict("records"):
            method, asset = row["method"], row["asset"]
            row.update(monthly_statistics(monthly_ic[asset, method], options.min_months))
            row.update(
                intervals.get(
                    (method, asset),
                    {
                        "ci95_lower": np.nan,
                        "ci95_upper": np.nan,
                        "bootstrap_valid": 0,
                        "bootstrap_status": aggregate[method]["bootstrap_status"],
                    },
                )
            )
            row["bootstrap_block_bars"] = aggregate[method]["bootstrap_block_bars"]
            row["signal_autocorr_lag1"] = autocorrelation[method][positions[asset]]
            assets_all.append(row)
        for method in METHODS:
            group = assets.loc[assets.method == method]
            valid = group.ic.dropna()
            by_month = monthly.loc[monthly.method == method].groupby("window_start").ic.mean()
            month_stats = monthly_statistics(by_month, options.min_months)
            summaries.append(
                {
                    "horizon": horizon,
                    "method": method,
                    "n_assets": len(valid),
                    "total_assets": len(group),
                    "mean": float(valid.mean()),
                    "median": float(valid.median()) if len(valid) else np.nan,
                    "q25": float(valid.quantile(0.25)) if len(valid) else np.nan,
                    "q75": float(valid.quantile(0.75)) if len(valid) else np.nan,
                    "positive_fraction": float((valid > 0).mean()) if len(valid) else np.nan,
                    "mean_pair_coverage": float(group.pair_coverage.mean()),
                    **{f"universe_{k}": v for k, v in month_stats.items()},
                    **aggregate[method],
                }
            )
        eligible_assets = assets.loc[(assets.method == "spearman") & assets.ic.notna(), "asset"]
        for asset in eligible_assets:
            scores = x.loc[mature, asset].to_numpy(float)[None, :]
            returns = y.loc[mature, asset].to_numpy(float)[None, :]
            means, counts, usable = bucket_means(scores, returns, config.quantiles)
            if usable[0]:
                quantiles.extend(
                    {
                        "asset": asset,
                        "horizon": horizon,
                        "quantile": q + 1,
                        "mean_return": float(means[0, q]),
                        "n_pairs": int(counts[0, q]),
                    }
                    for q in range(config.quantiles)
                )
    return TimeSeriesEvaluation(
        pd.DataFrame(assets_all),
        _table(monthly_all),
        _table(rolling_all),
        pd.DataFrame(summaries),
        pd.DataFrame(quantiles, columns=["asset", "horizon", "quantile", "mean_return", "n_pairs"]),
    )
