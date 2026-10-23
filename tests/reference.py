"""Straightforward reference implementations used to check the optimized code.

These follow the original, timestamp-by-timestamp and window-by-window formulation, on a
regular clock grid. They are slow and exist only so tests can assert that the vectorized
implementations compute the same tables.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from alphatonic.config import METHODS, EvaluationConfig
from alphatonic.stats import ZERO_TOLERANCE, correlations, summarize_ic
from alphatonic.time_series import bootstrap_intervals, monthly_statistics


def snap(value: float) -> float:
    return 0.0 if abs(value) < ZERO_TOLERANCE else value


def quantile_rows(x: pd.Series, y: pd.Series, quantiles: int = 5) -> list[dict]:
    valid = np.isfinite(x) & np.isfinite(y)
    x, y = x[valid], y[valid]
    if x.nunique() < 2:
        return []
    bins = np.ceil(x.rank(method="average", pct=True) * quantiles).astype(int)
    return [
        {
            "quantile": q,
            "mean_return": float(y[bins == q].mean()),
            "n_pairs": int((bins == q).sum()),
        }
        for q in range(1, quantiles + 1)
    ]


def cross_sectional(
    factor: pd.DataFrame,
    labels: dict[int, pd.DataFrame],
    prices: pd.DataFrame,
    config: EvaluationConfig,
):
    records, quantiles = [], []
    available = prices.notna().sum(axis=1)
    for horizon in config.horizons:
        for timestamp in factor.index:
            score = factor.loc[timestamp]
            target = labels[horizon].loc[timestamp]
            valid = np.isfinite(score) & np.isfinite(target)
            count = int(valid.sum())
            rank_ic = linear_ic = np.nan
            status = "insufficient_assets"
            if config.mode == "time_series":
                status = "disabled"
            elif count >= config.min_assets:
                x, y = score[valid], target[valid]
                if x.nunique() < 2:
                    status = "constant_signal"
                elif y.nunique() < 2:
                    status = "constant_returns"
                else:
                    rank_ic = snap(float(x.rank().corr(y.rank())))
                    linear_ic = snap(float(x.corr(y)))
                    status = "valid"
                    quantiles.extend(
                        {"timestamp": timestamp, "horizon": horizon, **row}
                        for row in quantile_rows(x, y, config.quantiles)
                    )
            n_available = int(available.loc[timestamp])
            records.append(
                {
                    "timestamp": timestamp,
                    "horizon": horizon,
                    "spearman": rank_ic,
                    "pearson": linear_ic,
                    "n_available": n_available,
                    "n_signal": int(score.notna().sum()),
                    "n_pairs": count,
                    "pair_coverage": count / n_available if n_available else np.nan,
                    "status": status,
                }
            )
    periods = pd.DataFrame(records)
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
    response = pd.DataFrame(
        quantiles, columns=["timestamp", "horizon", "quantile", "mean_return", "n_pairs"]
    )
    return periods, pd.DataFrame(summaries), response


def window_records(
    x: pd.DataFrame,
    y: pd.DataFrame,
    config: EvaluationConfig,
    horizon: int,
    start: pd.Timestamp,
    end: pd.Timestamp,
    duration: pd.Timedelta,
    *,
    complete: bool = True,
) -> list[dict]:
    span = (horizon + config.delay) * duration
    in_window = (x.index >= start) & (x.index < end)
    eligible = in_window & (x.index + span < end)
    scores, returns = x.loc[eligible], y.loc[eligible]
    finite = np.isfinite(scores) & np.isfinite(returns)
    counts = finite.sum()
    expected = int(eligible.sum())
    coverage = counts / expected if expected else counts * 0.0
    options = config.time_series
    duration_ok = end - start >= options.min_horizons * horizon * duration
    values = {m: correlations(scores.to_numpy(), returns.to_numpy(), m) for m in METHODS}
    records = []
    for i, asset in enumerate(x.columns):
        valid = finite[asset]
        sx, sy = scores.loc[valid, asset], returns.loc[valid, asset]
        status = "valid"
        if not complete:
            status = "partial_window"
        elif not duration_ok:
            status = "short_window"
        elif counts[asset] < options.min_pairs:
            status = "insufficient_pairs"
        elif coverage[asset] < options.min_coverage:
            status = "low_coverage"
        elif sx.nunique() < 2:
            status = "constant_signal"
        elif sy.nunique() < 2:
            status = "constant_returns"
        for method in METHODS:
            records.append(
                {
                    "asset": asset,
                    "horizon": horizon,
                    "method": method,
                    "window_start": start,
                    "window_end": end,
                    "complete": complete,
                    "n_expected": expected,
                    "n_pairs": int(counts[asset]),
                    "boundary_excluded": int(in_window.sum()) - expected,
                    "pair_coverage": float(coverage[asset]),
                    "status": status,
                    "first_pair": sx.index[0] if len(sx) else pd.NaT,
                    "last_pair": sx.index[-1] if len(sx) else pd.NaT,
                    "ic": float(values[method][i]) if status == "valid" else np.nan,
                }
            )
    return records


def time_series(
    factor: pd.DataFrame,
    labels: dict[int, pd.DataFrame],
    config: EvaluationConfig,
    duration: pd.Timedelta,
    start: pd.Timestamp,
    end: pd.Timestamp,
):
    """The original evaluation: clock arithmetic on a regular grid, one asset at a time."""
    grid = pd.date_range(start, end, freq=duration, inclusive="left")
    x = factor.reindex(grid)
    month_starts = pd.date_range(start.normalize().replace(day=1), end, freq="MS", inclusive="left")
    options = config.time_series
    window = pd.Timedelta(options.rolling_window)
    step = pd.Timedelta(options.rolling_step)
    endpoints = pd.date_range(start, end, freq=step, inclusive="right")
    assets_all, monthly_all, rolling_all, summaries, quantiles = [], [], [], [], []
    for horizon, target in labels.items():
        y = target.reindex(index=grid, columns=x.columns)
        assets = pd.DataFrame(window_records(x, y, config, horizon, start, end, duration))
        months, rolling = [], []
        for month in month_starts:
            boundary = month + pd.offsets.MonthBegin(1)
            months.extend(
                window_records(
                    x,
                    y,
                    config,
                    horizon,
                    max(month, start),
                    min(boundary, end),
                    duration,
                    complete=month >= start and boundary <= end,
                )
            )
        for endpoint in endpoints:
            rolling.extend(
                window_records(
                    x,
                    y,
                    config,
                    horizon,
                    max(start, endpoint - window),
                    endpoint,
                    duration,
                    complete=endpoint - window >= start,
                )
            )
        monthly = pd.DataFrame(months)
        monthly_all.extend(months)
        rolling_all.extend(rolling)
        mature = x.index + (horizon + config.delay) * duration < end
        intervals, aggregate = bootstrap_intervals(
            x.loc[mature], y.loc[mature], assets, config, horizon
        )
        for row in assets.to_dict("records"):
            method, asset = row["method"], row["asset"]
            group = monthly.loc[(monthly.asset == asset) & (monthly.method == method)]
            row.update(monthly_statistics(group.ic, options.min_months))
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
            sx = x.loc[mature, asset]
            row["signal_autocorr_lag1"] = correlations(
                sx.to_numpy()[:, None], sx.shift(1).to_numpy()[:, None], method
            )[0]
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
        for asset in assets.loc[(assets.method == "spearman") & assets.ic.notna(), "asset"]:
            quantiles.extend(
                {"asset": asset, "horizon": horizon, **q}
                for q in quantile_rows(x.loc[mature, asset], y.loc[mature, asset], config.quantiles)
            )
    return {
        "assets": pd.DataFrame(assets_all),
        "monthly": pd.DataFrame(monthly_all),
        "rolling": pd.DataFrame(rolling_all),
        "summary": pd.DataFrame(summaries),
        "quantiles": pd.DataFrame(
            quantiles, columns=["asset", "horizon", "quantile", "mean_return", "n_pairs"]
        ),
    }
