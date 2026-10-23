"""Plotly figures for the cross-sectional part of a tearsheet."""

from __future__ import annotations

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from alphatonic.config import ReportOptions
from alphatonic.stats import correlations

COLORS = ("#146b70", "#cf7841", "#64748b")
SCALE = [[0, "#b45b3e"], [0.5, "#f4f3ef"], [1, COLORS[0]]]


def bar_count(horizon: int) -> str:
    """Name a horizon in bars, such as `1 bar` or `24 bars`."""
    return f"{int(horizon)} {'bar' if horizon == 1 else 'bars'}"


def _span(seconds: float) -> str:
    for unit, size in (("d", 86400), ("h", 3600), ("min", 60)):
        if seconds % size == 0:
            return f"{int(seconds // size)}{unit}"
    return f"{seconds:g}s"


def horizon_label(horizon: int, bar: pd.Timedelta | None = None) -> str:
    """Name a horizon in bars, adding its duration when the bars are evenly spaced."""
    if bar is None:
        return bar_count(horizon)
    return f"{bar_count(horizon)} · {_span(bar.total_seconds() * int(horizon))}"


def style(fig: go.Figure, height: int = 360) -> go.Figure:
    """Apply the shared look of the tearsheet charts."""
    fig.update_layout(
        template="plotly_white",
        height=height,
        margin=dict(l=55, r=25, t=45, b=55),
        font=dict(family="Arial, sans-serif", color="#243447", size=12),
        colorway=list(COLORS),
        legend=dict(orientation="h", y=-0.15),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def values(series: pd.Series) -> list:
    """List finite values as floats and everything else as `None`, which JSON writes as null."""
    return [float(value) if pd.notna(value) and np.isfinite(value) else None for value in series]


def method_figures(
    periods: pd.DataFrame,
    summary: pd.DataFrame,
    method: str,
    bar: pd.Timedelta | None,
    options: ReportOptions,
) -> dict[str, go.Figure]:
    """Build the charts of one correlation method without recalculating any statistic."""
    horizons = sorted(periods.horizon.unique())
    labels = [horizon_label(h, bar) for h in horizons]
    groups = [periods.loc[periods.horizon == h].set_index("timestamp") for h in horizons]
    window = pd.Timedelta(options.rolling_window)
    stats = summary.loc[summary.method == method].set_index("horizon").reindex(horizons)
    means = stats.get("mean", pd.Series(np.nan, index=stats.index))
    lower = stats.get("ci95_lower", pd.Series(np.nan, index=stats.index))
    upper = stats.get("ci95_upper", pd.Series(np.nan, index=stats.index))
    comparison = go.Figure(
        go.Scatter(
            x=labels,
            y=values(means),
            mode="markers",
            marker=dict(size=11, color=COLORS[0]),
            error_y=dict(
                type="data",
                symmetric=False,
                array=values(upper - means),
                arrayminus=values(means - lower),
            ),
            hovertemplate="%{x}<br>Mean IC: %{y:.4f}<extra></extra>",
        )
    )
    comparison.add_hline(y=0, line_dash="dot", line_color="#94a3b8")
    comparison.update_yaxes(title_text="Mean IC / HAC 95% interval")

    timeseries = make_subplots(rows=len(horizons), cols=1, subplot_titles=labels)
    distribution = make_subplots(rows=len(horizons), cols=1, subplot_titles=labels)
    dependence = go.Figure()
    monthly_means, monthly_counts = [], []
    months = pd.date_range(
        periods.timestamp.min().normalize().replace(day=1),
        periods.timestamp.max().normalize().replace(day=1),
        freq="MS",
    )
    for i, group in enumerate(groups):
        series = group[method]
        lags = list(range(1, min(48, max(1, len(series) // 4)) + 1))
        dependence.add_trace(
            go.Scatter(
                x=lags,
                y=values(
                    pd.Series(
                        [
                            correlations(
                                series.to_numpy()[:, None],
                                series.shift(lag).to_numpy()[:, None],
                                "pearson",
                            )[0]
                            for lag in lags
                        ]
                    )
                ),
                name=labels[i],
                mode="lines+markers",
                connectgaps=False,
            )
        )
        counts = series.rolling(window, min_periods=1).count()
        # Mask current missing observations so smoothing cannot hide evaluation gaps.
        rolling = (
            series.rolling(window, min_periods=options.min_periods).mean().where(series.notna())
        )
        dates = [value.isoformat() for value in group.index]
        for name, line, color in (
            ("IC", series, "#a8b7c5"),
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
                    line=dict(color=color, width=1 if name == "IC" else 2),
                    customdata=counts.tolist(),
                    hovertemplate=(
                        "%{x}<br>IC: %{y:.4f}<br>Window observations: %{customdata}"
                        "<extra>%{fullData.name}</extra>"
                    ),
                ),
                row=i + 1,
                col=1,
            )
        timeseries.add_hline(y=0, line_dash="dot", row=i + 1, col=1)
        timeseries.update_yaxes(title_text="IC", range=[-1.05, 1.05], row=i + 1, col=1)
        distribution.add_trace(
            go.Histogram(
                x=series.dropna().tolist(),
                xbins=dict(start=-1.05, end=1.05, size=0.1),
                marker_color=COLORS[0],
                showlegend=False,
                hovertemplate="IC: %{x}<br>Observations: %{y}<extra></extra>",
            ),
            row=i + 1,
            col=1,
        )
        if not series.notna().any():
            for figure in (timeseries, distribution):
                figure.add_annotation(
                    text="No valid IC periods",
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
    distribution.update_xaxes(title_text="IC", range=[-1.05, 1.05])
    distribution.update_yaxes(title_text="Observations")
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
            colorbar=dict(title="Mean IC"),
            hoverongaps=False,
            hovertemplate=(
                "%{x}<br>%{y}<br>Mean IC: %{z:.4f}<br>Valid periods: %{customdata}<extra></extra>"
            ),
        )
    )
    monthly.update_xaxes(type="category")
    monthly.update_yaxes(autorange="reversed")
    dependence.add_hline(y=0, line_dash="dot")
    dependence.update_xaxes(title_text="Lag (bars)")
    dependence.update_yaxes(title_text="IC autocorrelation", range=[-1.05, 1.05])
    return {
        "comparison": style(comparison),
        "timeseries": style(timeseries, 240 * len(horizons) + 100),
        "monthly": style(monthly, max(300, 65 * len(horizons) + 120)),
        "distribution": style(distribution, 220 * len(horizons) + 100),
        "dependence": style(dependence),
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


def quantile_figure(frame: pd.DataFrame, *, unit: str, quantiles: int) -> go.Figure:
    """Chart the mean forward return of each score bucket, one line per horizon."""
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
                y=values(summary.mean_return * 10000),
                mode="lines+markers",
                name=bar_count(horizon),
                connectgaps=False,
                customdata=summary[["n_pairs", "n_units"]].fillna(0).to_numpy().tolist(),
                hovertemplate=(
                    "Bucket %{x}<br>Mean return: %{y:.2f} bps"
                    f"<br>Pairs: %{{customdata[0]}}<br>{unit}: %{{customdata[1]}}"
                    "<extra>%{fullData.name}</extra>"
                ),
            )
        )
    fig.add_hline(y=0, line_dash="dot")
    fig.update_xaxes(title=f"Score bucket of {quantiles} (lowest → highest)", dtick=1)
    fig.update_yaxes(title="Mean forward return (bps)")
    return style(fig)
