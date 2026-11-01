"""The trials of a study as one HTML page, sorted by any column.

The page renders [`Study.to_dict`][alphatonic.Study.to_dict] at one horizon, so it shows what
the JSON document holds. Sorting, the horizon, a filter by signal and the column groups shown are
query parameters, so a view is a link that can be shared. Links to a trial's files are relative to
the study's directory, which is how the server lays them out.
"""

from __future__ import annotations

from bisect import bisect_left, bisect_right
from collections.abc import Sequence
from datetime import datetime
from math import floor, log10
from typing import Any
from urllib.parse import urlencode

from alphatonic.report.figures import span
from alphatonic.report.page import environment
from alphatonic.study import DESCENDING, Study

COLUMNS: tuple[tuple[str, str, str], ...] = (
    ("signal", "Signal", "Trial"),
    ("cs_ic", "Rank IC", "Cross-sectional"),
    ("cs_z", "z", "Cross-sectional"),
    ("cs_p", "p", "Cross-sectional"),
    ("adjusted_p", "p × trials", "Cross-sectional"),
    ("ts_ic", "Rank IC", "Time-series"),
    ("ts_t", "t", "Time-series"),
    ("ts_p", "p", "Time-series"),
    ("ts_adjusted_p", "p × trials", "Time-series"),
    ("ts_cosine", "Cosine", "Cosine"),
    ("ts_cosine_t", "t", "Cosine"),
    ("ts_cosine_p", "p", "Cosine"),
    ("ts_cosine_adjusted_p", "p × trials", "Cosine"),
    ("ts_timing", "Timing", "Cosine"),
    ("start", "Window", "Data"),
    ("bar", "Bars", "Data"),
    ("assets", "Assets", "Data"),
    ("created_at", "Created", "Data"),
    ("trials", "Trials", "Multiple testing"),
    ("sample", "Sample", "Multiple testing"),
)
"""The sortable columns of the page by board column, with their headings and groups, in display
order. The caller's context keys join the `Data` group after `assets`."""

NAMES: dict[str, str] = {
    "cs_z": "z-statistic of the rank IC",
    "cs_p": "p-value of the rank IC",
    "ts_t": "t-statistic of the rank IC",
    "ts_p": "p-value of the rank IC",
    "ts_cosine_t": "t-statistic of the cosine IC",
    "ts_cosine_p": "p-value of the cosine IC",
}
"""What the columns headed by a single letter hold, for their tooltips and for the line that
explains a ranking."""

GROUPS: dict[str, str] = {
    "Cross-sectional": "cs",
    "Time-series": "ts",
    "Cosine": "cosine",
    "Data": "data",
    "Multiple testing": "testing",
}
"""The groups of columns that can be shown or hidden, by group heading, with the name that the
`show` parameter uses. The `Trial` group, which names the row, is always shown."""

PLOTS: dict[str, tuple[str, str]] = {
    "cs_ic": ("cs_ci", "Rank IC"),
    "ts_ic": ("ts_ci", "Time-series rank IC"),
    "ts_cosine": ("ts_cosine_ci", "Time-series cosine IC"),
}
"""The columns drawn as a dot with an interval, each with the prefix of its interval's keys in
[`Study.to_dict`][alphatonic.Study.to_dict] and the name of the estimate in the text of the mark."""

INTERVALS: dict[str, str] = {"cs": "95% interval", "ts": "95% bootstrap interval"}
"""What to call the interval of a plotted column, by the first two letters of its key."""

SIGNIFICANT = 0.05
"""Adjusted p-values at or below this are set in bold, to be found, not to be believed: the
trial count is a lower bound on the alternatives tried."""

RANKED: dict[str, bool] = {
    "cs_ic": True,
    "cs_z": True,
    "cs_p": False,
    "adjusted_p": False,
    "ts_ic": True,
    "ts_t": True,
    "ts_p": False,
    "ts_adjusted_p": False,
    "ts_cosine": True,
    "ts_cosine_t": True,
    "ts_cosine_p": False,
    "ts_cosine_adjusted_p": False,
    "ts_timing": True,
}
"""The statistics the page numbers its rows by when it is sorted by one, each with whether a
larger value is better. Rank 1 is the best value however the page is ordered."""


def render_board(
    study: Study,
    *,
    horizon: str | int | None = None,
    sort: str | None = None,
    order: str | None = None,
    signal: str | None = None,
    show: str | Sequence[str] | None = None,
) -> str:
    """Render the list of the study's trials as a standalone HTML page.

    Args:
        study: The study whose trials to list.
        horizon: Horizon of the statistics in bars; default, or one no trial has: the smallest.
        sort: Board column to sort by; default, or an unknown one: `created_at`.
        order: `asc` or `desc`; default: the column's own direction.
        signal: Show only the trials of this signal.
        show: The column groups to show, as names of `GROUPS` (`cs`, `testing`, `ts`, `cosine`,
            `data`), in one string separated by commas or in several. Names that are not
            groups are ignored, and an empty string shows only the trial. Default: every group. A
            column that the page is sorted by, other than `created_at`, is shown whatever the
            groups.

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
            "name": NAMES.get(key),
            "group": group,
            "numeric": key in {"cs_ic", "cs_z", "cs_p", "trials", "adjusted_p", "assets"}
            or key.startswith("ts_"),
            "order": _next_order(key, data["sort"], data["descending"]),
        }
        for key, heading, group in [*COLUMNS[:position], *((k, k, "Data") for k in keys)]
        + list(COLUMNS[position:])
    ]
    chosen_groups = _chosen(show)
    on = set(GROUPS.values()) if chosen_groups is None else chosen_groups
    # The default order, newest first, needs no column to explain it.
    forced = None if data["sort"] == "created_at" else data["sort"]
    sorted_group = next((c["group"] for c in columns if c["key"] == forced), None)
    visible = [
        column
        for column in columns
        if column["group"] == "Trial" or GROUPS[column["group"]] in on or column["key"] == forced
    ]
    toggles = [
        {
            "name": name,
            "label": label,
            "on": name in on,
            "forced": label == sorted_group and name not in on,
        }
        for label, name in GROUPS.items()
    ]
    # Every group is shown by default, which a link leaves unsaid.
    shown_groups = None if chosen_groups is None else ",".join(sorted(chosen_groups))
    groups: list[dict[str, Any]] = []
    for column in visible:
        if groups and groups[-1]["label"] == column["group"]:
            groups[-1]["span"] += 1
        else:
            groups.append({"label": column["group"], "span": 1})
    signals = sorted({trial["signal"] for trial in data["trials"]})
    shown = signal if signal in signals else None
    rows = [trial for trial in data["trials"] if not signal or trial["signal"] == signal]
    families = data["families"]

    def link(**changes: Any) -> str:
        """The query of this view with some parameters changed, so a link keeps the rest."""
        query = {
            "sort": data["sort"],
            "order": "desc" if data["descending"] else "asc",
            "horizon": data["horizon"],
            "signal": shown or "",
            "show": shown_groups,
            **changes,
        }
        return "?" + urlencode({key: value for key, value in query.items() if value is not None})

    # The scale is that of every trial at this horizon, so that choosing a signal moves no mark.
    extents = {
        key: extent
        for key, (prefix, _) in PLOTS.items()
        if (extent := _extent(data["trials"], key, prefix)) is not None
    }
    larger = RANKED.get(data["sort"])
    ranks = _ranks([row[data["sort"]] for row in rows], larger) if larger is not None else None
    tiles = _tiles(rows, data)
    rows = [
        {
            **trial,
            "plots": {key: _plot(trial, key, extents.get(key)) for key in PLOTS},
            "rank": None if ranks is None else ranks[i],
        }
        for i, trial in enumerate(rows)
    ]
    ranked_by = None
    if larger is not None:
        column = next(column for column in columns if column["key"] == data["sort"])
        label, group = column["name"] or column["heading"], column["group"].lower()
        # The group says which analysis the column belongs to, unless its label already does.
        if group not in label.lower():
            label = f"{label} ({group})"
        ranked_by = f"{label}: 1 is the {'largest' if larger else 'smallest'}"
    return (
        environment()
        .get_template("board.html")
        .render(
            title=study.name or study.directory.name,
            data=data,
            rows=rows,
            tiles=tiles,
            columns=visible,
            groups=groups,
            toggles=toggles,
            plotted=list(PLOTS),
            testing_hidden="testing" not in on and bool({"cs", "ts", "cosine"} & on),
            signals=signals,
            signal=shown,
            asked_signal=signal,
            link=link,
            extents={key: f"{extent:g}" for key, extent in extents.items()},
            intervals=INTERVALS,
            ranked_by=ranked_by,
            holdout_uses=sum(family["holdout_uses"] for family in families.values()),
            significant=SIGNIFICANT,
            number=_number,
            p_value=_p_value,
            bar=_bar,
            when=_when,
        )
    )


def render_drawing(signal: str, title: str) -> str:
    """Render the page that stands in for a tearsheet while the server draws it.

    The page shows a spinner and a message, asks for the tearsheet with `?render`, and replaces
    itself with the answer. If the drawing fails, it shows the error and a link to the list.

    Args:
        signal: The trial's signal, shown as the heading.
        title: The study's name, shown in the page's title.

    Returns:
        The HTML.
    """
    return environment().get_template("drawing.html").render(signal=signal, title=title)


def _ranks(values: list[float | None], larger: bool) -> list[int | None]:
    """Rank values from the best, which is rank 1; equal values share a rank, as in a league table.

    A missing value has no rank. The ranks do not depend on the order of `values`.
    """
    defined = sorted(value for value in values if value is not None)
    ranks: list[int | None] = []
    for value in values:
        if value is None:
            ranks.append(None)
        elif larger:  # The trials with a strictly larger value come first.
            ranks.append(len(defined) - bisect_right(defined, value) + 1)
        else:
            ranks.append(bisect_left(defined, value) + 1)
    return ranks


def _nice(value: float) -> float:
    """Round a positive number up to 1, 2, 5 or 10 times a power of ten."""
    exponent = floor(log10(value))
    step = next(step for step in (1, 2, 5, 10) if step * 10.0**exponent >= value)
    return float(f"{step * 10.0**exponent:.12g}")


def _chosen(show: str | Sequence[str] | None) -> set[str] | None:
    """The group names asked for, or `None` for the default of every group."""
    if show is None:
        return None
    parts = [show] if isinstance(show, str) else show
    return {name.strip() for part in parts for name in part.split(",")} & set(GROUPS.values())


def _extent(trials: list[dict[str, Any]], key: str, prefix: str) -> float | None:
    """Half the width of a column's axis: the reach of any estimate or interval, rounded up.

    The axis runs from minus to plus this value around zero, the same for every row. It is `None`
    if no trial has an estimate in the column at the horizon, or all of them are zero.
    """
    keys = (key, f"{prefix}_lower", f"{prefix}_upper")
    reach = max((abs(t[k]) for t in trials for k in keys if t[k] is not None), default=0.0)
    return _nice(reach) if reach > 0 else None


def _plot(trial: dict[str, Any], key: str, extent: float | None) -> dict[str, Any] | None:
    """Place a trial's estimate and its 95% interval on the column's axis, in percent of its width.

    `low` and `high` are `None` when the interval is undefined: the estimate is then drawn alone
    and hollow, because a dot without a whisker would suggest that it is exact.
    """
    prefix, name = PLOTS[key]
    interval = INTERVALS[key[:2]]
    estimate, lower, upper = trial[key], trial[f"{prefix}_lower"], trial[f"{prefix}_upper"]
    if estimate is None or extent is None:
        return None

    def place(value: float) -> float:
        return round(50 + 50 * value / extent, 2)

    if lower is None or upper is None:
        text = f"{name} {estimate:.4f}; the {interval} is undefined at this horizon"
        return {"at": place(estimate), "low": None, "high": None, "text": text}
    text = f"{name} {estimate:.4f}, {interval} {lower:.4f} to {upper:.4f}"
    return {"at": place(estimate), "low": place(lower), "high": place(upper), "text": text}


def _tiles(rows: list[dict[str, Any]], data: dict[str, Any]) -> list[dict[str, Any]]:
    """The headline figures of the trials shown, each with the trial or family behind it.

    The best-looking rank IC comes with its adjusted p-value, so that it is never read without the
    number of alternatives tried. A figure that cannot be computed is a dash with the reason.
    """
    if not rows:
        return []

    def named(trial: dict[str, Any]) -> str:
        details = ", ".join(f"{name}={value}" for name, value in trial["parameters"].items())
        return f"{trial['signal']} ({details})" if details else trial["signal"]

    def about(trial: dict[str, Any] | None) -> dict[str, Any]:
        if trial is None:
            return {"name": None, "href": None}
        return {"name": named(trial), "href": trial["files"]["tearsheet"]}

    adjusted = [trial for trial in rows if trial["adjusted_p"] is not None]
    lowest = min(adjusted, key=lambda trial: trial["adjusted_p"], default=None)
    defined = [trial for trial in rows if trial["cs_ic"] is not None]
    highest = max(defined, key=lambda trial: trial["cs_ic"], default=None)
    biggest = max(rows, key=lambda trial: trial["trials"])
    uses = {trial["family"]: trial["holdout_uses"] for trial in rows}
    repeated = sum(count > 1 for count in uses.values())
    if repeated:
        looked = f"{repeated} {'family' if repeated == 1 else 'families'} looked more than once"
    elif data["holdout_start"]:
        looked = f"holdout from {_when(data['holdout_start'])} UTC"
    else:
        looked = "no holdout set"
    return [
        {
            "label": "Lowest p × trials",
            "figure": "–" if lowest is None else _p_value(lowest["adjusted_p"]),
            "detail": (
                "no p-value at this horizon"
                if lowest is None
                else (
                    f"p {_p_value(lowest['cs_p'])} · {lowest['trials']} "
                    f"trial{'' if lowest['trials'] == 1 else 's'} in its family"
                )
            ),
            **about(lowest),
        },
        {
            "label": "Highest rank IC",
            "figure": "–" if highest is None else _number(highest["cs_ic"], 4),
            "detail": (
                "no rank IC at this horizon"
                if highest is None
                else f"p × trials {_p_value(highest['adjusted_p'])}"
            ),
            **about(highest),
        },
        {
            "label": "Largest family",
            "figure": f"{biggest['trials']} trial{'' if biggest['trials'] == 1 else 's'}",
            "detail": f"family {biggest['family']}",
            "name": None,
            "href": None,
        },
        {
            "label": "Holdout looks",
            "figure": str(sum(uses.values())),
            "detail": looked,
            "badge": "re-used" if repeated else None,
            "name": None,
            "href": None,
        },
    ]


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
