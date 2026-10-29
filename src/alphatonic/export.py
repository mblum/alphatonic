"""Plain JSON values for results: the contract behind `Evaluation.to_dict` and `Study.to_dict`.

Both documents pass `json.dumps(document, allow_nan=False)`: a missing value is `null`, never
`NaN` and never zero. Timestamps are ISO 8601 strings in UTC, durations are seconds, and a table
is an object of equally long columns, `{"column": [value, ...]}`, in the table's column order.
The results reference describes every field.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from datetime import date, datetime, timedelta
from typing import Any, Final

import numpy as np
import pandas as pd

FORMAT_VERSION: Final = 1
"""Version of the layout of both documents. Fields may be added within a version; a change that
renames, removes or reinterprets one increments it."""

Json = None | bool | int | float | str | list["Json"] | dict[str, "Json"]
"""A value `json.dumps` writes as it is."""


def jsonable(value: Any) -> Json:
    """Convert `value`, and anything inside it, to a plain JSON value.

    `None`, `NaN`, infinities, `NaT` and `pd.NA` become `None`. Timestamps become ISO 8601
    strings, durations seconds, NumPy scalars Python numbers, and mappings, lists, tuples and
    arrays are converted item by item.

    Raises:
        TypeError: If a value has no JSON form.
    """
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, bool | np.bool_):
        return bool(value)
    if isinstance(value, int | np.integer):
        return int(value)
    if isinstance(value, float | np.floating):
        number = float(value)
        return number if math.isfinite(number) else None
    if isinstance(value, str):
        return value
    if isinstance(value, datetime | date):  # pd.Timestamp is a datetime.
        return value.isoformat()
    if isinstance(value, np.datetime64):
        return jsonable(pd.Timestamp(value))
    if isinstance(value, timedelta | np.timedelta64):  # pd.Timedelta is a timedelta.
        return pd.Timedelta(value).total_seconds()
    if isinstance(value, Mapping):
        return {str(key): jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | np.ndarray):
        return [jsonable(item) for item in value]
    raise TypeError(f"{type(value).__name__} has no JSON form")


def columns(frame: pd.DataFrame) -> dict[str, list[Json]]:
    """Return a table as `{"column": [value, ...]}`, each value converted as by `jsonable`."""
    return {str(name): _column(frame[name]) for name in frame}


def _column(series: pd.Series) -> list[Json]:
    # Common columns are converted whole: the rolling table can hold millions of values.
    dtype = series.dtype
    if isinstance(dtype, np.dtype) and dtype.kind == "f":
        values = series.to_numpy(dtype=float)
        result = values.astype(object)
        result[~np.isfinite(values)] = None
        return result.tolist()
    if isinstance(dtype, np.dtype) and dtype.kind in "iub":
        return series.to_numpy().tolist()
    if isinstance(dtype, pd.DatetimeTZDtype):
        stamps = series.dt.tz_convert("UTC").dt.tz_localize(None).to_numpy("datetime64[us]")
        whole = stamps.astype("datetime64[s]") == stamps
        text = np.where(
            whole,
            np.datetime_as_string(stamps, unit="s"),
            np.datetime_as_string(stamps, unit="us"),
        ).astype(object)
        result = text + "+00:00"
        result[np.isnat(stamps)] = None
        return result.tolist()
    if pd.api.types.infer_dtype(series, skipna=True) in ("string", "empty"):
        return series.astype(object).where(series.notna(), None).tolist()
    return [jsonable(value) for value in series.astype(object)]


__all__ = ["FORMAT_VERSION", "Json", "columns", "jsonable"]
