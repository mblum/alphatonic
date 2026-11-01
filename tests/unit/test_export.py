import json
from datetime import timedelta

import numpy as np
import pandas as pd
import pytest

from alphatonic.export import columns, jsonable


def test_recursive_strict_json_scalars_nullable_and_durations():
    value = {
        1: (
            np.int64(2),
            np.bool_(True),
            np.nan,
            np.inf,
            pd.NA,
            pd.NaT,
            np.array([3.0, np.nan]),
            timedelta(seconds=2.5),
            np.datetime64("2024-01-01"),
        )
    }
    result = jsonable(value)
    assert result == {
        "1": [2, True, None, None, None, None, [3.0, None], 2.5, "2024-01-01T00:00:00"]
    }
    json.dumps(result, allow_nan=False)
    with pytest.raises(TypeError, match="no JSON form"):
        jsonable(object())


def test_columns_preserve_schema_and_utc_microseconds():
    frame = pd.DataFrame(
        {
            "f": [1.0, np.inf],
            "i": pd.Series([1, pd.NA], dtype="Int64"),
            "b": [True, False],
            "s": ["x", None],
            "t": pd.to_datetime(["2024-01-01T00:00:00.123456Z", None]),
        }
    )
    result = columns(frame)
    assert list(result) == list(frame)
    assert result == {
        "f": [1.0, None],
        "i": [1, None],
        "b": [True, False],
        "s": ["x", None],
        "t": ["2024-01-01T00:00:00.123456+00:00", None],
    }
    json.dumps(result, allow_nan=False)


def test_datetime_columns_preserve_nanosecond_precision():
    # ISO timestamps must preserve the score grid: two distinct nanosecond bars stay distinct.
    frame = pd.DataFrame(
        {
            "time": pd.to_datetime(
                ["2024-01-01T00:00:00.123456001Z", "2024-01-01T00:00:00.123456999Z"]
            )
        }
    )
    result = columns(frame)["time"]
    assert result == ["2024-01-01T00:00:00.123456001+00:00", "2024-01-01T00:00:00.123456999+00:00"]


def test_hand_authored_scalar_export_contract():
    from pathlib import Path

    expected = json.loads((Path(__file__).parents[1] / "data/exports/scalars.json").read_text())
    actual = jsonable(
        {
            "number": np.int64(2),
            "flag": np.bool_(True),
            "missing": np.nan,
            "duration": pd.Timedelta(2.5, "s"),
        }
    )
    assert actual == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        (np.timedelta64(5, "s"), 5.0),
        (np.timedelta64(1500, "ms"), 1.5),
        (np.timedelta64("NaT", "s"), None),
        (np.datetime64("NaT", "ns"), None),
    ],
)
def test_numpy_time_scalars_convert_units_and_missingness(value, expected):
    assert jsonable(value) == expected
