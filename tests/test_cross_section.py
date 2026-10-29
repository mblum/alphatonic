import numpy as np
import pandas as pd
import pytest

from alphatonic import evaluate
from conftest import perfect_market, regular_panel


def cs(factor, prices, **options):
    options = {
        "horizons": [1, 4],
        "min_assets": 3,
        "time_series": {"bootstrap_samples": 0},
    } | options
    return evaluate(factor, prices, **options)


def test_perfect_and_reversed_ic():
    factor, prices = perfect_market()
    result = cs(factor, prices)
    assert result.periods["spearman"].dropna().to_numpy() == pytest.approx(1)
    assert result.periods["pearson"].dropna().to_numpy() == pytest.approx(1, abs=0.02)
    reverse = cs(-factor, prices)
    assert reverse.periods["spearman"].dropna().to_numpy() == pytest.approx(-1)
    one_bar = result.periods.query("horizon == 1")
    # The last bar has no label, so no pairs.
    assert one_bar.iloc[-1]["status"] == "insufficient_assets"
    assert one_bar.iloc[-1]["n_pairs"] == 0
    assert result.summary.query("method == 'spearman'")["mean"].tolist() == pytest.approx([1, 1])


def test_ties_match_spearman_definition():
    factor, prices = perfect_market()
    factor.iloc[:, :] = [1, 1, 2, 3, 4]
    result = cs(factor, prices)
    expected = pd.Series([1, 1, 2, 3, 4]).rank().corr(pd.Series([1, 2, 3, 4, 5]))
    assert result.periods.iloc[0]["spearman"] == pytest.approx(expected)


def test_constant_scores_and_constant_returns_are_undefined_not_zero():
    factor, prices = perfect_market()
    result = cs(factor * 0 + 1, prices)
    assert result.periods["spearman"].isna().all()
    assert set(result.periods.status) <= {"constant_signal", "insufficient_assets"}
    assert result.periods.iloc[0]["status"] == "constant_signal"
    flat = prices * 0 + 100
    result = cs(factor, flat)
    assert result.periods.iloc[0]["status"] == "constant_returns"
    assert result.periods["pearson"].isna().all()


def test_cross_sections_below_the_minimum_are_skipped():
    factor, prices = perfect_market()
    factor.iloc[10, :3] = np.nan
    result = cs(factor, prices, horizons=[1], min_assets=4)
    row = result.periods.iloc[10]
    assert row["n_pairs"] == 2 and row["status"] == "insufficient_assets"
    assert np.isnan(row["spearman"])
    assert (
        result.summary.iloc[0]["skipped_periods"] == 2
    )  # the sparse row and the unlabeled last row


def test_counts_and_pair_coverage():
    factor, prices = perfect_market()
    factor.iloc[5, 0] = np.nan
    prices.iloc[7, 1] = np.nan
    row = cs(factor, prices, horizons=[1]).periods
    assert row.loc[5, ["n_available", "n_signal", "n_pairs"]].tolist() == [5, 4, 4]
    assert row.loc[5, "pair_coverage"] == pytest.approx(4 / 5)
    # A missing price at t+1 removes the label of t and t+1's own label.
    assert row.loc[6, "n_pairs"] == 4 and row.loc[7, "n_available"] == 4
    assert row.loc[7, "n_pairs"] == 4


def test_pair_coverage_is_undefined_without_available_assets():
    factor, prices = perfect_market()
    prices.iloc[3, :] = np.nan
    row = cs(factor, prices, horizons=[1]).periods.iloc[3]
    assert row["n_available"] == 0 and np.isnan(row["pair_coverage"])


def test_periods_follow_the_configured_horizon_order_and_summary_sorts_them():
    factor, prices = perfect_market()
    result = cs(factor, prices, horizons=[4, 1])
    assert result.periods.horizon.iloc[0] == 4 and result.periods.horizon.iloc[-1] == 1
    assert result.summary.horizon.tolist() == [1, 1, 4, 4]


def test_quantile_response_orders_buckets_by_score():
    factor, prices = perfect_market(n_assets=10, n_bars=30)
    result = cs(factor, prices, horizons=[1], quantiles=5)
    mean = result.quantiles.groupby("quantile").mean_return.mean()
    assert mean.is_monotonic_increasing and len(mean) == 5
    assert set(result.quantiles.n_pairs) == {2}
    assert result.quantiles.timestamp.nunique() == 29


@pytest.mark.parametrize("quantiles", [2, 3, 10])
def test_quantile_count_is_configurable(quantiles):
    factor, prices = perfect_market(n_assets=10, n_bars=30)
    result = cs(factor, prices, horizons=[1], quantiles=quantiles)
    assert sorted(result.quantiles["quantile"].unique()) == list(range(1, quantiles + 1))


def test_hac_lags_cover_overlapping_labels_and_can_be_overridden():
    factor, prices = regular_panel(n_assets=8, n_bars=400, freq="D", seed=3)
    default = cs(factor, prices, horizons=[1, 10])
    lags = default.summary.query("method == 'spearman'").set_index("horizon").hac_lags
    assert lags[10] >= 9
    assert lags[1] == int(np.floor(4 * (399 / 100) ** (2 / 9)))
    longer = cs(factor, prices, horizons=[1, 10], hac_lags=30)
    assert (longer.summary.hac_lags == 30).all()
    shorter = cs(factor, prices, horizons=[10], hac_lags=1)
    assert (shorter.summary.hac_lags == 9).all()  # never fewer than horizon - 1


def test_summary_keeps_missing_periods_in_time_for_inference():
    factor, prices = regular_panel(n_assets=8, n_bars=200, freq="D", seed=4)
    full = cs(factor, prices, horizons=[1])
    factor.iloc[50:80] = np.nan
    gapped = cs(factor, prices, horizons=[1])
    row = gapped.summary.query("method == 'spearman'").iloc[0]
    assert row.total_periods == 200 and row.skipped_periods >= 30
    assert row.n_periods < full.summary.iloc[0].n_periods


def test_future_prices_beyond_the_window_do_not_change_results():
    factor, prices = regular_panel(n_assets=8, n_bars=100, freq="D", seed=5)
    end = prices.index[80]
    base = cs(factor, prices, horizons=[5], end=end)
    prices.iloc[80:] *= 7.0
    again = cs(factor, prices, horizons=[5], end=end)
    pd.testing.assert_frame_equal(base.periods, again.periods)
    # Labels cannot reach into the data after the window.
    assert base.periods.query("timestamp >= @prices.index[75]").spearman.isna().all()


def test_changing_a_later_price_cannot_change_earlier_labels():
    factor, prices = regular_panel(n_assets=8, n_bars=60, freq="D", seed=6)
    base = cs(factor, prices, horizons=[3])
    changed = prices.copy()
    changed.iloc[-1] *= 2
    after = cs(factor, changed, horizons=[3])
    cut = prices.index[-4]  # noqa: F841 - referenced by the queries below
    pd.testing.assert_frame_equal(
        base.periods.query("timestamp < @cut"), after.periods.query("timestamp < @cut")
    )


def test_label_delay_moves_the_label_start():
    factor, prices = perfect_market()
    result = cs(factor, prices, horizons=[1], delay=3)
    nolabel = result.periods.query("n_pairs == 0")
    assert len(nolabel) == 4  # the last delay + horizon bars
