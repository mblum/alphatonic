"""Keep every evaluation of a research question as a trial, and count the trials.

A p-value means what it says only for a test chosen in advance. Evaluate twenty variants of an
idea and the best one looks significant by chance. A [`Study`][alphatonic.Study] keeps each
evaluation it runs as a trial in one directory, counts the trials of each family of signals, and
reports every cross-sectional p-value next to that count. It also keeps a holdout period away from
in-sample evaluations and counts each look at it.

Each trial is a directory `<study>/<id>/`:

    record.json      what was evaluated, on which window and sample, and the flat metrics
    tearsheet.html   the tearsheet
    tables/          the tables, reloadable with `Evaluation.load`

`record.json` is written last, so a directory without one is an evaluation that did not finish,
and the study ignores it.
"""

from __future__ import annotations

import hashlib
import re
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, Literal, cast
from uuid import uuid4

import numpy as np
import pandas as pd
from pydantic import BaseModel, ConfigDict, Field, JsonValue, ValidationError, model_validator

from alphatonic.config import EvaluationConfig, _utc
from alphatonic.evaluation import Evaluation, evaluate
from alphatonic.export import FORMAT_VERSION as JSON_FORMAT_VERSION
from alphatonic.export import jsonable
from alphatonic.inputs import utc_index
from alphatonic.progress import ProgressFactory, silent

RECORD: Final = "record.json"
"""Name of the record file in a trial's directory."""

TEARSHEET: Final = "tearsheet.html"
"""Name of the tearsheet file in a trial's directory."""

TABLES: Final = "tables"
"""Name of the directory holding a trial's tables."""

IDENTIFIER: Final = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")
"""What a trial identifier may look like, so that one never names a path outside the study."""

FORMAT_VERSION: Final = 1
"""Version of the record layout this module writes and reads."""

BOARD_COLUMNS: Final = (
    "created_at",
    "signal",
    "family",
    "parameters",
    "sample",
    "start",
    "end",
    "assets",
    "bar",
    "horizon",
    "cs_ic",
    "cs_z",
    "cs_p",
    "adjusted_p",
    "ts_ic",
    "ts_cosine",
    "ts_timing",
    "trials",
    "holdout_uses",
    "note",
)
"""Columns of [`Study.board`][alphatonic.Study.board], before those of the caller's context."""

DESCENDING: Final = frozenset(
    {"created_at", "assets", "cs_ic", "cs_z", "ts_ic", "ts_cosine", "ts_timing", "trials"}
)
"""Board columns that sort largest first unless asked otherwise; all others sort smallest first."""

_STATISTICS: Final = {
    "cs_ic": "cs.h{horizon}.spearman.mean",
    "cs_z": "cs.h{horizon}.spearman.hac_z",
    "cs_p": "cs.h{horizon}.spearman.hac_p_value",
    "ts_ic": "ts.h{horizon}.spearman.mean",
    "ts_cosine": "ts.h{horizon}.cosine.mean",
    "ts_timing": "ts.h{horizon}.cosine.mean_timing",
}
"""Board columns read from the metrics, by the metric name at a horizon."""

Sample = Literal["in_sample", "holdout"]
"""Which side of the holdout boundary a trial evaluated."""


class HoldoutError(ValueError):
    """Refuse a window that crosses the holdout boundary from the side it was asked for."""


class UnknownTrialError(LookupError):
    """Refuse an identifier that no finished trial of the study has."""


class Trial(BaseModel):
    """The record of one evaluation: what was evaluated, on which sample, and its metrics.

    Fields this version does not know are ignored when a record is read, so a record written by
    another tool with the same core fields still counts as a trial. A record of another
    `format_version` is unreadable.
    """

    model_config = ConfigDict(extra="ignore", frozen=True)

    format_version: Literal[1] = FORMAT_VERSION
    """Version of the record layout."""

    id: str
    """Identifier, which is also the name of the trial's directory."""

    created_at: datetime
    """When the evaluation ran, in UTC."""

    signal: str
    """Name of the signal evaluated."""

    family: str
    """Name the trials are counted under: the signal's name unless the caller pooled several
    signals that test one idea under a common name."""

    summary: str | None = None
    """One line saying what the signal bets on."""

    parameters: dict[str, JsonValue] = Field(default_factory=dict)
    """The signal's parameters."""

    sample: Sample
    """`in_sample` before the holdout boundary, `holdout` from it on."""

    holdout_start: datetime | None = None
    """The study's holdout boundary when the evaluation ran."""

    start: datetime
    """Inclusive start of the evaluated window, in UTC."""

    end: datetime
    """Exclusive end of the evaluated window, in UTC."""

    horizons: list[int]
    """Forward-return horizons, in bars."""

    delay: int = 0
    """Bars between a score and the start of its label."""

    assets: list[str] = Field(default_factory=list)
    """Assets with prices in the evaluation."""

    bar_seconds: float | None = None
    """Spacing of the bars in seconds if regular, otherwise `None`."""

    data_fingerprint: str | None = None
    """SHA-256 of the factor and price tables evaluated."""

    versions: dict[str, str | None] = Field(default_factory=dict)
    """Versions of alphatonic and of whatever the caller names, such as its own code."""

    context: dict[str, str] = Field(default_factory=dict)
    """Facts the caller supplied, such as how returns were adjusted or what checks the signal
    passed, shown in the tearsheet and the board."""

    note: str | None = None
    """The researcher's note, such as why this variant was run."""

    metrics: dict[str, float] = Field(default_factory=dict)
    """The flat metrics of [`Evaluation.metrics`][alphatonic.Evaluation.metrics]."""

    @model_validator(mode="before")
    @classmethod
    def _family_defaults_to_signal(cls, data: Any) -> Any:
        if isinstance(data, dict) and data.get("family") is None and "signal" in data:
            return {**data, "family": data["signal"]}
        return data


class Study:
    """Keep every evaluation of a research question as a trial in one directory.

    Run evaluations through [`evaluate`][alphatonic.Study.evaluate] instead of
    [`alphatonic.evaluate`][alphatonic.evaluate]: the study saves each result, refuses windows
    that cross the holdout boundary, and counts trials per family. Read the trials back with
    [`trials`][alphatonic.Study.trials] and compare them with [`board`][alphatonic.Study.board].
    Delete nothing from the directory: the trial count is what keeps the p-values honest.

    Args:
        directory: Where the trials are kept. It is created by the first evaluation.
        holdout_start: First timestamp of the holdout period. In-sample evaluations end before
            it, and only an evaluation that asks for the holdout reads from it on. `None` means
            no holdout. Naive timestamps are UTC.
        name: The project's name, shown in each tearsheet's specification and on the list of
            trials.
    """

    def __init__(
        self,
        directory: str | Path,
        *,
        holdout_start: datetime | pd.Timestamp | str | None = None,
        name: str | None = None,
    ) -> None:
        self.directory = Path(directory)
        self.holdout_start = _utc(holdout_start)
        self.name = name

    def __repr__(self) -> str:
        """Describe the study by its directory and holdout boundary."""
        return f"Study({str(self.directory)!r}, holdout_start={self.holdout_start!r})"

    def window(
        self,
        start: datetime | pd.Timestamp | str | None = None,
        end: datetime | pd.Timestamp | str | None = None,
        *,
        holdout: bool = False,
    ) -> tuple[datetime | None, datetime | None]:
        """Return the evaluation window after applying the holdout rule.

        An in-sample window ends at the holdout boundary unless it ends earlier; a holdout window
        starts there unless it starts later. Call this before computing a signal to know which
        data it may read.

        Args:
            start: Inclusive start, or `None` for the first score (the boundary on the holdout).
            end: Exclusive end, or `None` for the end of the prices (the boundary in sample).
            holdout: Evaluate the holdout instead of the in-sample period.

        Returns:
            The start and end, as UTC datetimes or `None`.

        Raises:
            HoldoutError: If an in-sample window ends after the boundary, a holdout window starts
                before it, the holdout is asked for and the study has none, or the window is
                empty.
        """
        first, last, boundary = _utc(start), _utc(end), self.holdout_start
        if boundary is None:
            if holdout:
                raise HoldoutError("this study has no holdout; pass holdout_start to Study")
        elif holdout:
            first = first or boundary
            if first < boundary:
                raise HoldoutError(
                    f"a holdout evaluation starts at or after {boundary:%Y-%m-%d %H:%M}, "
                    f"not {first:%Y-%m-%d %H:%M}"
                )
        else:
            last = last or boundary
            if last > boundary:
                raise HoldoutError(
                    f"an in-sample evaluation ends at or before the holdout start "
                    f"{boundary:%Y-%m-%d %H:%M}, not {last:%Y-%m-%d %H:%M}; pass holdout=True to "
                    f"evaluate the holdout"
                )
        if first is not None and last is not None and last <= first:
            raise HoldoutError(f"the window [{first}, {last}) is empty")
        return first, last

    def evaluate(
        self,
        factor: pd.DataFrame | pd.Series,
        prices: pd.DataFrame,
        config: EvaluationConfig | None = None,
        *,
        signal: str,
        summary: str | None = None,
        family: str | None = None,
        parameters: dict[str, JsonValue] | None = None,
        holdout: bool = False,
        context: dict[str, str] | None = None,
        versions: dict[str, str | None] | None = None,
        note: str | None = None,
        report: bool = True,
        progress: ProgressFactory = silent,
        **options: Any,
    ) -> Trial:
        """Evaluate `factor` against `prices`, save the result as a trial, and return its record.

        The window of `config` passes through [`window`][alphatonic.Study.window] first. When the
        prices end before the window does, the window ends with them, so the record states the
        period evaluated. A failed evaluation saves nothing and is not counted.

        Args:
            factor: Scores, as for [`alphatonic.evaluate`][alphatonic.evaluate].
            prices: Prices, as for `alphatonic.evaluate`.
            config: The evaluation options.
            signal: Name of the signal, used in the identifier and the tearsheet's title.
            summary: One line saying what the signal bets on.
            family: Name to count the trial under; default: `signal`. Give variants of one idea
                under different names a common family so that they are counted together.
            parameters: The signal's parameters, recorded and shown under the title.
            holdout: Evaluate the holdout period. Each such evaluation is counted.
            context: Labelled facts to record and show, such as `{"Returns": "net of funding"}`.
                Keys must differ from the columns of [`board`][alphatonic.Study.board].
            versions: Versions to record next to alphatonic's, such as your code's commit.
            note: A note stored with the trial.
            report: Write the tearsheet. Needs `alphatonic[report]`.
            progress: A progress display; see `alphatonic.progress`.
            **options: Fields of `EvaluationConfig`, instead of `config`.

        Returns:
            The trial's record.

        Raises:
            HoldoutError: If the window crosses the holdout boundary.
            TypeError: If an input has the wrong type, or both `config` and options are given.
            ValueError: If an input, an option or a context key is invalid.
        """
        if config is not None and options:
            raise TypeError("pass either a config or keyword options, not both")
        config = config or EvaluationConfig(**options)
        clashes = sorted(set(context or {}) & {"id", *BOARD_COLUMNS})
        if clashes:
            raise ValueError(f"context keys {clashes} are board columns; rename them")
        start, end = self.window(config.start, config.end, holdout=holdout)
        data_end = _data_end(prices)
        if data_end is not None:
            if start is not None and start >= data_end:
                raise ValueError(
                    f"the prices end at {data_end:%Y-%m-%d %H:%M}, at or before the window "
                    f"starts at {start:%Y-%m-%d %H:%M}"
                )
            if end is not None and end > data_end:
                end = data_end
        config = config.model_copy(update={"start": start, "end": end})
        result = evaluate(factor, prices, config, progress=progress)

        created = datetime.now(UTC)
        trial = Trial(
            id=f"{created:%Y%m%d-%H%M%S}-{_slug(signal)}-{uuid4().hex[:6]}",
            created_at=created,
            signal=signal,
            family=family or signal,
            summary=summary,
            parameters=parameters or {},
            sample="holdout" if holdout else "in_sample",
            holdout_start=self.holdout_start,
            start=result.start.to_pydatetime(),
            end=result.end.to_pydatetime(),
            horizons=list(config.horizons),
            delay=config.delay,
            assets=_assets(result),
            bar_seconds=None if result.bar is None else result.bar.total_seconds(),
            data_fingerprint=_fingerprint(factor, prices),
            versions={"alphatonic": _version(), **(versions or {})},
            context=context or {},
            note=note,
            metrics=result.metrics(),
        )
        directory = self.directory / trial.id
        result.save(directory / TABLES)
        if report:
            count = 1 + sum(item.family == trial.family for item in self.trials())
            result.tearsheet(directory / TEARSHEET, **self._tearsheet(trial, count))
        partial = directory / f"{RECORD}.partial"
        partial.write_text(trial.model_dump_json(indent=2) + "\n", encoding="utf-8")
        partial.replace(directory / RECORD)
        return trial

    def trials(self) -> list[Trial]:
        """Return every finished trial, newest first; see `unreadable` for records that fail."""
        return self._scan()[0]

    def unreadable(self) -> list[Path]:
        """Return the records that exist but cannot be read, such as a truncated file."""
        return self._scan()[1]

    def trial(self, identifier: str) -> Trial:
        """Return the record of one finished trial.

        Raises:
            UnknownTrialError: If the identifier is malformed or no finished trial has it.
        """
        path = self.directory / identifier / RECORD
        if not IDENTIFIER.match(identifier) or not path.is_file():
            raise UnknownTrialError(
                f"no finished trial is called {identifier!r} in {self.directory}"
            )
        return Trial.model_validate_json(path.read_text(encoding="utf-8"))

    def evaluation(self, identifier: str) -> Evaluation:
        """Reload the tables of one finished trial.

        Raises:
            UnknownTrialError: If the identifier is malformed or no finished trial has it.
        """
        self.trial(identifier)
        return Evaluation.load(self.directory / identifier / TABLES)

    def board(
        self,
        horizon: int | None = None,
        *,
        sort: str | None = None,
        descending: bool | None = None,
    ) -> pd.DataFrame:
        """Return one row per trial with its headline statistics at one horizon, newest first.

        Trials are counted per family, across all parameters and both samples, and `adjusted_p`
        is the cross-sectional p-value times that count, at most 1: Bonferroni's correction over
        the family. The count is a lower bound on the alternatives tried, because variants run
        outside the study, or abandoned before evaluation, are not in it.

        Args:
            horizon: Horizon of the statistics, in bars; default: the smallest horizon of any
                trial.
            sort: A column to sort by instead, such as `adjusted_p`: any column but
                `parameters`, including the context keys. Rows without a value come last.
            descending: Largest first; default: largest first for the ICs, z-statistics, counts
                and `created_at`, smallest first for everything else.

        Returns:
            A table indexed by trial identifier with the columns in `BOARD_COLUMNS`, then one
            column per context key. Statistics a trial lacks at the horizon are `NaN`.

        Raises:
            ValueError: If `sort` names no sortable column. The message lists them.
        """
        return self._board(self.trials(), horizon, sort, descending)

    def to_dict(
        self,
        horizon: int | None = None,
        *,
        sort: str | None = None,
        descending: bool | None = None,
    ) -> dict[str, Any]:
        """Return the study as plain JSON values: its trials with the board's statistics.

        The trials come in the order of [`board`][alphatonic.Study.board] with the same
        arguments, newest first by default, and carry the board's columns, so a page that lists
        them needs nothing else. Missing statistics are `None`, timestamps are ISO 8601 strings
        in UTC, and `json.dumps(..., allow_nan=False)` succeeds. The results reference describes
        the layout.

        Args:
            horizon: Horizon of the statistics, in bars; default: the smallest of any trial.
            sort: A board column to sort by; default: `created_at`.
            descending: Largest first; default: the column's own direction, as for `board`.

        Returns:
            A dictionary with `format` (`"alphatonic.study"`), `format_version`, `name`,
            `holdout_start`, `horizon`, `horizons` (of all trials), `sort`, `descending`,
            `context_keys`, `families`, `trials` and `unreadable`.

        Raises:
            ValueError: If `sort` names no sortable column. The message lists them.
        """
        trials, unreadable = self._scan()
        horizons = sorted({h for trial in trials for h in trial.horizons})
        if horizon is None:
            horizon = horizons[0] if horizons else None
        sort = sort or "created_at"
        descending = sort in DESCENDING if descending is None else descending
        board = self._board(trials, horizon, sort, descending)
        records = {trial.id: trial for trial in trials}
        families: dict[str, dict[str, int]] = {}
        for trial in trials:
            counts = families.setdefault(trial.family, {"trials": 0, "holdout_uses": 0})
            counts["trials"] += 1
            counts["holdout_uses"] += trial.sample == "holdout"
        keys = list(dict.fromkeys(key for trial in trials for key in trial.context))
        rows = []
        for identifier, row in board.iterrows():
            trial = records[str(identifier)]
            tearsheet = self.directory / trial.id / TEARSHEET
            rows.append(
                {
                    "id": trial.id,
                    "created_at": trial.created_at,
                    "signal": trial.signal,
                    "family": trial.family,
                    "summary": trial.summary,
                    "parameters": trial.parameters,
                    "note": trial.note,
                    "sample": trial.sample,
                    "start": trial.start,
                    "end": trial.end,
                    "horizons": trial.horizons,
                    "delay": trial.delay,
                    "assets": len(trial.assets) or None,
                    "bar_seconds": trial.bar_seconds,
                    **{column: row[column] for column in (*_STATISTICS, "adjusted_p")},
                    "trials": row["trials"],
                    "holdout_uses": row["holdout_uses"],
                    "context": trial.context,
                    "files": {
                        "record": f"{trial.id}/{RECORD}",
                        "tearsheet": f"{trial.id}/{TEARSHEET}" if tearsheet.is_file() else None,
                    },
                }
            )
        document = {
            "format": "alphatonic.study",
            "format_version": JSON_FORMAT_VERSION,
            "name": self.name,
            "holdout_start": self.holdout_start,
            "horizon": horizon,
            "horizons": horizons,
            "sort": sort,
            "descending": descending,
            "context_keys": keys,
            "families": families,
            "trials": rows,
            "unreadable": [path.relative_to(self.directory).as_posix() for path in unreadable],
        }
        return cast(dict[str, Any], jsonable(document))

    def _board(
        self,
        trials: list[Trial],
        horizon: int | None,
        sort: str | None,
        descending: bool | None,
    ) -> pd.DataFrame:
        if horizon is None:
            horizon = min((h for trial in trials for h in trial.horizons), default=1)
        counts = Counter(trial.family for trial in trials)
        holdout = Counter(trial.family for trial in trials if trial.sample == "holdout")
        rows = []
        for trial in trials:
            bar = None if trial.bar_seconds is None else pd.Timedelta(seconds=trial.bar_seconds)
            statistics = {
                column: trial.metrics.get(name.format(horizon=horizon), np.nan)
                for column, name in _STATISTICS.items()
            }
            rows.append(
                {
                    "id": trial.id,
                    "created_at": trial.created_at,
                    "signal": trial.signal,
                    "family": trial.family,
                    "parameters": trial.parameters,
                    "sample": trial.sample,
                    "start": trial.start,
                    "end": trial.end,
                    "assets": len(trial.assets) or None,
                    "bar": bar,
                    "horizon": horizon,
                    **statistics,
                    "adjusted_p": float(np.minimum(1.0, statistics["cs_p"] * counts[trial.family])),
                    "trials": counts[trial.family],
                    "holdout_uses": holdout[trial.family],
                    "note": trial.note,
                    **trial.context,
                }
            )
        keys = list(dict.fromkeys(key for trial in trials for key in trial.context))
        board = pd.DataFrame(rows, columns=["id", *BOARD_COLUMNS, *keys]).set_index("id")
        numbers = [*_STATISTICS, "adjusted_p"]
        board[numbers] = board[numbers].astype(float)
        board["assets"] = board["assets"].astype("Int64")
        if sort is None:
            return board
        if sort not in board.columns or sort == "parameters":
            names = ", ".join(column for column in board.columns if column != "parameters")
            raise ValueError(f"cannot sort by {sort!r}; sort by one of {names}")
        reverse = sort in DESCENDING if descending is None else descending
        return board.sort_values(sort, ascending=not reverse, na_position="last", kind="stable")

    def _scan(self) -> tuple[list[Trial], list[Path]]:
        trials, unreadable = [], []
        if not self.directory.is_dir():
            return [], []
        for path in sorted(self.directory.glob(f"*/{RECORD}")):
            try:
                trials.append(Trial.model_validate_json(path.read_text(encoding="utf-8")))
            except (ValidationError, OSError):
                unreadable.append(path)
        trials.sort(key=lambda trial: trial.created_at, reverse=True)
        return trials, unreadable

    def _tearsheet(self, trial: Trial, count: int) -> dict[str, Any]:
        parameters = ", ".join(f"{name}={value}" for name, value in trial.parameters.items())
        context = {
            "Signal": f"{trial.signal}: {trial.summary}" if trial.summary else trial.signal,
            "Assets": _assets_line(trial.assets),
            "Sample": "holdout" if trial.sample == "holdout" else "in sample",
            "Trials": f"{count} of {trial.family}, this one included",
            **trial.context,
        }
        if trial.note:
            context["Note"] = trial.note
        versions = ", ".join(f"{name} {value}" for name, value in trial.versions.items() if value)
        options: dict[str, Any] = {
            "title": trial.signal,
            "subtitle": parameters or None,
            "context": context,
            "footer": [
                f"Trial {trial.id}",
                f"Data fingerprint {(trial.data_fingerprint or '')[:16]}",
                versions,
            ],
        }
        if self.name:
            options["context"] = {"Study": self.name, **context}
        return options


def _slug(name: str) -> str:
    """Turn a signal's name into the part of an identifier that names it."""
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", name).strip("-._")
    return slug or "signal"


def _assets_line(assets: list[str], shown: int = 20) -> str:
    """Count the assets and name the first `shown` of them."""
    names = ", ".join(assets[:shown])
    more = len(assets) - shown
    return f"{len(assets)}: {names}" + (f", and {more} more" if more > 0 else "")


def _data_end(prices: pd.DataFrame) -> datetime | None:
    """One median bar after the last price, which is where `evaluate` ends a window by default."""
    if not isinstance(prices, pd.DataFrame) or len(prices) < 2:
        return None
    index = utc_index(prices.index, "prices").sort_values()
    return cast(pd.Timestamp, index[-1] + index.to_series().diff().median()).to_pydatetime()


def _assets(result: Evaluation) -> list[str]:
    """The assets of the evaluation's price table, which the time-series table lists in order."""
    if result.time_series is None:
        return []
    return [str(asset) for asset in dict.fromkeys(result.time_series.assets["asset"])]


def _fingerprint(factor: pd.DataFrame | pd.Series, prices: pd.DataFrame) -> str:
    """Return a SHA-256 over the tables' values, indexes and column labels."""
    digest = hashlib.sha256()
    for table in (factor, prices):
        digest.update(pd.util.hash_pandas_object(table, index=True).to_numpy().tobytes())
        if isinstance(table, pd.DataFrame):
            digest.update(np.asarray(table.columns, dtype=str).tobytes())
    return digest.hexdigest()


def _version() -> str:
    from alphatonic import __version__

    return __version__


__all__ = [
    "BOARD_COLUMNS",
    "DESCENDING",
    "RECORD",
    "TABLES",
    "TEARSHEET",
    "HoldoutError",
    "Study",
    "Trial",
    "UnknownTrialError",
]
