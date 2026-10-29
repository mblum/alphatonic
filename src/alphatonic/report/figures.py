"""Plotly figures for the cross-sectional part of a tearsheet."""

from __future__ import annotations

from typing import cast

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots

from alphatonic.config import ReportOptions

COLORS = ("#4169e1", "#eb6834", "#199e70")
"""Series colours in fixed order: royal blue (the page's accent), orange, aqua. Checked for
lightness, chroma, colour-vision-deficiency separation and contrast on a light surface."""
INK = "#373c44"
"""The page's text colour (Pico's), so that charts read as part of it."""
FONT = dict(family='system-ui, "Segoe UI", Roboto, Helvetica, Arial, sans-serif', color=INK)
"""The page's font and text colour."""
CONTEXT = "#a8b7c5"
"""Lines that give context to a series: the raw IC under its rolling mean, confidence intervals."""
REFERENCE = "#94a3b8"
"""Reference lines in the plot of confidence intervals."""
ZERO = "#2a3f5f"
"""The dotted line at zero (the shape colour of Plotly's white template)."""
POLES = ("#b45b3e", "#f0efec")
"""The negative pole and the neutral middle of the diverging scale."""
SCALE = [[0, POLES[0]], [0.5, POLES[1]], [1, COLORS[0]]]
"""Diverging scale of correlations: red below zero, neutral grey at zero, royal blue above."""
MODEBAR = ("rgba(68, 68, 68, 0.3)", "rgba(68, 68, 68, 0.7)")
"""The toolbar's icons, resting and active. Plotly's own light defaults, set so that they can be
replaced on a dark page."""

DARK_COLORS = ("#6a8cf0", "#d95926", "#199e70")
"""The series colours stepped for the dark page: the same hues, with blue lightened and orange
deepened to stay inside the lightness band of a dark surface. Checked as `COLORS` are, against the
card colour (`#181c25`) and the page colour (`#13171f`) of Pico's dark theme."""
DARK = {
    INK: "#c2c7d0",
    CONTEXT: "#5d6b7e",
    REFERENCE: "#7b8495",
    ZERO: "#9aa3b2",
    POLES[0]: "#d4694a",
    POLES[1]: "#2f343f",
    MODEBAR[0]: "rgba(194, 199, 208, 0.45)",
    MODEBAR[1]: "rgba(194, 199, 208, 0.9)",
    **dict(zip(COLORS, DARK_COLORS, strict=True)),
}
"""The dark counterpart of every colour written into a figure. The page redraws its charts on a
dark system by replacing each of these, and Plotly's white template by its dark one, in the figure
as written here. Every colour a figure sets explicitly must be a key: `tests/test_report.py`
checks. The ink and the greys are Pico's dark text, muted and border tones."""


def dark_theme() -> dict:
    """Return what the page needs to redraw its charts on a dark system, as JSON-ready data.

    Returns:
        The colour replacements (`colors`) and Plotly's dark `template`.
    """
    return {"colors": DARK, "template": pio.templates["plotly_dark"].to_plotly_json()}


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


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    """Apply the shared look of the tearsheet charts."""
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=55, r=25, t=45, b=55),
        font=dict(FONT, size=12),
        colorway=list(COLORS),
        legend=dict(orientation="h", y=-0.15),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        modebar=dict(bgcolor="rgba(0,0,0,0)", color=MODEBAR[0], activecolor=MODEBAR[1]),
    )
    return fig


def values(series: pd.Series) -> list:
    """List finite values as floats and everything else as `None`, which JSON writes as null."""
    return [float(value) if pd.notna(value) and np.isfinite(value) else None for value in series]


def method_figures(
    periods: pd.DataFrame,
    method: str,
    bar: pd.Timedelta | None,
    options: ReportOptions,
) -> dict[str, go.Figure]:
    """Build the charts of one correlation method without recalculating any statistic."""
    horizons = sorted(periods.horizon.unique())
    labels = [horizon_label(h, bar) for h in horizons]
    groups = [periods.loc[periods.horizon == h].set_index("timestamp") for h in horizons]
    window = pd.Timedelta(options.rolling_window)
    timeseries = make_subplots(rows=len(horizons), cols=1, subplot_titles=labels)
    monthly_means, monthly_counts = [], []
    months = pd.date_range(
        periods.timestamp.min().normalize().replace(day=1),
        periods.timestamp.max().normalize().replace(day=1),
        freq="MS",
    )
    for i, group in enumerate(groups):
        series = group[method]
        counts = series.rolling(window, min_periods=1).count()
        # Mask current missing observations so smoothing cannot hide evaluation gaps.
        rolling = (
            series.rolling(window, min_periods=options.min_periods).mean().where(series.notna())
        )
        dates = [value.isoformat() for value in group.index]
        for name, line, color in (
            ("Spearman IC", series, CONTEXT),
            (f"{options.rolling_window} rolling mean", rolling, COLORS[0]),
        ):
            timeseries.add_trace(
                go.Scatter(
                    x=dates,
                    y=values(line),
                    name=name,
                    legendgroup=name,
                    showlegend=i == 0,
                    mode="lines",
                    connectgaps=False,
                    line=dict(color=color, width=1 if name == "Spearman IC" else 2),
                    customdata=counts.tolist(),
                    hovertemplate=(
                        "%{x}<br>Spearman IC: %{y:.3f}<br>Window observations: %{customdata}"
                        "<extra>%{fullData.name}</extra>"
                    ),
                ),
                row=i + 1,
                col=1,
            )
        # Plotly accepts integer subplot coordinates; its inferred types only allow "all".
        timeseries.add_hline(
            y=0,
            line_dash="dot",
            line_color=ZERO,
            row=i + 1,  # pyright: ignore[reportArgumentType]
            col=1,  # pyright: ignore[reportArgumentType]
        )
        timeseries.update_yaxes(title_text="Spearman IC", range=[-1.05, 1.05], row=i + 1, col=1)
        if not series.notna().any():
            timeseries.add_annotation(
                text="No valid cross-sectional observations",
                x=0.5,
                y=0.5,
                xref="x domain",
                yref="y domain",
                showarrow=False,
                row=i + 1,
                col=1,
            )
        monthly = series.resample("MS").agg(["mean", "count"]).reindex(months)
        monthly_means.append(values(monthly["mean"]))
        monthly_counts.append(monthly["count"].fillna(0).astype(int).tolist())
    timeseries.update_xaxes(title_text="Timestamp (UTC)", row=len(horizons), col=1)
    monthly = go.Figure(
        go.Heatmap(
            x=months.strftime("%Y-%m").tolist(),
            y=labels,
            z=monthly_means,
            customdata=monthly_counts,
            zmin=-1,
            zmax=1,
            colorscale=SCALE,
            colorbar=dict(title="Mean<br>Spearman IC"),
            hoverongaps=False,
            hovertemplate=(
                "%{x}<br>%{y}<br>Mean Spearman IC: %{z:.3f}"
                "<br>Valid periods: %{customdata}<extra></extra>"
            ),
        )
    )
    monthly.update_xaxes(type="category")
    monthly.update_yaxes(autorange="reversed")
    return {
        "timeseries": style(timeseries, 240 * len(horizons) + 100),
        "monthly": style(monthly, max(300, 65 * len(horizons) + 120)),
    }


def coverage_figures(periods: pd.DataFrame, bar: pd.Timedelta | None) -> dict[str, go.Figure]:
    """Build the asset-count, pair-coverage and status charts shared by all methods."""
    horizons = sorted(periods.horizon.unique())
    coverage = make_subplots(
        rows=len(horizons),
        cols=2,
        subplot_titles=[
            f"{horizon_label(h, bar)} · {kind}"
            for h in horizons
            for kind in ("Asset counts", "Pair coverage")
        ],
    )
    for i, horizon in enumerate(horizons):
        group = periods.loc[periods.horizon == horizon]
        dates = [value.isoformat() for value in group.timestamp]
        for name, label, color in zip(
            ("n_available", "n_signal", "n_pairs"),
            ("Available", "Scored", "Paired"),
            COLORS,
            strict=True,
        ):
            coverage.add_trace(
                go.Scatter(
                    x=dates,
                    y=values(group[name]),
                    name=label,
                    legendgroup=label,
                    showlegend=i == 0,
                    mode="lines",
                    line=dict(color=color),
                    connectgaps=False,
                ),
                row=i + 1,
                col=1,
            )
        coverage.add_trace(
            go.Scatter(
                x=dates,
                y=values(group.pair_coverage),
                name="Pair coverage",
                showlegend=False,
                mode="lines",
                line=dict(color=COLORS[0]),
                connectgaps=False,
                hovertemplate="%{x}<br>Coverage: %{y:.1%}<extra></extra>",
            ),
            row=i + 1,
            col=2,
        )
        coverage.update_yaxes(rangemode="tozero", row=i + 1, col=1)
        coverage.update_yaxes(range=[0, 1.05], tickformat=".0%", row=i + 1, col=2)
    statuses = periods.groupby(["horizon", "status"]).size().unstack(fill_value=0)
    reasons = go.Figure()
    for status in statuses.columns:
        reasons.add_bar(
            name=status.replace("_", " "),
            x=[horizon_label(h, bar) for h in statuses.index],
            y=statuses[status].tolist(),
        )
    reasons.update_layout(barmode="stack", yaxis_title="Evaluation periods")
    return {
        "coverage": style(coverage, 230 * len(horizons) + 100),
        "statuses": style(reasons),
    }


def quantile_figure(
    frame: pd.DataFrame, *, unit: str, quantiles: int, vol_scaled: bool = False
) -> go.Figure:
    """Chart the mean target of each score bucket, one line per horizon.

    Returns are drawn in basis points; vol-scaled returns in multiples of the volatility of a
    return over the horizon.
    """
    scale, value, axis = (
        (1, "%{y:.3f} σ", "Mean vol-scaled return (σ)")
        if vol_scaled
        else (10000, "%{y:.2f} bps", "Mean forward return (bps)")
    )
    fig = go.Figure()
    buckets = list(range(1, quantiles + 1))
    for horizon, group in frame.groupby("horizon"):
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
        fig.add_trace(
            go.Scatter(
                x=buckets,
                y=values(summary.mean_return * scale),
                mode="lines+markers",
                name=bar_count(cast(int, horizon)),
                connectgaps=False,
                customdata=summary[["n_pairs", "n_units"]].fillna(0).to_numpy().tolist(),
                hovertemplate=(
                    f"Quantile %{{x}}<br>Mean: {value}"
                    f"<br>Pairs: %{{customdata[0]}}<br>{unit}: %{{customdata[1]}}"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )
    fig.add_hline(y=0, line_dash="dot", line_color=ZERO)
    fig.update_xaxes(title=f"Signal quantile (1–{quantiles})", dtick=1)
    fig.update_yaxes(title=axis)
    return style(fig)
