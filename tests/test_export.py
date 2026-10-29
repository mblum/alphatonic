import json
from datetime import UTC, date, datetime, timedelta

import numpy as np
import pandas as pd
import pytest

from alphatonic.export import columns, jsonable


@pytest.mark.parametrize("missing", [None, np.nan, float("inf"), -np.inf, pd.NaT, pd.NA])
def test_a_missing_value_is_null_never_nan_or_zero(missing):
    assert jsonable(missing) is None


def test_values_become_plain_json():
    stamp = pd.Timestamp("2026-01-02 03:04:05", tz="UTC")

    assert jsonable(np.int64(3)) == 3 and type(jsonable(np.int64(3))) is int
    assert jsonable(np.float32(0.5)) == 0.5 and type(jsonable(np.float32(0.5))) is float
    assert jsonable(np.bool_(True)) is True
    assert jsonable(stamp) == "2026-01-02T03:04:05+00:00"
    assert jsonable(datetime(2026, 1, 2, tzinfo=UTC)) == "2026-01-02T00:00:00+00:00"
    assert jsonable(date(2026, 1, 2)) == "2026-01-02"
    assert jsonable(np.datetime64("2026-01-02T00:00")) == "2026-01-02T00:00:00"
    assert jsonable(pd.Timedelta(hours=1)) == 3600.0
    assert jsonable(timedelta(minutes=15)) == 900.0
    assert jsonable({"a": (1, np.nan), 2: np.array([1.5])}) == {"a": [1, None], "2": [1.5]}


def test_a_value_without_a_json_form_is_refused():
    with pytest.raises(TypeError, match="object has no JSON form"):
        jsonable(object())


def test_a_table_becomes_columns_converted_like_single_values():
    frame = pd.DataFrame(
        {
            "timestamp": pd.Series(
                [
                    pd.Timestamp("2026-01-01", tz="UTC"),
                    pd.NaT,
                    pd.Timestamp("2026-01-01 00:00:00.5", tz="UTC"),
                ],
                dtype="datetime64[ns, UTC]",
            ),
            "ic": [0.1, np.nan, np.inf],
            "n": np.array([1, 2, 3], dtype=np.int64),
            "flag": [True, False, True],
            "status": ["valid", None, np.nan],
            "count": pd.array([1, None, 3], dtype="Int64"),
            "mixed": [1, "a", None],
        }
    )

    table = columns(frame)

    assert list(table) == list(frame.columns)
    assert table["timestamp"] == [
        "2026-01-01T00:00:00+00:00",
        None,
        "2026-01-01T00:00:00.500000+00:00",
    ]
    assert table["ic"] == [0.1, None, None]
    assert table["status"] == ["valid", None, None]
    assert table["count"] == [1, None, 3]
    for name in frame:
        assert table[name] == [jsonable(value) for value in frame[name].astype(object)]
    json.dumps(table, allow_nan=False)
    assert columns(frame.iloc[:0]) == {name: [] for name in frame.columns}
