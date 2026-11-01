import numpy as np
import pytest

from alphatonic.cross_section import cross_sectional_ic
from tests.support.assertions import same_numbers
from tests.support.oracles import correlation


def test_every_period_counts_correlations_and_summary(panel, config):
    x, p = panel
    y = x.iloc[::-1].set_axis(x.index).copy()
    y.iloc[0, :] = np.nan
    x.iloc[1, :] = 0.1
    y.iloc[2, :] = 0.2
    x.iloc[3, 0] = np.nan
    periods, summary, buckets = cross_sectional_ic(x, {h: y for h in config.horizons}, p, config)
    for row in periods.itertuples():
        a = x.loc[row.timestamp].to_numpy()
        b = y.loc[row.timestamp].to_numpy()
        pairs = np.isfinite(a) & np.isfinite(b)
        assert row.n_pairs == pairs.sum()
        assert row.n_signal == np.isfinite(a).sum()
        assert row.n_available == 5
        assert row.pair_coverage == pytest.approx(pairs.mean())
        expected = (
            "insufficient_assets"
            if pairs.sum() < 3
            else "constant_signal"
            if len(set(a[pairs])) == 1
            else "constant_returns"
            if len(set(b[pairs])) == 1
            else "valid"
        )
        assert row.status == expected
        for method in ["pearson", "spearman"]:
            same_numbers(
                [getattr(row, method)],
                [correlation(a, b, method) if expected == "valid" else np.nan],
            )
    for row in summary.itertuples():
        values = periods.loc[periods.horizon == row.horizon, row.method].dropna()
        assert row.mean == pytest.approx(values.mean())
        assert row.std == pytest.approx(values.std())
        assert row.n_periods == len(values)
        assert row.hac_lags >= row.horizon - 1
    assert set(buckets.timestamp).isdisjoint(set(x.index[:3]))
    assert (buckets.groupby(["timestamp", "horizon"]).n_pairs.sum() >= 3).all()
