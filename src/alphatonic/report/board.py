"""The trials of a study as one HTML page, sorted by any column. Needs `alphatonic[report]`.

The page renders [`Study.to_dict`][alphatonic.Study.to_dict] at one horizon, so it shows what
the JSON document holds. Sorting, the horizon and a filter by signal are query parameters, so a
sorted view is a link that can be shared. Links to a trial's files are relative to the study's
directory, which is how the server lays them out.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from alphatonic.report.figures import span
from alphatonic.report.page import environment
from alphatonic.study import DESCENDING, Study

COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("signal", "Signal", "Trial"),
    ("cs_ic", "Rank IC", "Cross-sectional"),
    ("cs_z", "z", "Cross-sectional"),
    ("cs_p", "p", "Cross-sectional"),
    ("trials", "Trials", "Multiple testing"),
    ("adjusted_p", "p × trials", "Multiple testing"),
    ("sample", "Sample", "Multiple testing"),
    ("ts_ic", "Rank IC", "Time-series"),
    ("ts_cosine", "Cosine", "Time-series"),
    ("ts_timing", "Timing", "Time-series"),
    ("start", "Window", "Data"),
    ("bar", "Bars", "Data"),
    ("assets", "Assets", "Data"),
    ("created_at", "Created", "Record"),
)
"""The sortable columns of the page by board column, with their headings and groups, in display
order. The caller's context keys join the `Data` group after `assets`."""

SIGNIFICANT = 0.05
"""Adjusted p-values at or below this are set in bold, to be found, not to be believed: the
trial count is a lower bound on the alternatives tried."""


def render_board(
    study: Study,
    *,
    horizon: str | int | None = None,
    sort: str | None = None,
    order: str | None = None,
    signal: str | None = None,
) -> str:
    """Render the list of the study's trials as a standalone HTML page.

    Args:
        study: The study whose trials to list.
        horizon: Horizon of the statistics in bars; default, or one no trial has: the smallest.
        sort: Board column to sort by; default, or an unknown one: `created_at`.
        order: `asc` or `desc`; default: the column's own direction.
        signal: Show only the trials of this signal.

    Returns:
        The HTML.
    """
    asked = "" if horizon is None else str(horizon)
    chosen = int(asked) if asked.isdigit() else None
    descending = {"asc": False, "desc": True}.get(order or "")
    try:
        data = study.to_dict(chosen, sort=sort, descending=descending)
    except ValueError:  # An unknown column: newest first.
        data = study.to_dict(chosen)
    if data["horizons"] and data["horizon"] not in data["horizons"]:
        data = study.to_dict(sort=data["sort"], descending=data["descending"])
    keys = data["context_keys"]
    position = [key for key, _, _ in COLUMNS].index("assets") + 1
    columns = [
        {
            "key": key,
            "heading": heading,
            "group": group,
            "numeric": key in {"cs_ic", "cs_z", "cs_p", "trials", "adjusted_p", "assets"}
            or key.startswith("ts_"),
            "order": _next_order(key, data["sort"], data["descending"]),
        }
        for key, heading, group in [*COLUMNS[:position], *((k, k, "Data") for k in keys)]
        + list(COLUMNS[position:])
    ]
    groups: list[dict[str, Any]] = []
    for column in columns:
        if groups and groups[-1]["label"] == column["group"]:
            groups[-1]["span"] += 1
        else:
            groups.append({"label": column["group"], "span": 1})
    signals = sorted({trial["signal"] for trial in data["trials"]})
    rows = [trial for trial in data["trials"] if not signal or trial["signal"] == signal]
    families = data["families"]
    return (
        environment()
        .get_template("board.html")
        .render(
            title=study.name or study.directory.name,
            data=data,
            rows=rows,
            columns=columns,
            groups=groups,
            signals=signals,
            signal=signal if signal in signals else None,
            asked_signal=signal,
            holdout_uses=sum(family["holdout_uses"] for family in families.values()),
            significant=SIGNIFICANT,
            number=_number,
            p_value=_p_value,
            bar=_bar,
            when=_when,
        )
    )


def _next_order(key: str, sort: str, descending: bool) -> str:
    """The order a click on a heading asks for: the opposite one, or the column's own."""
    if key == sort:
        return "asc" if descending else "desc"
    return "desc" if key in DESCENDING else "asc"


def _number(value: float | None, places: int = 3) -> str:
    """Format a statistic to fixed decimals, so that a column's digits line up, or an en dash."""
    if value is None:
        return "–"
    return f"{value:.{places}f}"


def _p_value(value: float | None) -> str:
    """Format a p-value to three decimals, and smaller ones as `< 0.001`."""
    if value is None:
        return "–"
    return "< 0.001" if value < 0.001 else f"{value:.3f}"


def _bar(seconds: float | None) -> str:
    """Name a bar spacing in its largest whole unit, such as `1h` or `15min`."""
    return "–" if seconds is None else span(seconds)


def _when(value: str | None, form: str = "%Y-%m-%d %H:%M") -> str:
    """Format an ISO 8601 timestamp of the document."""
    return "–" if value is None else datetime.fromisoformat(value).strftime(form)


__all__ = ["COLUMNS", "render_board"]
