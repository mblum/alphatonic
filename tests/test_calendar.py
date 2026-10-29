"""Horizons count rows, so trading calendars, 24/7 grids and sparse dates all work."""

import numpy as np
import pandas as pd
import pytest

from alphatonic import evaluate
from conftest import regular_panel

TS = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 0, "rolling_window": "14D"}


def business_days(n_bars=260, seed=0):
    return regular_panel(n_assets=8, n_bars=n_bars, freq="B", start="2024-01-01", seed=seed)


def test_weekends_do_not_remove_labels():
    factor, prices = business_days()
    result = evaluate(factor, prices, horizons=[5], time_series={"bootstrap_samples": 0})
    periods = result.periods
    # Every bar except the last five has a 5-bar label, although weekends are missing rows.
    assert (periods.n_pairs > 0).sum() == len(periods) - 5
    assert periods.n_pairs.iloc[-5:].eq(0).all()


def test_cross_section_depends_on_positions_not_timestamps():
    factor, prices = business_days()
    weekday = evaluate(factor, prices, horizons=[1, 5], time_series={"bootstrap_samples": 0})
    relabeled = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    daily = evaluate(
        factor.set_axis(relabeled),
        prices.set_axis(relabeled),
        horizons=[1, 5],
        time_series={"bootstrap_samples": 0},
    )
    for column in ("spearman", "pearson", "n_pairs", "status"):
        np.testing.assert_array_equal(weekday.periods[column], daily.periods[column])
    pd.testing.assert_frame_equal(weekday.summary, daily.summary)


def test_full_period_time_series_ic_depends_on_positions_not_timestamps():
    factor, prices = business_days()
    weekday = evaluate(factor, prices, horizons=[3], time_series=TS)
    relabeled = pd.date_range("2024-01-01", periods=len(prices), freq="D")
    daily = evaluate(
        factor.set_axis(relabeled),
        prices.set_axis(relabeled),
        horizons=[3],
        time_series=TS,
    )
    a, b = weekday.time_series.assets, daily.time_series.assets
    assert a.ic.tolist() == pytest.approx(b.ic.tolist())
    assert a.n_pairs.tolist() == b.n_pairs.tolist()
    assert a.boundary_excluded.tolist() == [3] * len(a)


def test_the_last_labels_are_excluded_by_position_in_the_time_series_view():
    factor, prices = business_days(n_bars=120)
    result = evaluate(factor, prices, horizons=[4], time_series=TS)
    asset = result.time_series.assets.query("asset == 'A0' and method == 'spearman'").iloc[0]
    assert asset.boundary_excluded == 4
    assert asset.n_expected == 120 - 4
    assert asset.last_pair == prices.index[-5]


def test_months_are_calendar_months_of_the_timestamps():
    factor, prices = business_days()
    result = evaluate(
        factor,
        prices,
        horizons=[1],
        start="2024-01-01",
        end="2024-08-01",
        # Raw returns: the prices start with the window, so a volatility warm-up would leave
        # January short of pairs.
        time_series=TS | {"min_months": 3, "min_pairs": 15, "target": "return"},
    )
    monthly = result.time_series.monthly.query("asset == 'A0' and method == 'spearman'")
    assert monthly.window_start.dt.strftime("%Y-%m").tolist() == [
        f"2024-{m:02d}" for m in range(1, 8)
    ]
    assert set(monthly.status) == {"valid"}
    # Each month holds its business days, and the last bar's label ends in the next month.
    days = prices.loc[:"2024-07-31"].groupby([prices.loc[:"2024-07-31"].index.month]).size()
    assert monthly.n_expected.tolist() == (days - 1).tolist()
    assert result.time_series.assets.query("method == 'spearman'").valid_months.eq(7).all()


def test_sparse_factor_dates_are_scored_where_they_exist():
    factor, prices = regular_panel(n_assets=10, n_bars=300, freq="B", start="2024-01-01", seed=2)
    stamps = factor.index.to_series()
    last_of_month = stamps.groupby([stamps.dt.year, stamps.dt.month]).transform("max") == stamps
    sparse = factor.copy()
    sparse.loc[~last_of_month.to_numpy()] = np.nan
    result = evaluate(sparse, prices, horizons=[21], time_series={"bootstrap_samples": 0})
    scored = result.periods.query("n_signal > 0")
    assert 0 < len(scored) < 20
    assert result.summary.query("method == 'spearman'").n_periods.iloc[0] <= len(scored)
    assert (result.periods.query("n_signal == 0").status == "insufficient_assets").all()


def test_irregular_grids_work_and_have_no_nominal_bar():
    rng = np.random.default_rng(0)
    index = pd.DatetimeIndex(
        sorted(
            pd.Timestamp("2024-01-01") + pd.to_timedelta(rng.choice(400, 150, replace=False), "D")
        )
    )
    factor, prices = regular_panel(n_assets=6, n_bars=150, seed=1)
    result = evaluate(factor.set_axis(index), prices.set_axis(index), horizons=[2], time_series=TS)
    assert result.bar is None
    assert result.summary.n_periods.max() > 0
