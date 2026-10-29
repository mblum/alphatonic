"""Write an evaluation to a directory of gzip-compressed CSV files and read it back."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal, TypedDict, cast

import pandas as pd

from alphatonic.config import EvaluationConfig
from alphatonic.evaluation import Evaluation
from alphatonic.signal_persistence import TABLES as PERSISTENCE_TABLES
from alphatonic.signal_persistence import PersistenceEvaluation
from alphatonic.time_series import TABLES, TimeSeriesEvaluation

FORMAT_VERSION = 4
"""Format 4 gzips the tables; formats 1 to 3, which wrote plain CSV, remain readable."""
READABLE_FORMATS = (1, 2, 3, 4)
METADATA = "evaluation.json"
PERIODS = "ic_by_timestamp.csv"
SUMMARY = "ic_summary.csv"
MONTHLY = "ic_monthly.csv"
QUANTILES = "cs_quantiles.csv"
TIME_COLUMNS = {
    "periods": ["timestamp"],
    "quantiles": ["timestamp"],
    "assets": ["window_start", "window_end", "first_pair", "last_pair"],
    "monthly": ["window_start", "window_end", "first_pair", "last_pair"],
    "rolling": ["window_start", "window_end", "first_pair", "last_pair"],
}


class _CSVOptions(TypedDict, total=False):
    float_precision: Literal["round_trip"]


COMPRESSION: Final[dict[str, Any]] = {"method": "gzip", "compresslevel": 6, "mtime": 0}
"""How tables are compressed. Level 6 is nearly as small as 9 in two thirds of the time, and a
fixed `mtime` keeps the bytes the same every time the same evaluation is saved."""

# Before pandas 3 the default CSV parser can be off in the last digit, and saved tables must load
# back exactly. From pandas 3 the default is exact and the option is deprecated.
_CSV_OPTIONS: _CSVOptions = (
    {"float_precision": "round_trip"} if int(pd.__version__.split(".")[0]) < 3 else {}
)


def _version() -> str:
    from alphatonic import __version__

    return __version__


def _write(table: pd.DataFrame, directory: Path, name: str, *, index: bool = False) -> None:
    """Write `table` as `<name>.gz` and remove the plain `<name>` a format 1 to 3 save left."""
    table.to_csv(directory / f"{name}.gz", index=index, compression=COMPRESSION)
    (directory / name).unlink(missing_ok=True)


def _file(directory: Path, name: str) -> Path:
    """Return the file holding table `name`: `<name>.gz` from format 4, else the plain `<name>`."""
    compressed = directory / f"{name}.gz"
    return compressed if compressed.is_file() else directory / name


def save(evaluation: Evaluation, directory: Path) -> Path:
    """Write `evaluation` into `directory`; see `Evaluation.save`."""
    directory.mkdir(parents=True, exist_ok=True)
    _write(evaluation.periods, directory, PERIODS)
    _write(evaluation.summary, directory, SUMMARY)
    _write(evaluation.monthly_ic(), directory, MONTHLY, index=True)
    _write(evaluation.quantiles, directory, QUANTILES)
    if evaluation.time_series is not None:
        for name, table in evaluation.time_series.tables().items():
            _write(table, directory, f"ts_{name}.csv")
    if evaluation.persistence is not None:
        for name, table in evaluation.persistence.tables().items():
            _write(table, directory, f"persistence_{name}.csv")
    else:
        # Do not leave stale diagnostics when replacing a previously saved evaluation.
        for name in PERSISTENCE_TABLES:
            for suffix in ("", ".gz"):
                (directory / f"persistence_{name}.csv{suffix}").unlink(missing_ok=True)
    metadata = {
        "format_version": FORMAT_VERSION,
        "alphatonic_version": _version(),
        "config": evaluation.config.model_dump(mode="json"),
        "start": evaluation.start.isoformat(),
        "end": evaluation.end.isoformat(),
        "bar_seconds": evaluation.bar.total_seconds() if evaluation.bar is not None else None,
    }
    (directory / METADATA).write_text(
        json.dumps(metadata, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return directory


def _read(directory: Path, name: str, key: str) -> pd.DataFrame:
    table = pd.read_csv(_file(directory, name), **_CSV_OPTIONS)
    for column in TIME_COLUMNS.get(key, []):
        if column in table:
            table[column] = pd.to_datetime(table[column], utc=True)
    return table


def load(directory: Path, config: EvaluationConfig | None = None) -> Evaluation:
    """Read the evaluation in `directory`; see `Evaluation.load`."""
    metadata = {}
    if (directory / METADATA).is_file():
        metadata = json.loads((directory / METADATA).read_text(encoding="utf-8"))
        if metadata.get("format_version") not in READABLE_FORMATS:
            raise ValueError(
                f"{directory} uses evaluation format {metadata.get('format_version')!r}; "
                f"this version reads formats {', '.join(map(str, READABLE_FORMATS))}"
            )
    if config is None:
        if "config" not in metadata:
            raise ValueError(
                f"{directory / METADATA} not found; pass the EvaluationConfig the tables came from"
            )
        # Older formats could select one analysis. Preserve their tables as saved, while
        # removing the retired option from the configuration used by current evaluations.
        stored = {key: value for key, value in metadata["config"].items() if key != "mode"}
        if metadata["format_version"] == 1:
            # Format 1 predates the target options: every label was the forward return.
            time_series = {**stored.get("time_series", {}), "target": "return"}
            stored = {**stored, "target": "return", "time_series": time_series}
        config = EvaluationConfig.model_validate(stored)
    periods = _read(directory, PERIODS, "periods")
    summary = _read(directory, SUMMARY, "summary")
    quantiles = (
        _read(directory, QUANTILES, "quantiles")
        if _file(directory, QUANTILES).is_file()
        else pd.DataFrame(columns=["timestamp", "horizon", "quantile", "mean_return", "n_pairs"])
    )
    time_series = None
    if _file(directory, "ts_assets.csv").is_file():
        time_series = TimeSeriesEvaluation(
            **{name: _read(directory, f"ts_{name}.csv", name) for name in TABLES}
        )
    persistence = None
    if _file(directory, "persistence_summary.csv").is_file():
        persistence = PersistenceEvaluation(
            **{
                name: _read(
                    directory,
                    f"persistence_{name}.csv",
                    name if name in {"periods", "quantiles"} else "persistence",
                )
                for name in PERSISTENCE_TABLES
            }
        )
    return Evaluation(
        config=config,
        start=_window_bound(metadata.get("start"), config.start, periods.timestamp.min()),
        end=_window_bound(
            metadata.get("end"), config.end, periods.timestamp.max() + _step(periods)
        ),
        bar=_bar(metadata, periods),
        periods=periods,
        summary=summary,
        quantiles=quantiles,
        time_series=time_series,
        persistence=persistence,
    )


def _step(periods: pd.DataFrame) -> pd.Timedelta:
    steps = periods.timestamp.drop_duplicates().sort_values().diff().dropna()
    return cast(pd.Timedelta, steps.median()) if len(steps) else pd.Timedelta(0)


def _window_bound(
    stored: str | None, configured: datetime | None, fallback: pd.Timestamp
) -> pd.Timestamp:
    value = stored or configured
    return pd.Timestamp(value) if value is not None else fallback


def _bar(metadata: dict, periods: pd.DataFrame) -> pd.Timedelta | None:
    if "bar_seconds" in metadata:
        seconds = metadata["bar_seconds"]
        return None if seconds is None else pd.Timedelta(seconds=seconds)
    steps = periods.timestamp.drop_duplicates().sort_values().diff().dropna()
    return steps.iloc[0] if len(steps) and steps.nunique() == 1 else None
