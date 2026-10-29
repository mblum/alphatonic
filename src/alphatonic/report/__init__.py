"""The offline HTML tearsheet. Needs the `report` extra: `pip install "alphatonic[report]"`."""

from __future__ import annotations

from collections.abc import Hashable, Mapping, Sequence
from datetime import UTC, datetime
from html import escape
from importlib.metadata import version
from typing import TYPE_CHECKING, Any, cast

import numpy as np
import pandas as pd

from alphatonic.config import EvaluationConfig, ReportOptions

try:
    from alphatonic.report.figures import (
        Spec,
        coverage_figures,
        horizon_label,
        method_figures,
        quantile_figure,
        span,
    )
    from alphatonic.report.page import environment
    from alphatonic.report.ts_figures import horizon_figures
except ModuleNotFoundError as error:  # pragma: no cover - exercised only without the extra
    if error.name and error.name.split(".")[0] == "jinja2":
        raise ImportError(
            f"The tearsheet needs jinja2 ({error.name} is missing): "
            'pip install "alphatonic[report]"'
        ) from error
    raise

if TYPE_CHECKING:
    from alphatonic.evaluation import Evaluation

__all__ = ["render_tearsheet"]

ASSET_COLUMNS = {
    "asset": "Asset",
    "ic": "Spearman IC",
    "interval": "95% confidence interval",
    "n_pairs": "Usable pairs",
    "pair_coverage": "Pair coverage",
    "status": "Sample status",
    "bootstrap_status": "Inference status",
}
MONTHLY_COLUMNS = {
    "asset": "Asset",
    "month": "Month (UTC)",
    "n_pairs": "Usable pairs",
    "n_expected": "Expected pairs",
    "pair_coverage": "Pair coverage",
    "boundary_excluded": "Boundary exclusions",
    "status": "Sample status",
}
COUNT_COLUMNS = frozenset({"lag", "quantile", "boundary_excluded"})
"""Detail-table columns of whole numbers besides those named `n_*`, even when stored as floats."""
PERSISTENCE_SCOPES = {"cs": "Cross-section", "quantile": "Score buckets", "ts": "Time series"}
PERSISTENCE_METRICS = {
    "rank_autocorrelation": "Rank persistence",
    "entry_fraction": "Entry fraction",
    "normalized_change": "Normalised change",
    "sign_change_fraction": "Sign-change fraction",
    "zero_transition_fraction": "Zero-transition fraction",
}

Row = Mapping[Hashable, Any]


def _finite(value: Any) -> bool:
    numeric = isinstance(value, int | float | np.integer | np.floating)
    return numeric and not isinstance(value, bool) and bool(np.isfinite(value))


def _number(value: Any) -> str:
    return f"{value:.3f}" if _finite(value) else "—"


def _percent(value: Any) -> str:
    return f"{value:.1%}" if _finite(value) else "—"


def _decimal(value: Any) -> str:
    return f"{value:,.1f}" if _finite(value) else "—"


def _count(count: Any, total: Any) -> str:
    return f"{int(count):,} of {int(total):,}" if _finite(count) and _finite(total) else "—"


def _interval(row: Row) -> str:
    lower, upper = row.get("ci95_lower", np.nan), row.get("ci95_upper", np.nan)
    if not (_finite(lower) and _finite(upper)):
        return "Unavailable"
    return f"{lower:.3f} to {upper:.3f}"


def _estimate(row: Row) -> dict[str, Any]:
    """A mean IC with its interval, set in bold in the metrics tables."""
    return {
        "value": _number(row.get("mean", np.nan)),
        "detail": f"95% CI {_interval(row)}",
        "emphasis": True,
    }


def _table(
    frame: pd.DataFrame,
    columns: Mapping[str, str],
    label: str,
    *,
    intervals: bool = False,
) -> str:
    """Format a stored table as HTML, with numbers right-aligned and a dash where one is missing.

    Fractions and coverage are percentages to one decimal, counts are whole numbers, and other
    statistics have three decimals.

    Every value is escaped, so caller-supplied strings such as asset names never become HTML.
    """
    # Columns of numbers align right, so that digits line up down the column; text aligns left.
    numeric = {c for c in columns if c in frame and frame[c].dtype.kind in "iuf"}
    rows = frame.to_dict("records")

    def text(column: str, row: Row) -> str:
        if column == "interval" and intervals:
            return _interval(row)
        value = row.get(column)
        if value is None or (not isinstance(value, str) and bool(pd.isna(value))):
            return "—"
        if column.endswith("status"):
            return str(value).replace("_", " ")
        # Every row of a column gets the same decimals, so that right-aligned digits line up.
        if column == "pair_coverage" or column.endswith("_fraction"):
            return _percent(value)
        if (
            column.startswith("n_")
            or column in COUNT_COLUMNS
            or isinstance(value, int | np.integer)
        ):
            return f"{int(value):,}"
        return _number(value) if isinstance(value, float | np.floating) else str(value)

    def cell(tag: str, column: str, content: str) -> str:
        align = ' class="number"' if column in numeric else ""
        scope = ' scope="col"' if tag == "th" else ""
        return f"<{tag}{scope}{align}>{escape(content)}</{tag}>"

    head = "".join(cell("th", column, heading) for column, heading in columns.items())
    body = "\n".join(
        "<tr>" + "".join(cell("td", column, text(column, row)) for column in columns) + "</tr>"
        for row in rows
    )
    label = escape(label)
    return (
        f'<table aria-label="{label}"><caption class="sr-only">{label}</caption>'
        f"<thead><tr>{head}</tr></thead>\n<tbody>\n{body}\n</tbody></table>"
    )


def _targets(config: EvaluationConfig) -> str:
    """Describe the targets of both analyses."""
    names = {"return": "forward return", "vol_scaled": "vol-scaled return"}
    parts = [("Cross-section", config.target), ("time series", config.time_series.target)]
    text = " · ".join(f"{analysis}: {names[target]}" for analysis, target in parts)
    if any(target == "vol_scaled" for _, target in parts):
        text += f" (EWMA volatility, span {config.vol_span} bars)"
    return text[0].upper() + text[1:]


def _units(target: str) -> str:
    return "σ of horizon volatility" if target == "vol_scaled" else "basis points"


def _return_value(value: float, *, vol_scaled: bool) -> str:
    if not _finite(value):
        return "—"
    return f"{value:.3f} σ" if vol_scaled else f"{value * 10000:.2f} bps"


def _quantile_means(frame: pd.DataFrame, horizon: int) -> pd.Series:
    if frame.empty:
        return pd.Series(dtype=float)
    return frame.loc[frame.horizon == horizon].groupby("quantile").mean_return.mean()


def _spread(frame: pd.DataFrame, horizon: int, quantiles: int, *, vol_scaled: bool) -> dict:
    """Subtract the plotted bottom-quantile mean from the top-quantile mean."""
    means = _quantile_means(frame, horizon)
    # Require the configured endpoints, even when ties leave an extreme quantile empty.
    top, bottom = means.get(quantiles, np.nan), means.get(1, np.nan)
    return {
        "value": _return_value(top - bottom, vol_scaled=vol_scaled),
        "detail": f"Q{quantiles} {_return_value(top, vol_scaled=vol_scaled)}"
        f" · Q1 {_return_value(bottom, vol_scaled=vol_scaled)}",
    }


def _summary_row(summary: pd.DataFrame, horizon: int, method: str) -> dict[Hashable, Any]:
    if summary.empty:
        return {}
    selected = summary.loc[(summary.horizon == horizon) & (summary.method == method)]
    return selected.iloc[0].to_dict() if not selected.empty else {}


def _glance(evaluation: Evaluation) -> list[dict[str, Any]]:
    """The headline per horizon: mean rank IC with its interval, and the quantile spread."""
    config, ts = evaluation.config, evaluation.time_series
    rows = []
    for horizon in sorted(config.horizons):
        cells = []
        for summary, quantiles, target in (
            (evaluation.summary, evaluation.quantiles, config.target),
            (
                ts.summary if ts is not None else pd.DataFrame(),
                ts.quantiles if ts is not None else pd.DataFrame(),
                config.time_series.target,
            ),
        ):
            row = _summary_row(summary, horizon, "spearman")
            cells.append(_estimate(row))
            spread = _spread(
                quantiles, horizon, config.quantiles, vol_scaled=target == "vol_scaled"
            )
            cells.append(spread)
        rows.append({"label": horizon_label(horizon, evaluation.bar), "cells": cells})
    return rows


def _metrics(evaluation: Evaluation, *, time_series: bool) -> dict[str, Any]:
    """Every stored summary statistic worth reading, as metric rows by horizon columns."""
    config, ts = evaluation.config, evaluation.time_series
    source = ts if time_series else evaluation
    summary = source.summary if source is not None else pd.DataFrame()
    quantiles = source.quantiles if source is not None else pd.DataFrame()
    target = config.time_series.target if time_series else config.target
    horizons = sorted(config.horizons)
    unit = "assets" if time_series else "timestamps"
    top = config.quantiles
    # One mapping per horizon: method -> stored summary row, plus the quantile spread.
    stats = [
        {
            **{m: _summary_row(summary, h, m) for m in ("spearman", "pearson", "cosine")},
            "spread": _spread(quantiles, h, top, vol_scaled=target == "vol_scaled"),
        }
        for h in horizons
    ]

    def row(label: str, cell: Any) -> dict[str, Any]:
        return {"label": label, "cells": [cell(s) for s in stats]}

    def value(method: str, column: str, form: Any = _number) -> Any:
        return lambda s: {"value": form(s[method].get(column))}

    def positive(method: str) -> dict[str, Any]:
        return row(f"Positive {unit}", value(method, "positive_fraction", _percent))

    spearman = [row("Mean", lambda s: _estimate(s["spearman"])), positive("spearman")]
    if time_series:
        spearman.append(
            row(
                "Median across assets",
                lambda s: {
                    "value": _number(s["spearman"].get("median")),
                    "detail": f"middle half {_number(s['spearman'].get('q25'))}"
                    f" to {_number(s['spearman'].get('q75'))}",
                },
            )
        )
    else:
        spearman.append(row("Standard deviation", value("spearman", "std")))
        spearman.append(row("Mean ÷ standard deviation", value("spearman", "ic_ir")))
    groups: list[dict[str, Any]] = [
        {"label": "Spearman rank IC", "link": "method-correlation", "rows": spearman},
        {
            "label": "Pearson IC",
            "link": "method-correlation",
            "rows": [row("Mean", lambda s: _estimate(s["pearson"])), positive("pearson")],
        },
    ]
    if time_series and not summary.empty and summary.method.eq("cosine").any():
        groups.append(
            {
                "label": "Cosine similarity",
                "link": "method-cosine",
                "rows": [
                    row("Mean", value("cosine", "mean")),
                    row("Timing component", value("cosine", "mean_timing")),
                    row("Static component", value("cosine", "mean_static")),
                ],
            }
        )
    groups.append(
        {
            "label": "Quantile returns",
            "link": "method-quantiles",
            "rows": [row(f"Spread Q{top} − Q1", lambda s: s["spread"])],
        }
    )
    if time_series:
        sample = [
            row(
                "Eligible assets",
                lambda s: {
                    "value": _count(
                        s["spearman"].get("n_assets"), s["spearman"].get("total_assets")
                    )
                },
            ),
            row("Mean asset pair coverage", value("spearman", "mean_pair_coverage", _percent)),
            row("Bootstrap", lambda s: _bootstrap(s["spearman"])),
        ]
    else:
        sample = [
            row(
                "Usable timestamps",
                lambda s: {
                    "value": _count(
                        s["spearman"].get("n_periods"), s["spearman"].get("total_periods")
                    )
                },
            ),
            row("Mean paired assets", value("spearman", "mean_n_pairs", _decimal)),
            row("Mean pair coverage", value("spearman", "mean_pair_coverage", _percent)),
        ]
    groups.append({"label": "Sample", "link": "method-coverage", "rows": sample})
    return {
        "label": "Time-series metrics" if time_series else "Cross-sectional metrics",
        "horizons": [horizon_label(h, evaluation.bar) for h in horizons],
        "target": "volatility-scaled forward return, in σ of horizon volatility"
        if target == "vol_scaled"
        else "forward return, in basis points (bps)",
        "weighting": "Means weight eligible assets equally."
        if time_series
        else "Means weight usable timestamps equally.",
        "groups": groups,
    }


def _bootstrap(row: Row) -> dict[str, str | None]:
    status = row.get("bootstrap_status")
    if not isinstance(status, str):
        return {"value": "—"}
    samples, valid = row.get("bootstrap_samples"), row.get("bootstrap_valid")
    detail = f"{_count(valid, samples)} draws" if _finite(samples) and samples else None
    return {"value": status.replace("_", " "), "detail": detail}


def render_tearsheet(
    evaluation: Evaluation,
    *,
    options: ReportOptions | None = None,
    title: str = "Factor tearsheet",
    eyebrow: str | None = None,
    subtitle: str | None = None,
    context: Mapping[str, str] | None = None,
    footer: Sequence[str] | None = None,
) -> str:
    """Render an evaluation as one standalone HTML document.

    Figures and summary metrics use stored tables; statistical inference is not rerun.
    The page embeds the JavaScript that draws its charts and its stylesheet once, so it opens
    offline, and every piece of caller-supplied text is escaped. It follows the system's light or
    dark setting, and prints in light colours.

    Args:
        evaluation: The result to show.
        options: Display options of the cross-sectional charts.
        title: Page heading.
        eyebrow: Small label above the heading, such as a project's name; default: none.
        subtitle: A line under the heading, such as the factor's name.
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

    charts: dict[str, Spec] = {}

    def html(spec: Spec, identifier: str) -> str:
        """Keep a chart's specification for the page's script, and mark where it is drawn."""
        charts[identifier] = spec
        return f'<div class="host" id="{identifier}" data-chart="{identifier}"></div>'

    cs_available = bool(summary.n_periods.gt(0).any())
    ts_available = time_series is not None and bool(time_series.summary.n_assets.gt(0).any())
    cs_summary = summary.loc[summary.method == "spearman"]
    cs_figures = (
        {
            name: html(fig, f"cs-{name}")
            for name, fig in method_figures(periods, "spearman", bar, options).items()
        }
        if cs_available
        else {}
    )

    horizons, cosine = [], None
    if time_series is not None:
        for item in horizon_figures(time_series):
            horizon = item["horizon"]
            assets = item.pop("assets").copy()
            item["table"] = _table(assets, ASSET_COLUMNS, "asset rank correlations", intervals=True)
            # Coverage includes ineligible assets and is reported separately from IC estimates.
            item["coverage_table"] = _table(
                assets,
                {
                    "asset": "Asset",
                    "n_pairs": "Usable pairs",
                    "n_expected": "Expected pairs",
                    "pair_coverage": "Pair coverage",
                    "boundary_excluded": "Boundary exclusions",
                    "status": "Sample status",
                    "bootstrap_status": "Inference status",
                },
                "asset sample coverage",
            )
            item["monthly_table"] = _table(
                item.pop("monthly"), MONTHLY_COLUMNS, "monthly sample coverage"
            )
            pearson = (
                time_series.assets.loc[
                    (time_series.assets.method == "pearson")
                    & (time_series.assets.horizon == horizon)
                ]
                .sort_values("asset")
                .copy()
            )
            item["pearson_table"] = _table(
                pearson,
                {
                    **ASSET_COLUMNS,
                    "ic": "Pearson IC",
                },
                "asset linear correlations",
                intervals=True,
            )
            item["label"] = horizon_label(horizon, bar)
            item["figures"] = {
                name: html(fig, f"ts-h{horizon}-{name}") for name, fig in item["figures"].items()
            }
            horizons.append(item)
        if ts_available and time_series.summary.method.eq("cosine").any():
            cosine = [
                {
                    "label": horizon_label(cast(int, horizon), bar),
                    "table": _table(
                        group.sort_values("asset"),
                        {
                            "asset": "Asset",
                            "ic": "Cosine similarity",
                            "ic_timing": "Timing component",
                            "ic_static": "Static component",
                            "long_fraction": "Long fraction",
                            "status": "Sample status",
                        },
                        "asset position alignment",
                    ),
                }
                for horizon, group in time_series.assets.loc[
                    time_series.assets.method == "cosine"
                ].groupby("horizon", sort=True)
            ]

    def buckets(frame: pd.DataFrame, identifier: str, *, time_series: bool) -> str | None:
        if frame.empty:
            return None
        target = config.time_series.target if time_series else config.target
        return html(
            quantile_figure(
                frame,
                unit="Assets" if time_series else "Timestamps",
                quantiles=config.quantiles,
                vol_scaled=target == "vol_scaled",
            ),
            identifier,
        )

    versions = {name: version(name) for name in ("alphatonic", "jinja2")}
    return (
        environment()
        .get_template("tearsheet.html")
        .render(
            title=title,
            eyebrow=eyebrow,
            subtitle=subtitle,
            context=dict(context or {}),
            footer=list(footer or []),
            config=config,
            bar=span(bar.total_seconds()) if bar is not None else None,
            glance=_glance(evaluation),
            cs_units=_units(config.target),
            ts_units=_units(config.time_series.target),
            cs_metrics=_metrics(evaluation, time_series=False),
            ts_metrics=_metrics(evaluation, time_series=True),
            targets=_targets(config),
            window=f"{evaluation.start:%Y-%m-%d %H:%M} → {evaluation.end:%Y-%m-%d %H:%M}",
            options=options,
            cs_available=cs_available,
            ts_available=ts_available,
            cs_figures=cs_figures,
            invalid_horizons=sorted(cs_summary.loc[cs_summary.n_periods == 0, "horizon"].tolist()),
            ts_evaluated=time_series is not None,
            ts_pearson=time_series is not None
            and bool(time_series.summary.method.eq("pearson").any()),
            horizons=horizons,
            cosine=cosine,
            persistence=_persistence(evaluation),
            ts_options=config.time_series,
            diagnostics={
                name: html(fig, name) for name, fig in coverage_figures(periods, bar).items()
            },
            charts=charts,
            cs_quantiles=buckets(evaluation.quantiles, "cs-quantiles", time_series=False)
            if cs_available
            else None,
            ts_quantiles=buckets(time_series.quantiles, "ts-quantiles", time_series=True)
            if time_series is not None
            else None,
            versions=versions,
            generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        )
    )


def _persistence(evaluation: Evaluation) -> dict[str, Any] | None:
    """Arrange stored persistence means as measures by lag, and format the detail tables."""
    result = evaluation.persistence
    if result is None:
        return None
    summary = result.summary
    lags = sorted(summary.lag.unique().tolist())
    groups: dict[str, list[dict[str, Any]]] = {}
    for (scope, quantile, metric), rows in summary.groupby(
        ["scope", "quantile", "metric"], sort=False
    ):
        label = PERSISTENCE_METRICS.get(str(metric), str(metric).replace("_", " "))
        if quantile:
            label += f" · Q{quantile}"
        by_lag = rows.set_index("lag")
        cells = []
        for lag in lags:
            if lag not in by_lag.index:
                cells.append({"value": "—"})
                continue
            stored = by_lag.loc[lag]
            mean = stored["mean"]
            status = str(stored["status"])
            cells.append(
                {
                    "value": _percent(mean) if str(metric).endswith("_fraction") else _number(mean),
                    "detail": _count(stored["n_valid"], stored["n_total"])
                    if status == "valid"
                    else status.replace("_", " "),
                }
            )
        scope_label = PERSISTENCE_SCOPES.get(str(scope), str(scope))
        groups.setdefault(scope_label, []).append({"label": label, "cells": cells})
    columns = {
        "assets": {
            "asset": "Asset",
            "lag": "Lag (bars)",
            "normalized_change": "Normalised change",
            "sign_change_fraction": "Sign-change fraction",
            "zero_transition_fraction": "Zero-transition fraction",
            "n_pairs": "Valid pairs",
            "n_expected": "Expected pairs",
            "pair_coverage": "Pair coverage",
            "change_status": "Change status",
            "status": "Transition status",
        },
        "periods": {
            "timestamp": "Timestamp (UTC)",
            "lag": "Lag (bars)",
            "rank_autocorrelation": "Rank persistence",
            "n_common": "Common assets",
            "n_current": "Current assets",
            "n_previous": "Previous assets",
            "pair_coverage": "Pair coverage",
            "n_entries": "Universe entries",
            "n_exits": "Universe exits",
            "status": "Status",
        },
        "quantiles": {
            "timestamp": "Timestamp (UTC)",
            "lag": "Lag (bars)",
            "quantile": "Bucket",
            "entry_fraction": "Entry fraction",
            "n_current": "Current members",
            "n_previous": "Previous members",
            "n_entries": "Entries",
            "n_exits": "Exits",
            "n_universe_entries": "Entries absent from prior universe",
            "n_universe_exits": "Exits absent from current universe",
            "status": "Status",
        },
    }
    tables = {
        name: _table(getattr(result, name).head(200), labels, f"signal persistence {name}")
        for name, labels in columns.items()
    }
    return {
        "lags": lags,
        "groups": [{"label": label, "rows": rows} for label, rows in groups.items()],
        "tables": tables,
    }
