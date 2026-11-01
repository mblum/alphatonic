import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from alphatonic.inputs import clean_factor, clean_prices, prepare, utc_index


def test_wide_long_level_order_and_unsorted_factor_equivalent(panel, config):
    x, p = panel
    expected = prepare(x, p, config)
    for factor in [x.iloc[::-1], x.stack(), x.stack().swaplevel()]:
        actual = prepare(factor, p, config)
        assert_frame_equal(actual.factor, expected.factor)
        assert_frame_equal(actual.prices, expected.prices)
    assert_frame_equal(x, panel[0])


@pytest.mark.parametrize("clean", [clean_prices, clean_factor])
def test_invalid_shape_and_labels(clean, panel):
    x = panel[0]
    for value, error, match in [
        (x.reset_index(drop=True), TypeError, "DatetimeIndex"),
        (pd.concat([x, x]), ValueError, "duplicate timestamps"),
        (pd.concat([x, x], axis=1), ValueError, "duplicate asset"),
        (x.astype(str).mask(x.notna(), "nonnumeric"), ValueError, "numeric"),
    ]:
        with pytest.raises(error, match=match):
            clean(value)
    bad = x.copy()
    bad.index = pd.DatetimeIndex([pd.NaT, *x.index[1:]])
    with pytest.raises(ValueError, match="NaT"):
        clean(bad)
    bad = x.copy()
    bad.columns = pd.MultiIndex.from_product([["field"], x.columns])
    with pytest.raises(ValueError):
        clean(bad)


@pytest.mark.parametrize("value", [0, -1, np.inf, -np.inf])
def test_prices_reject_nonpositive_or_infinite(panel, value):
    p = panel[1].copy()
    p.iloc[1, 1] = value
    with pytest.raises(ValueError, match="positive|finite"):
        clean_prices(p)


def test_inputs_types_no_scores_short_no_assets_and_off_grid(panel, config):
    x, p = panel
    with pytest.raises(TypeError):
        clean_prices([])
    with pytest.raises(TypeError):
        clean_factor([])
    with pytest.raises(ValueError):
        clean_factor(pd.Series([1, 2]))
    with pytest.raises(TypeError):
        clean_factor(pd.Series([1], index=pd.MultiIndex.from_tuples([("a", "b")])))
    long = x.stack()
    long = pd.concat([long, long])
    with pytest.raises(ValueError, match="duplicate"):
        clean_factor(long)
    with pytest.raises(ValueError, match="sorted"):
        clean_prices(p.iloc[::-1])
    with pytest.raises(ValueError, match="finite scores"):
        prepare(x * np.nan, p, config)
    with pytest.raises(ValueError, match="at least two"):
        prepare(x, p.iloc[:1], config)
    with pytest.raises(ValueError, match="no factor asset"):
        prepare(x.rename(columns=lambda c: c + "x"), p, config)
    stray = x.iloc[:1].copy()
    stray.index += pd.Timedelta(1, "h")
    with pytest.raises(ValueError, match="not in prices"):
        prepare(pd.concat([x, stray]), p, config)
    actual = prepare(pd.concat([x, stray * np.nan]), p, config)
    assert len(actual.factor) == len(x)


def test_overlap_order_warning_missing_assets_and_input_immutability(panel, config):
    x, p = panel
    original = x.copy(deep=True)
    factor = x.iloc[:, :2].assign(unpriced=1)
    with pytest.warns(UserWarning, match="no prices"):
        result = prepare(factor, p, config)
    assert list(result.factor) == list(p)
    assert result.factor.iloc[:, 2:].isna().all().all()
    assert_frame_equal(x, original)
    inf = x.copy()
    inf.iloc[0, 0] = np.inf
    assert pd.isna(clean_factor(inf).iloc[0, 0])


def test_windows_history_regular_irregular_and_timezone(panel, config):
    x, p = panel
    result = prepare(x, p, config.model_copy(update={"start": x.index[10], "end": x.index[30]}))
    assert len(result.factor) == 20 and len(result.history) == 30
    assert result.bar == pd.Timedelta(1, "D")
    result = prepare(x.drop(x.index[20]), p.drop(p.index[20]), config)
    assert result.bar is None
    for kwargs in [
        {"start": pd.Timestamp("2030-01-01", tz="UTC")},
        {
            "start": pd.Timestamp("2030-01-01", tz="UTC"),
            "end": pd.Timestamp("2030-02-01", tz="UTC"),
        },
    ]:
        with pytest.raises(ValueError):
            prepare(x, p, config.model_copy(update=kwargs))
    index = pd.date_range("2024-10-26", periods=4, freq="D", tz="Europe/Berlin")
    assert utc_index(index, "test").equals(index.tz_convert("UTC").rename("timestamp"))
    naive = pd.date_range("2024-01-01", periods=3).as_unit("us")
    assert utc_index(naive, "test").dtype == pd.DatetimeTZDtype("ns", "UTC")
