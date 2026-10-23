"""Plotly figures for the time-series part of a tearsheet, drawn from stored tables."""

from __future__ import annotations

import pandas as pd
import plotly.graph_objects as go

from alphatonic.report.figures import COLORS, SCALE, bar_count, quantile_figure, style, values
from alphatonic.time_series import TimeSeriesEvaluation


def confidence_plot(frame: pd.DataFrame, labels: list[str], column: str) -> go.Figure:
    """Chart a point estimate per label with its bootstrap interval."""
    fig = go.Figure()
    xs, ys = [], []
    for label, row in zip(labels, frame.to_dict("records"), strict=True):
        xs.extend([row.get("ci95_lower"), row.get("ci95_upper"), None])
        ys.extend([label, label, None])
    fig.add_trace(
        go.Scatter(
            x=xs,
            y=ys,
            mode="lines",
            name="Block-bootstrap 95% interval",
            line=dict(color="#a8b7c5", width=3),
            connectgaps=False,
        )
    )
    fig.add_trace(
        go.Scatter(
            x=values(frame[column]),
            y=labels,
            mode="markers",
            name="IC",
            marker=dict(color=COLORS[0], size=9),
            hovertemplate="%{y}<br>IC: %{x:.4f}<extra></extra>",
        )
    )
    fig.add_vline(x=0, line_dash="dot", line_color="#94a3b8")
    fig.update_xaxes(title="IC", range=[-1.05, 1.05])
    fig.update_yaxes(type="category", autorange="reversed")
    return _style(fig, max(350, 25 * len(frame) + 160))


def heatmap(frame: pd.DataFrame, x: str, y: str, z: str, count: str) -> go.Figure:
    """Chart `z` by `x` and `y`, with the pair count `count` on hover."""
    matrix = frame.pivot(index=y, columns=x, values=z).sort_index()
    counts = frame.pivot(index=y, columns=x, values=count).reindex_like(matrix)
    fig = go.Figure(
        go.Heatmap(
            x=[str(v) for v in matrix.columns],
            y=matrix.index.tolist(),
            z=[values(row) for _, row in matrix.iterrows()],
            customdata=[values(row) for _, row in counts.iterrows()],
            zmin=-1,
            zmax=1,
            zmid=0,
            colorscale=SCALE,
            colorbar=dict(title="IC"),
            hoverongaps=False,
            hovertemplate="%{y}<br>%{x}<br>IC: %{z:.4f}<br>Pairs: %{customdata}<extra></extra>",
        )
    )
    fig.update_xaxes(type="category")
    fig.update_yaxes(autorange="reversed")
    return _style(fig, max(350, 25 * len(matrix) + 160))


def _style(fig: go.Figure, height: int = 380) -> go.Figure:
    style(fig, height)
    fig.update_layout(
        margin=dict(l=85, r=25, t=70, b=95), legend=dict(orientation="h", x=0, y=-0.25)
    )
    return fig


def figures(
    result: TimeSeriesEvaluation, method: str, quantiles: int
) -> tuple[dict[str, go.Figure], list[dict]]:
    """Build the overview charts of one method and the charts and tables of each horizon."""
    assets = result.assets.loc[result.assets.method == method].copy()
    summary = result.summary.loc[result.summary.method == method].sort_values("horizon")
    overview = {
        "breadth": heatmap(assets, "horizon", "asset", "ic", "n_pairs"),
        "comparison": confidence_plot(summary, [bar_count(h) for h in summary.horizon], "mean"),
        "quantiles": quantile_figure(result.quantiles, unit="Assets", quantiles=quantiles),
    }
    horizons = []
    for horizon, group in assets.groupby("horizon", sort=True):
        group = group.sort_values("asset")
        monthly = result.monthly.loc[
            (result.monthly.method == method) & (result.monthly.horizon == horizon)
        ].copy()
        monthly["month"] = pd.to_datetime(monthly.window_start, utc=True).dt.strftime("%Y-%m")
        counts = monthly.groupby("month").ic.count()
        breadth = go.Figure(
            go.Bar(x=counts.index.tolist(), y=counts.tolist(), marker_color=COLORS[0])
        )
        breadth.update_yaxes(title="Eligible assets", rangemode="tozero", dtick=1)
        breadth.update_xaxes(title="UTC calendar month", type="category")
        rolling = result.rolling.loc[
            (result.rolling.method == method) & (result.rolling.horizon == horizon)
        ].copy()
        chart = go.Figure()
        # Alphabetical initial selection, not selected by apparent predictive performance.
        for i, (asset, history) in enumerate(rolling.groupby("asset", sort=True)):
            chart.add_trace(
                go.Scatter(
                    x=[pd.Timestamp(t).isoformat() for t in history.window_end],
                    y=values(history.ic),
                    mode="lines",
                    name=str(asset),
                    visible=i == 0,
                    connectgaps=False,
                    line=dict(color=COLORS[0]),
                    customdata=history[["n_pairs", "pair_coverage", "status"]].values.tolist(),
                    hovertemplate=(
                        "%{x}<br>IC: %{y:.4f}<br>Pairs: %{customdata[0]}"
                        "<br>Coverage: %{customdata[1]:.1%}<br>%{customdata[2]}"
                        "<extra>%{fullData.name}</extra>"
                    ),
                )
            )
        chart.update_layout(
            updatemenus=[
                dict(
                    buttons=[
                        dict(
                            label=trace.name,
                            method="update",
                            args=[{"visible": [j == i for j in range(len(chart.data))]}],
                        )
                        for i, trace in enumerate(chart.data)
                    ],
                    x=0,
                    y=1.2,
                )
            ],
            showlegend=False,
        )
        chart.add_hline(y=0, line_dash="dot")
        chart.update_yaxes(title="Rolling TS IC", range=[-1.05, 1.05])
        chart.update_xaxes(title="Evaluation window end (UTC, exclusive)")
        horizons.append(
            {
                "horizon": int(horizon),
                "assets": group,
                "monthly": monthly,
                "figures": {
                    "assets": confidence_plot(group, group.asset.astype(str).tolist(), "ic"),
                    "monthly": heatmap(monthly, "month", "asset", "ic", "n_pairs"),
                    "breadth": style(breadth, 280),
                    "rolling": style(chart),
                },
            }
        )
    return overview, horizons
