"""The offline HTML tearsheet. Needs the `report` extra: `pip install "alphatonic[report]"`."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from importlib.metadata import version
from typing import TYPE_CHECKING, Any

import numpy as np
import pandas as pd

from alphatonic.config import METHODS, ReportOptions

try:
    from jinja2 import Environment, PackageLoader, select_autoescape
    from plotly.offline import get_plotlyjs

    from alphatonic.report.figures import (
        coverage_figures,
        horizon_label,
        method_figures,
        quantile_figure,
    )
    from alphatonic.report.ts_figures import figures as ts_figures
except ModuleNotFoundError as error:  # pragma: no cover - exercised only without the extra
    if error.name and error.name.split(".")[0] in {"plotly", "jinja2"}:
        raise ImportError(
            f"The tearsheet needs plotly and jinja2 ({error.name} is missing): "
            'pip install "alphatonic[report]"'
        ) from error
    raise

if TYPE_CHECKING:
    import plotly.graph_objects as go

    from alphatonic.evaluation import Evaluation

__all__ = ["render_tearsheet"]

SUMMARY_COLUMNS = {
    "mean": "Mean IC",
    "ci95_lower": "95% lower",
    "ci95_upper": "95% upper",
    "std": "Std. dev.",
    "ic_ir": "IC IR",
    "positive_fraction": "Positive fraction",
    "n_periods": "Valid",
    "skipped_periods": "Skipped",
    "mean_pair_coverage": "Pair coverage",
    "hac_lags": "HAC lags",
    "hac_se": "HAC SE",
    "hac_z": "HAC z",
    "hac_p_value": "HAC p-value",
}
TS_SUMMARY_COLUMNS = {
    "horizon": "Horizon (bars)",
    "mean": "Mean asset IC",
    "median": "Median",
    "q25": "25th percentile",
    "q75": "75th percentile",
    "ci95_lower": "Mean IC 95% lower",
    "ci95_upper": "Mean IC 95% upper",
    "positive_fraction": "Positive assets",
    "n_assets": "Eligible assets",
    "total_assets": "Total assets",
    "bootstrap_status": "Uncertainty status",
    "bootstrap_block_bars": "Block (bars)",
    "bootstrap_valid": "Valid draws",
    "universe_monthly_ic_ir": "ICIR of monthly mean asset IC",
    "universe_valid_months": "Valid months",
    "universe_monthly_ir_status": "Monthly ICIR status",
}
TS_ASSET_COLUMNS = {
    "asset": "Asset",
    "ic": "Full-period IC",
    "monthly_ic_ir": "Monthly TS ICIR",
    "valid_months": "Valid months",
    "monthly_ir_status": "Monthly ICIR status",
    "n_pairs": "Pairs",
    "pair_coverage": "Coverage",
    "status": "Status",
    "n_expected": "Expected",
    "first_pair": "First pair",
    "last_pair": "Last pair",
    "boundary_excluded": "Boundary exclusions",
    "skipped_months": "Skipped months",
    "signal_autocorr_lag1": "Score autocorrelation (1 bar)",
    "bootstrap_status": "Uncertainty status",
}
TS_MONTHLY_COLUMNS = {
    "asset": "Asset",
    "month": "Month",
    "ic": "IC",
    "status": "Status",
    "n_pairs": "Pairs",
    "n_expected": "Expected",
    "pair_coverage": "Coverage",
    "boundary_excluded": "Boundary exclusions",
}


def _format(value: Any, column: str) -> str:
    if pd.isna(value):
        return "—"
    if column in {"n_periods", "skipped_periods", "hac_lags"}:
        return str(int(value))
    if column in {"positive_fraction", "mean_pair_coverage"}:
        return f"{value:.1%}"
    return f"{value:.4g}"


def _table(frame: pd.DataFrame, columns: Mapping[str, str]) -> str:
    frame = frame.reindex(columns=list(columns)).copy()
    for column in columns:
        if column.endswith("status"):
            frame[column] = frame[column].astype(object).str.replace("_", " ")
        elif column in {"pair_coverage", "positive_fraction"}:
            frame[column] = frame[column].map(lambda v: f"{v:.1%}" if pd.notna(v) else "—")
    return frame.rename(columns=columns).to_html(
        index=False,
        border=0,
        na_rep="—",
        float_format=lambda v: f"{v:.4g}",
        escape=True,
        classes="ts-table",
    )


def render_tearsheet(
    evaluation: Evaluation,
    *,
    options: ReportOptions | None = None,
    title: str = "Factor tearsheet",
    eyebrow: str | None = "alphatonic · information coefficient",
    subtitle: str | None = None,
    context: Mapping[str, str] | None = None,
    footer: Sequence[str] | None = None,
) -> str:
    """Render an evaluation as one standalone HTML document.

    The charts are drawn from the evaluation's tables; nothing is recomputed. The page embeds
    Plotly's JavaScript once, so it opens offline, and every piece of caller-supplied text is
    escaped.

    Args:
        evaluation: The result to show.
        options: Display options of the cross-sectional charts.
        title: Page heading.
        eyebrow: Small label above the heading; `None` hides it.
        subtitle: A line under the heading, shown in code style, such as the factor's name.
        context: Extra labelled facts shown under the heading.
        footer: Extra lines in the page footer.

    Returns:
        The HTML document.

    Raises:
        ValueError: If the evaluation has no periods to draw.
    """
    options = options or ReportOptions()
    periods = evaluation.periods.copy()
    periods["timestamp"] = pd.to_datetime(periods.timestamp, utc=True)
    periods = periods.sort_values(["horizon", "timestamp"])
    if periods.empty:
        raise ValueError("Cannot render a tearsheet without evaluation periods")
    config = evaluation.config
    summary, bar, time_series = evaluation.summary, evaluation.bar, evaluation.time_series

    def html(fig: go.Figure, identifier: str) -> str:
        return fig.to_html(
            full_html=False,
            include_plotlyjs=False,
            div_id=identifier,
            config={"responsive": True, "displaylogo": False},
        )

    methods = []
    for method in METHODS:
        if config.mode == "time_series":
            continue
        rows = [
            [
                horizon_label(row["horizon"], bar),
                *[_format(row.get(column, np.nan), column) for column in SUMMARY_COLUMNS],
            ]
            for row in summary.loc[summary.method == method]
            .sort_values("horizon")
            .to_dict("records")
        ]
        figures = method_figures(periods, summary, method, bar, options)
        methods.append(
            {
                "name": method,
                "rows": rows,
                "figures": {name: html(fig, f"{method}-{name}") for name, fig in figures.items()},
            }
        )
    ts_methods = []
    if time_series is not None:
        for method in METHODS:
            overview, horizons = ts_figures(time_series, method, config.quantiles)
            for item in horizons:
                item["table"] = _table(item.pop("assets"), TS_ASSET_COLUMNS)
                item["monthly_table"] = _table(item.pop("monthly"), TS_MONTHLY_COLUMNS)
                item["label"] = horizon_label(item["horizon"], bar)
                item["figures"] = {
                    name: html(fig, f"ts-{method}-h{item['horizon']}-{name}")
                    for name, fig in item["figures"].items()
                }
            ts_methods.append(
                {
                    "name": method,
                    "horizons": horizons,
                    "table": _table(
                        time_series.summary.loc[time_series.summary.method == method],
                        TS_SUMMARY_COLUMNS,
                    ),
                    "figures": {
                        name: html(fig, f"ts-{method}-{name}") for name, fig in overview.items()
                    },
                }
            )
    environment = Environment(
        loader=PackageLoader("alphatonic.report", "templates"),
        autoescape=select_autoescape(["html"]),
    )
    cs_quantiles = evaluation.quantiles
    versions = {name: version(name) for name in ("alphatonic", "plotly", "jinja2")}
    return environment.get_template("tearsheet.html").render(
        title=title,
        eyebrow=eyebrow,
        subtitle=subtitle,
        context=dict(context or {}),
        footer=list(footer or []),
        config=config,
        window=f"{evaluation.start:%Y-%m-%d %H:%M} → {evaluation.end:%Y-%m-%d %H:%M}",
        options=options,
        rolling_duration=str(pd.Timedelta(options.rolling_window)),
        methods=methods,
        columns=["Horizon", *SUMMARY_COLUMNS.values()],
        diagnostics={name: html(fig, name) for name, fig in coverage_figures(periods, bar).items()},
        plotly_js=get_plotlyjs(),
        invalid_horizons=sorted(summary.loc[summary.n_periods == 0, "horizon"].unique().tolist()),
        ts_methods=ts_methods,
        ts_options=config.time_series,
        cs_quantiles=(
            html(
                quantile_figure(cs_quantiles, unit="Timestamps", quantiles=config.quantiles),
                "cs-quantiles",
            )
            if not cs_quantiles.empty
            else None
        ),
        versions=versions,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
    )
