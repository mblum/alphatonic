import numpy as np
import pandas as pd
import pytest

from alphatonic import Study, evaluate
from tests.support.assertions import same_frame


@pytest.mark.parametrize("sign", [1, -1, 0])
def test_known_cross_sectional_association(sign, config):
    index = pd.date_range("2024-01-01", periods=6, tz="UTC")
    score = np.array([-1.0, 0, 1])
    returns = np.array([0.01, -0.02, 0.01]) if sign == 0 else sign * 0.01 * score
    p = pd.DataFrame(100 * (1 + returns) ** np.arange(6)[:, None], index=index, columns=list("abc"))
    x = pd.DataFrame(np.tile(score, (6, 1)), index=index, columns=list("abc"))
    result = evaluate(x, p, config.model_copy(update={"horizons": (1,)}))
    assert result.periods.n_pairs.tolist() == [3] * 5 + [0]
    np.testing.assert_allclose(result.ic("pearson").iloc[:5, 0], sign, atol=2e-12)


def test_bounded_evaluation_ignores_future_prices(panel, config):
    x, p = panel
    config = config.model_copy(update={"end": p.index[50]})
    a = evaluate(x, p, config)
    changed = p.copy()
    changed.iloc[50:] *= 3
    b = evaluate(x, changed, config)
    for name in ["periods", "summary", "quantiles"]:
        same_frame(getattr(a, name), getattr(b, name))
    for name, table in a.time_series.tables().items():
        same_frame(table, b.time_series.tables()[name])
    for h, labels in a.forward_returns.items():
        assert labels.iloc[-h:].isna().all().all()


def test_constant_nonzero_position_has_cosine_but_no_centred_ic(panel, config):
    x, p = panel
    result = evaluate(x * 0 + 0.1, p, config)
    assert result.periods.spearman.isna().all()
    rows = result.time_series.assets
    assert rows.loc[rows.method == "pearson", "status"].eq("constant_signal").all()
    assert rows.loc[rows.method == "cosine", "ic"].notna().all()


def test_holdout_labels_end_before_boundary(panel, config, tmp_path):
    s = Study(tmp_path, holdout_start=panel[1].index[50])
    trial = s.evaluate(*panel, config, signal="bounded")
    loaded = s.evaluation(trial.id)
    assert loaded.periods.timestamp.max() < s.holdout_start
    for h in config.horizons:
        rows = loaded.periods.loc[loaded.periods.horizon == h]
        assert rows.tail(h).n_pairs.eq(0).all()


@pytest.mark.property
def test_generated_panels_column_permutations_and_missing_pairs(config):
    # Fixed independent streams make panel-level metamorphic failures reproducible.
    from tests.support.oracles import correlation
    from tests.support.panels import market

    for seed in range(8):
        x, p = market(24, 4, seed)
        x.iloc[seed::5, seed % 4] = np.nan
        p.iloc[(seed + 2) :: 9, (seed + 1) % 4] = np.nan
        a = evaluate(x, p, config)
        order = list(reversed(x.columns))
        b = evaluate(x[order], p[order], config)
        same_frame(a.periods, b.periods)
        for row in a.periods.itertuples():
            timestamp = x.index.get_loc(row.timestamp)
            horizon = row.horizon
            pairs = []
            for asset in x:
                if timestamp + horizon >= len(p):
                    continue
                path = p[asset].iloc[timestamp : timestamp + horizon + 1].to_numpy()
                score = x[asset].iloc[timestamp]
                if np.isfinite(score) and np.isfinite(path).all():
                    pairs.append((score, path[-1] / path[0] - 1))
            assert row.n_pairs == len(pairs)
            if row.status == "valid":
                scores, labels = zip(*pairs, strict=True)
                assert row.spearman == pytest.approx(
                    correlation(scores, labels, "spearman"), abs=2e-12
                )


def test_known_time_series_positive_negative_and_zero_association(config):
    index = pd.date_range("2024-01-01", periods=7, tz="UTC")
    score = np.array([-1, 0, 1, -1, 0, 1, 0.0])
    raw = np.array([0.01, -0.02, 0.01, 0.01, -0.02, 0.01])
    prices = np.column_stack(
        [
            np.r_[100, 100 * np.cumprod(1 + 0.01 * score[:-1])],
            np.r_[100, 100 * np.cumprod(1 - 0.01 * score[:-1])],
            np.r_[100, 100 * np.cumprod(1 + raw)],
        ]
    )
    p = pd.DataFrame(prices, index=index, columns=list("abc"))
    x = pd.DataFrame(np.tile(score[:, None], (1, 3)), index=index, columns=p.columns)
    result = evaluate(x, p, config.model_copy(update={"horizons": (1,)}))
    pearson = result.time_series.assets.loc[
        result.time_series.assets.method == "pearson"
    ].set_index("asset")
    np.testing.assert_allclose(pearson.ic, [1, -1, 0], atol=2e-12)
    assert pearson.n_pairs.tolist() == [6, 6, 6]
