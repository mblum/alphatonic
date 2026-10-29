"""Chart specifications for the cross-sectional part of a tearsheet, and what all charts share.

A specification is plain data: what to draw, with every number already computed. The page draws it
with `static/alphatonic.js`, which knows five kinds: `lines`, `heatmap`, `bars`, `intervals` and
`rolling`. A spec names colours as slots of the page's palette (`--at-c1` to `--at-c8` in
`static/alphatonic.css`), never as colour values, so the stylesheet decides them for the light and
the dark theme alike.
"""

from __future__ import annotations

from typing import Any, cast

import numpy as np
import pandas as pd

from alphatonic.config import ReportOptions

Spec = dict[str, Any]

BLUE, ORANGE, AQUA = 1, 2, 3
"""The first palette slots, in fixed order: royal blue (the page's accent), orange, aqua."""
CONTEXT = "context"
"""A muted grey for lines that give context to a series, like the raw IC under its mean."""
STATUSES = (
    "valid",
    "constant_signal",
    "constant_returns",
    "insufficient_assets",
    "low_coverage",
)
"""Sample statuses in the order they stack and take palette slots, so that a status keeps its colour
in every chart and every evaluation. Statuses not listed follow, in alphabetical order."""
DECIMALS = 6
"""Values are rounded to this many decimals in a spec: far below what a chart can show, and about a
third of the bytes of a full-precision float."""


def bar_count(horizon: int) -> str:
    """Name a horizon in bars, such as `1 bar` or `24 bars`."""
    return f"{int(horizon)} {'bar' if horizon == 1 else 'bars'}"


def span(seconds: float) -> str:
    """Name a duration in its largest whole unit, such as `1h` or `15min`."""
    for unit, size in (("d", 86400), ("h", 3600), ("min", 60)):
        if seconds % size == 0:
            return f"{int(seconds // size)}{unit}"
    return f"{seconds:g}s"


def horizon_label(horizon: int, bar: pd.Timedelta | None = None) -> str:
    """Name a horizon in bars, adding its duration when the bars are evenly spaced."""
    if bar is None:
        return bar_count(horizon)
    return f"{bar_count(horizon)} · {span(bar.total_seconds() * int(horizon))}"


def values(series: pd.Series | np.ndarray | list) -> list:
    """List finite values as rounded floats and everything else as `None` (JSON null).

    A value that is missing stays missing: the charts leave a gap, never a zero.
    """
    return [
        round(float(value), DECIMALS) if pd.notna(value) and np.isfinite(value) else None
        for value in series
    ]


def counts(series: pd.Series | np.ndarray | list) -> list:
    """List counts as integers, and anything that is not a number as `None`."""
    return [int(value) if pd.notna(value) and np.isfinite(value) else None for value in series]


def milliseconds(timestamps: pd.Series | pd.Index) -> list[int]:
    """List timestamps as milliseconds since the epoch, UTC. A timestamp without a zone is UTC."""
    index = pd.DatetimeIndex(pd.to_datetime(timestamps, utc=True))
    since_epoch = index - pd.Timestamp(0, tz="UTC")
    return cast("list[int]", (since_epoch // pd.Timedelta(milliseconds=1)).tolist())


def status_slots(statuses: list[str]) -> dict[str, int]:
    """Give each status its palette slot: a fixed one if it is known, the next free ones if not.

    A status keeps its colour whichever other statuses are present: colour follows the status,
    never its rank among them. Statuses beyond the eighth slot share the last.
    """
    unknown = sorted(status for status in statuses if status not in STATUSES)
    return {
        status: (
            STATUSES.index(status) + 1
            if status in STATUSES
            else min(len(STATUSES) + 1 + unknown.index(status), 8)
        )
        for status in statuses
    }


def status_order(statuses: list[str]) -> list[str]:
    """Order statuses as they stack: the known ones first, in `STATUSES` order, then the rest."""
    return sorted(statuses, key=lambda s: (STATUSES.index(s), s) if s in STATUSES else (99, s))


def method_figures(
    periods: pd.DataFrame,
    method: str,
    bar: pd.Timedelta | None,
    options: ReportOptions,
) -> dict[str, Spec]:
    """Specify the charts of one correlation method without recalculating any statistic."""
    horizons = sorted(periods.horizon.unique())
    labels = [horizon_label(h, bar) for h in horizons]
    groups = [periods.loc[periods.horizon == h].set_index("timestamp") for h in horizons]
    window = pd.Timedelta(options.rolling_window)
    panels: list[Spec] = []
    monthly_means, monthly_counts = [], []
    months = pd.date_range(
        periods.timestamp.min().normalize().replace(day=1),
        periods.timestamp.max().normalize().replace(day=1),
        freq="MS",
    )
    for label, group in zip(labels, groups, strict=True):
        series = group[method]
        observed = series.rolling(window, min_periods=1).count()
        # Mask current missing observations so smoothing cannot hide evaluation gaps.
        rolling = (
            series.rolling(window, min_periods=options.min_periods).mean().where(series.notna())
        )
        detail = [{"name": "Window observations", "values": counts(observed), "format": "d"}]
        panels.append(
            {
                "title": label,
                "height": 200,
                "x": milliseconds(group.index),
                "reference": 0,
                "empty": None if series.notna().any() else "No valid cross-sectional observations",
                "y": {"label": "Spearman IC", "domain": [-1.05, 1.05], "format": ".2~f"},
                "series": [
                    {
                        "name": "Spearman IC",
                        "color": CONTEXT,
                        "width": 1,
                        "y": values(series),
                        "columns": detail,
                    },
                    {
                        "name": f"{options.rolling_window} rolling mean",
                        "color": BLUE,
                        "width": 2,
                        "y": values(rolling),
                        "columns": detail,
                    },
                ],
            }
        )
        monthly = series.resample("MS").agg(["mean", "count"]).reindex(months)
        monthly_means.append(values(monthly["mean"]))
        monthly_counts.append(counts(monthly["count"].fillna(0)))
    return {
        "timeseries": {
            "kind": "lines",
            "label": "Cross-sectional IC time series",
            "x": {"type": "utc", "label": "Timestamp (UTC)"},
            "columns": 1,
            "legend": [
                {"name": "Spearman IC", "color": CONTEXT, "width": 1},
                {"name": f"{options.rolling_window} rolling mean", "color": BLUE, "width": 2},
            ],
            "panels": panels,
        },
        "monthly": {
            "kind": "heatmap",
            "label": "Cross-sectional monthly mean IC",
            "months": months.strftime("%Y-%m").tolist(),
            "rows": labels,
            "z": monthly_means,
            "counts": monthly_counts,
            "tip": {"value": "Mean Spearman IC", "count": "Valid periods", "first": "month"},
        },
    }


def coverage_figures(periods: pd.DataFrame, bar: pd.Timedelta | None) -> dict[str, Spec]:
    """Specify the asset-count, pair-coverage and status charts shared by all methods."""
    horizons = sorted(periods.horizon.unique())
    panels: list[Spec] = []
    for horizon in horizons:
        group = periods.loc[periods.horizon == horizon]
        label, when = horizon_label(horizon, bar), milliseconds(group.timestamp)
        panels.append(
            {
                "title": f"{label} · Asset counts",
                "height": 180,
                "x": when,
                "reference": None,
                "empty": None,
                "y": {"label": None, "zero": True},
                "series": [
                    {"name": name, "color": slot, "y": values(group[column])}
                    for column, name, slot in (
                        ("n_available", "Available", BLUE),
                        ("n_signal", "Scored", ORANGE),
                        ("n_pairs", "Paired", AQUA),
                    )
                ],
            }
        )
        panels.append(
            {
                "title": f"{label} · Pair coverage",
                "height": 180,
                "x": when,
                "reference": None,
                "empty": None,
                "y": {"label": None, "domain": [0, 1.05], "format": ".0%", "tip": ".1%"},
                "series": [{"name": "Coverage", "color": BLUE, "y": values(group.pair_coverage)}],
            }
        )
    statuses = periods.groupby(["horizon", "status"]).size().unstack(fill_value=0)
    names = status_order([str(status) for status in statuses.columns])
    slots = status_slots(names)
    return {
        "coverage": {
            "kind": "lines",
            "label": "Cross-sectional coverage time series",
            "x": {"type": "utc", "label": None},
            "columns": 2,
            "legend": [
                {"name": name, "color": slot}
                for name, slot in (("Available", BLUE), ("Scored", ORANGE), ("Paired", AQUA))
            ],
            "panels": panels,
        },
        "statuses": {
            "kind": "bars",
            "label": "Cross-sectional sample status",
            "height": 340,
            "categories": [horizon_label(h, bar) for h in statuses.index],
            "x": {"label": None},
            "y": {"label": "Evaluation periods"},
            "totals": True,
            "series": [
                {
                    "name": status.replace("_", " "),
                    "color": slots[status],
                    "values": counts(statuses[status]),
                }
                for status in names
            ],
        },
    }


def quantile_figure(
    frame: pd.DataFrame, *, unit: str, quantiles: int, vol_scaled: bool = False
) -> Spec:
    """Specify the mean target of each score bucket, one line per horizon.

    Returns are drawn in basis points; vol-scaled returns in multiples of the volatility of a
    return over the horizon.
    """
    scale, tip, axis, suffix = (
        (1, ".3f", "Mean vol-scaled return (σ)", " σ")
        if vol_scaled
        else (10000, ".2f", "Mean forward return (bps)", " bps")
    )
    buckets = list(range(1, quantiles + 1))
    series: list[Spec] = []
    for i, (horizon, group) in enumerate(frame.groupby("horizon")):
        # Each asset (TS) or timestamp (CS) contributes equally within each occupied bin.
        summary = (
            group.groupby("quantile")
            .agg(
                mean_return=("mean_return", "mean"),
                n_pairs=("n_pairs", "sum"),
                n_units=("mean_return", "count"),
            )
            .reindex(buckets)
        )
        series.append(
            {
                "name": bar_count(cast(int, horizon)),
                "color": i + 1,
                "markers": True,
                "y": values(summary.mean_return * scale),
                "columns": [
                    {"name": "Pairs", "values": counts(summary.n_pairs.fillna(0)), "format": "d"},
                    {"name": unit, "values": counts(summary.n_units.fillna(0)), "format": "d"},
                ],
            }
        )
    return {
        "kind": "lines",
        "label": "Mean target by signal quantile",
        "x": {
            "type": "linear",
            "label": f"Signal quantile (1–{quantiles})",
            "ticks": buckets,
            "tip": "Quantile",
        },
        "columns": 1,
        "legend": [
            {"name": item["name"], "color": item["color"], "shape": "dot"} for item in series
        ],
        "panels": [
            {
                "title": None,
                "height": 340,
                "x": buckets,
                "reference": 0,
                "empty": None,
                "y": {"label": axis, "tip": tip, "unit": suffix},
                "series": series,
            }
        ],
    }
