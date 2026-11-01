import numpy as np
import pytest

from alphatonic.signal_persistence import evaluate_persistence
from tests.support.oracles import correlation, ranks


def test_endpoint_ranks_membership_and_asset_changes(panel, config):
    x, p = panel
    x = x.iloc[:8].copy()
    p = p.iloc[:8].copy()
    x.iloc[1, 0] = np.nan
    p.iloc[3, 1] = np.nan
    x.iloc[:, 4] = 0
    result = evaluate_persistence(x, p, config)
    scores = x.where(p.notna())
    for row in result.periods.itertuples():
        t = x.index.get_loc(row.timestamp)
        lag = row.lag
        if t < lag:
            assert row.status == "boundary_excluded"
            continue
        a = scores.iloc[t].to_numpy()
        b = scores.iloc[t - lag].to_numpy()
        good = np.isfinite(a) & np.isfinite(b)
        ra = np.full(5, np.nan)
        rb = ra.copy()
        ra[np.isfinite(a)] = ranks(a[np.isfinite(a)])
        rb[np.isfinite(b)] = ranks(b[np.isfinite(b)])
        expected = correlation(ra, rb)
        assert row.n_common == good.sum()
        if good.sum() >= config.min_assets:
            assert row.rank_autocorrelation == pytest.approx(expected)
    for row in result.quantiles.itertuples():
        assert row.n_current - row.n_previous == row.n_entries - row.n_exits
        if row.status == "valid":
            assert row.entry_fraction == pytest.approx(row.n_entries / row.n_current)
    for row in result.assets.itertuples():
        a = scores[row.asset].to_numpy()[row.lag :]
        b = scores[row.asset].to_numpy()[: -row.lag]
        good = np.isfinite(a) & np.isfinite(b)
        a = a[good]
        b = b[good]
        assert row.n_pairs == len(a)
        if len(a) >= config.persistence.min_pairs:
            assert row.sign_change_fraction == pytest.approx(np.mean(a * b < 0))
            assert row.zero_transition_fraction == pytest.approx(np.mean((a == 0) != (b == 0)))
            denom = np.sum((abs(a) + abs(b)) / 2)
            if denom:
                assert row.normalized_change == pytest.approx(np.sum(abs(a - b)) / denom)
            else:
                assert row.change_status == "zero_signal" and np.isnan(row.normalized_change)
    for row in result.summary.itertuples():
        source = {"cs": result.periods, "ts": result.assets, "quantile": result.quantiles}[
            row.scope
        ]
        values = source.loc[source.lag == row.lag]
        if row.quantile:
            values = values.loc[values["quantile"] == row.quantile]
        assert row.n_valid == values[row.metric].notna().sum()


def test_persistence_independent_of_horizons_and_positive_scale(panel, config):
    a = evaluate_persistence(*panel, config)
    b = evaluate_persistence(
        panel[0] * 1e100, panel[1], config.model_copy(update={"horizons": (30,)})
    )
    from tests.support.assertions import same_frame

    for name, table in a.tables().items():
        same_frame(table, b.tables()[name])
