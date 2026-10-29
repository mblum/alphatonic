"""Write an evaluation to a directory of CSV files and read it back."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Literal, TypedDict, cast

import pandas as pd

from alphatonic.config import EvaluationConfig
from alphatonic.evaluation import Evaluation
from alphatonic.signal_persistence import TABLES as PERSISTENCE_TABLES
from alphatonic.signal_persistence import PersistenceEvaluation
from alphatonic.time_series import TABLES, TimeSeriesEvaluation

FORMAT_VERSION = 3
"""Format 3 adds signal persistence; formats 1 and 2 remain readable."""
READABLE_FORMATS = (1, 2, 3)
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


# Before pandas 3 the default CSV parser can be off in the last digit, and saved tables must load
# back exactly. From pandas 3 the default is exact and the option is deprecated.
_CSV_OPTIONS: _CSVOptions = (
    {"float_precision": "round_trip"} if int(pd.__version__.split(".")[0]) < 3 else {}
)


def _version() -> str:
    from alphatonic import __version__

    return __version__


def save(evaluation: Evaluation, directory: Path) -> Path:
    """Write `evaluation` into `directory`; see `Evaluation.save`."""
    directory.mkdir(parents=True, exist_ok=True)
    evaluation.periods.to_csv(directory / PERIODS, index=False)
    evaluation.summary.to_csv(directory / SUMMARY, index=False)
    evaluation.monthly_ic().to_csv(directory / MONTHLY)
    evaluation.quantiles.to_csv(directory / QUANTILES, index=False)
    if evaluation.time_series is not None:
        for name, table in evaluation.time_series.tables().items():
            table.to_csv(directory / f"ts_{name}.csv", index=False)
    if evaluation.persistence is not None:
        for name, table in evaluation.persistence.tables().items():
            table.to_csv(directory / f"persistence_{name}.csv", index=False)
    else:
        # Do not leave stale diagnostics when replacing a previously saved evaluation.
        for name in PERSISTENCE_TABLES:
            (directory / f"persistence_{name}.csv").unlink(missing_ok=True)
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
    table = pd.read_csv(directory / name, **_CSV_OPTIONS)
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
    quantiles_path = directory / QUANTILES
    quantiles = (
        _read(directory, QUANTILES, "quantiles")
        if quantiles_path.is_file()
        else pd.DataFrame(columns=["timestamp", "horizon", "quantile", "mean_return", "n_pairs"])
    )
    time_series = None
    if (directory / "ts_assets.csv").is_file():
        time_series = TimeSeriesEvaluation(
            **{name: _read(directory, f"ts_{name}.csv", name) for name in TABLES}
        )
    persistence = None
    if (directory / "persistence_summary.csv").is_file():
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
