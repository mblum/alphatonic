import numpy as np
import pandas as pd
import pytest

from alphatonic import EvaluationConfig, evaluate
from alphatonic.inputs import clean_factor, clean_prices, prepare
from conftest import regular_panel


def long_form(frame: pd.DataFrame, swap: bool = False) -> pd.Series:
    series = frame.stack()
    series.index.names = ["date", "asset"]
    return series.swaplevel().sort_index() if swap else series


def test_timestamps_are_read_as_utc():
    naive_factor, naive_prices = regular_panel(n_bars=30, freq="D")
    naive_factor.index = naive_factor.index.tz_localize(None)
    naive_prices.index = naive_prices.index.tz_localize(None)
    aware_factor = naive_factor.tz_localize("UTC")
    aware_prices = naive_prices.tz_localize("UTC")
    a = prepare(naive_factor, naive_prices, EvaluationConfig())
    b = prepare(aware_factor, aware_prices, EvaluationConfig())
    pd.testing.assert_frame_equal(a.prices, b.prices)
    assert str(a.prices.index.tz) == "UTC" and a.prices.index.dtype == "datetime64[ns, UTC]"


def test_other_timezones_are_converted_to_utc():
    factor, prices = regular_panel(n_bars=30, freq="D")
    local = prices.tz_convert("America/New_York")
    panel = prepare(factor.tz_convert("America/New_York"), local, EvaluationConfig())
    assert str(panel.prices.index.tz) == "UTC"
    assert panel.prices.index.equals(prices.index)


@pytest.mark.parametrize("swap", [False, True])
def test_long_series_equals_wide_frame(swap):
    factor, prices = regular_panel(n_bars=40, freq="D", missing=0.05)
    wide = clean_factor(factor)
    long = clean_factor(long_form(factor, swap=swap))
    pd.testing.assert_frame_equal(
        long.sort_index(axis=1), wide.sort_index(axis=1), check_freq=False
    )
    config = EvaluationConfig(horizons=[1], time_series={"bootstrap_samples": 0})
    pd.testing.assert_frame_equal(
        evaluate(long_form(factor, swap), prices, config).periods,
        evaluate(factor, prices, config).periods,
    )


def test_infinite_scores_are_missing_scores():
    factor, _ = regular_panel(n_bars=10)
    factor.iloc[2, 1] = np.inf
    factor.iloc[3, 2] = -np.inf
    cleaned = clean_factor(factor)
    assert np.isnan(cleaned.iloc[2, 1]) and np.isnan(cleaned.iloc[3, 2])


def test_integer_asset_labels_are_supported():
    factor, prices = regular_panel(n_bars=40, freq="D")
    factor.columns = prices.columns = range(len(prices.columns))
    result = evaluate(factor, prices, horizons=[1], time_series={"bootstrap_samples": 0})
    assert result.summary.n_periods.max() > 0
    assert set(result.time_series.assets.asset) == set(range(6))


@pytest.mark.parametrize(
    "mutate, error, message",
    [
        (lambda p: p.reset_index(drop=True), TypeError, "DatetimeIndex"),
        (lambda p: p.iloc[::-1], ValueError, "sorted"),
        (lambda p: pd.concat([p, p.iloc[:1]]).sort_index(), ValueError, "duplicate timestamps"),
        (lambda p: p.assign(A0=-1.0), ValueError, "positive"),
        (lambda p: p.assign(A0=0.0), ValueError, "positive"),
        (lambda p: p.assign(A0=np.inf), ValueError, "finite"),
        (lambda p: p.astype(object).assign(A0="abc"), ValueError, "numeric"),
        (lambda p: pd.concat({"close": p}, axis=1), ValueError, "one column level"),
        (lambda p: p.set_axis(["A0"] * p.shape[1], axis=1), ValueError, "duplicate asset"),
    ],
)
def test_malformed_prices_are_rejected(mutate, error, message):
    _, prices = regular_panel(n_bars=20, freq="D")
    with pytest.raises(error, match=message):
        clean_prices(mutate(prices))


def test_prices_must_be_a_dataframe():
    with pytest.raises(TypeError, match="DataFrame"):
        clean_prices(pd.Series([1.0, 2.0]))


def test_missing_prices_are_allowed():
    _, prices = regular_panel(n_bars=20, freq="D", missing=0.2)
    assert clean_prices(prices).isna().any().any()


@pytest.mark.parametrize(
    "factor, error, message",
    [
        ([1, 2, 3], TypeError, "wide DataFrame"),
        (pd.Series([1.0, 2.0]), ValueError, "two-level"),
        (
            pd.Series([1.0], index=pd.MultiIndex.from_tuples([("a", "b")])),
            TypeError,
            "timestamps",
        ),
        (
            pd.Series(
                [1.0, 2.0],
                index=pd.MultiIndex.from_tuples(
                    [(pd.Timestamp("2026-01-01"), "A"), (pd.Timestamp("2026-01-01"), "A")]
                ),
            ),
            ValueError,
            "duplicate",
        ),
        (
            pd.DataFrame(
                np.ones((2, 1)),
                index=pd.MultiIndex.from_product(
                    [pd.date_range("2026-01-01", periods=1), ["A", "B"]]
                ),
            ),
            ValueError,
            "wide",
        ),
    ],
)
def test_malformed_factors_are_rejected(factor, error, message):
    with pytest.raises(error, match=message):
        clean_factor(factor)


def test_unsorted_factor_rows_are_sorted():
    factor, _ = regular_panel(n_bars=10, freq="D")
    assert clean_factor(factor.iloc[::-1]).index.is_monotonic_increasing


def test_assets_without_prices_are_dropped_with_a_warning():
    factor, prices = regular_panel(n_bars=30, freq="D")
    factor["EXTRA"] = 1.0
    with pytest.warns(UserWarning, match="1 factor assets have no prices.*EXTRA"):
        panel = prepare(factor, prices, EvaluationConfig())
    assert list(panel.factor.columns) == list(prices.columns)


def test_assets_without_scores_stay_with_missing_scores():
    factor, prices = regular_panel(n_bars=30, freq="D")
    panel = prepare(factor.drop(columns="A0"), prices, EvaluationConfig())
    assert list(panel.factor.columns) == list(prices.columns)
    assert panel.factor["A0"].isna().all()


def test_scores_on_timestamps_without_prices_are_an_error():
    factor, prices = regular_panel(n_bars=30, freq="D")
    with pytest.raises(ValueError, match="not in prices.*2026-01-05"):
        prepare(factor, prices.drop(prices.index[4]), EvaluationConfig())


def test_empty_rows_on_timestamps_without_prices_are_ignored():
    factor, prices = regular_panel(n_bars=30, freq="D")
    factor.iloc[4] = np.nan
    panel = prepare(factor, prices.drop(prices.index[4]), EvaluationConfig())
    assert len(panel.factor) == 29


def test_default_window_runs_from_first_score_to_one_bar_after_last_price():
    factor, prices = regular_panel(n_bars=30, freq="D")
    factor.iloc[:5] = np.nan
    panel = prepare(factor, prices, EvaluationConfig())
    assert panel.start == factor.index[5]
    assert panel.end == prices.index[-1] + pd.Timedelta(days=1)
    assert panel.factor.index[0] == panel.start and len(panel.prices) == 25
    assert panel.bar == pd.Timedelta(days=1)


def test_factor_history_before_the_window_is_ignored():
    factor, prices = regular_panel(n_bars=40, freq="D")
    start = factor.index[10]
    panel = prepare(factor, prices, EvaluationConfig(start=start))
    assert panel.factor.index[0] == start and len(panel.factor) == 30


def test_prices_at_or_after_end_are_not_used():
    factor, prices = regular_panel(n_bars=40, freq="D")
    end = prices.index[30]
    panel = prepare(factor, prices, EvaluationConfig(end=end))
    assert panel.factor.index[-1] == prices.index[29] and panel.end == end
    assert len(panel.prices) == 30


@pytest.mark.parametrize(
    "config, message",
    [
        (EvaluationConfig(start="2030-01-01", end="2030-02-01"), "no rows"),
        (EvaluationConfig(start="2020-01-01", end="2020-02-01"), "no rows"),
    ],
)
def test_windows_without_bars_are_rejected(config, message):
    factor, prices = regular_panel(n_bars=30, freq="D")
    with pytest.raises(ValueError, match=message):
        prepare(factor, prices, config)


def test_all_missing_factor_is_rejected():
    factor, prices = regular_panel(n_bars=30, freq="D")
    with pytest.raises(ValueError, match="no finite scores"):
        prepare(factor * np.nan, prices, EvaluationConfig())


def test_single_row_prices_are_rejected():
    factor, prices = regular_panel(n_bars=30, freq="D")
    with pytest.raises(ValueError, match="at least two rows"):
        prepare(factor.iloc[:1], prices.iloc[:1], EvaluationConfig())


def test_bar_is_known_only_for_regular_grids():
    factor, prices = regular_panel(n_bars=60, freq="B")
    assert prepare(factor, prices, EvaluationConfig()).bar is None
    factor, prices = regular_panel(n_bars=60, freq="h")
    assert prepare(factor, prices, EvaluationConfig()).bar == pd.Timedelta(hours=1)


def test_inputs_are_not_modified():
    factor, prices = regular_panel(n_bars=30, freq="D", missing=0.1)
    before = factor.copy(), prices.copy()
    prepare(factor, prices, EvaluationConfig())
    pd.testing.assert_frame_equal(factor, before[0])
    pd.testing.assert_frame_equal(prices, before[1])


def test_completely_mismatched_asset_labels_are_an_error_that_shows_both_sides():
    factor, prices = regular_panel(n_bars=30, freq="D")
    factor.columns = range(len(factor.columns))
    with pytest.raises(ValueError, match=r"no factor asset has prices.*\[0, 1, 2\].*A0"):
        prepare(factor, prices, EvaluationConfig())
