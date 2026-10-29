import numpy as np
import pandas as pd
import pytest

from alphatonic import Evaluation, EvaluationConfig, PersistenceOptions, evaluate
from alphatonic.signal_persistence import evaluate_persistence


def diagnostics(values, *, lags=(1,), prices=None, quantiles=2, min_pairs=1):
    scores = pd.DataFrame(values, index=pd.date_range("2026-01-01", periods=len(values), tz="UTC"))
    if prices is None:
        prices = scores * 0 + 100
    config = EvaluationConfig(
        min_assets=3, quantiles=quantiles, persistence={"lags": lags, "min_pairs": min_pairs}
    )
    return evaluate_persistence(scores, prices, config)


def test_constant_and_reversed_order_have_known_persistence_and_bucket_changes():
    result = diagnostics([[1, 2, 3, 4], [1, 2, 3, 4], [4, 3, 2, 1]])
    assert result.periods.rank_autocorrelation.iloc[1:].tolist() == pytest.approx([1, -1])
    assert result.periods.status.iloc[0] == "boundary_excluded"
    assert result.quantiles.query("quantile == 2").entry_fraction.iloc[1:].tolist() == [0, 1]
    assert result.quantiles.query("quantile == 2").n_entries.iloc[1:].tolist() == [0, 2]


def test_signal_change_sign_flips_zero_and_constants():
    result = diagnostics([[1, 3, 0], [-1, 3, 0], [0, 3, 0], [1, 3, 0]])
    rows = result.assets.set_index("asset")
    assert rows.loc[0, "normalized_change"] == 2
    assert rows.loc[0, "sign_change_fraction"] == pytest.approx(1 / 3)
    assert rows.loc[0, "zero_transition_fraction"] == pytest.approx(2 / 3)
    assert rows.loc[1, "normalized_change"] == 0
    assert rows.loc[1, "change_status"] == "valid"
    assert np.isnan(rows.loc[2, "normalized_change"])
    assert rows.loc[2, "change_status"] == "zero_signal"
    assert rows.loc[2, "sign_change_fraction"] == 0


def test_normalization_is_scale_invariant_and_handles_extreme_finite_scores():
    values = np.array([[1, -2, 3], [-3, 2, 1], [2, -1, -3]], dtype=float)
    expected = diagnostics(values)
    for scale in (1e-250, 1e300, 10):
        actual = diagnostics(
            values * scale,
            prices=pd.DataFrame(
                100.0, index=pd.date_range("2026-01-01", periods=3, tz="UTC"), columns=range(3)
            ),
        )
        np.testing.assert_allclose(
            actual.assets.normalized_change, expected.assets.normalized_change
        )


def test_gaps_keep_original_lag_and_long_lags_are_unavailable():
    result = diagnostics([[1], [np.nan], [-1], [1]], lags=(1, 2, 20))
    rows = result.assets.set_index("lag")
    assert rows.loc[1, "n_pairs"] == 1
    assert rows.loc[1, "n_expected"] == 3
    assert rows.loc[1, "pair_coverage"] == pytest.approx(1 / 3)
    assert rows.loc[2, "n_pairs"] == 1  # t=0 to t=2, despite missing interior score
    assert rows.loc[2, "normalized_change"] == 2
    assert rows.loc[20, "n_expected"] == 0
    assert rows.loc[20, "status"] == "insufficient_pairs"
    assert result.periods.query("lag == 20").status.eq("boundary_excluded").all()


def test_universe_changes_are_counted_and_ties_leave_empty_buckets():
    result = diagnostics([[1, 2, 3, 4, np.nan], [1, 2, 3, np.nan, 5]])
    period = result.periods.iloc[1]
    assert (period.n_current, period.n_previous, period.n_common) == (4, 4, 3)
    assert (period.n_entries, period.n_exits, period.pair_coverage) == (1, 1, 0.75)
    bucket = result.quantiles.query("quantile == 2").iloc[1]
    assert bucket.entry_fraction == 0.5
    assert (bucket.n_universe_entries, bucket.n_universe_exits) == (1, 1)
    tied = diagnostics([[1, 1, 1, 2], [1, 1, 1, 2]], quantiles=5)
    assert tied.quantiles.query("quantile == 1").iloc[1].status == "empty_quantile"
    assert tied.quantiles.query("quantile == 3").iloc[1].n_current == 3
    constant = diagnostics([[1, 1, 1], [1, 1, 1]])
    assert constant.periods.iloc[1].status == "constant_signal"
    assert constant.quantiles.entry_fraction.isna().all()


def test_matches_independent_set_and_scalar_reference():
    rng = np.random.default_rng(13)
    x = rng.integers(-2, 4, size=(35, 8)).astype(float)
    x[rng.random(x.shape) < 0.2] = np.nan
    result = diagnostics(x, lags=(1, 4), quantiles=3)
    scores = pd.DataFrame(x)
    ranks = scores.rank(axis=1)
    buckets = np.ceil(ranks.div(scores.count(axis=1), axis=0) * 3)
    for row in result.periods.itertuples():
        t = result.periods.timestamp.drop_duplicates().tolist().index(row.timestamp)
        if t < row.lag:
            continue
        common = scores.iloc[t].notna() & scores.iloc[t - row.lag].notna()
        if (
            common.sum() >= 3
            and ranks.iloc[t][common].nunique() > 1
            and ranks.iloc[t - row.lag][common].nunique() > 1
        ):
            expected = np.corrcoef(ranks.iloc[t][common], ranks.iloc[t - row.lag][common])[0, 1]
            assert row.rank_autocorrelation == pytest.approx(expected, abs=1e-12)
    for row in result.quantiles.query("status == 'valid'").itertuples():
        t = result.periods.timestamp.drop_duplicates().tolist().index(row.timestamp)
        current = set(scores.columns[buckets.iloc[t] == row.quantile])
        old = set(scores.columns[buckets.iloc[t - row.lag] == row.quantile])
        assert row.entry_fraction == len(current - old) / len(current)
    for row in result.assets.itertuples():
        pairs = [
            (x[t, row.asset], x[t - row.lag, row.asset])
            for t in range(row.lag, len(x))
            if np.isfinite([x[t, row.asset], x[t - row.lag, row.asset]]).all()
        ]
        expected = sum(abs(a - b) for a, b in pairs) / sum((abs(a) + abs(b)) / 2 for a, b in pairs)
        assert row.normalized_change == pytest.approx(expected)


def test_evaluation_ignores_return_horizons_delay_and_future_prices():
    index = pd.date_range("2026-01-01", periods=25, tz="UTC")
    rng = np.random.default_rng(17)
    factor = pd.DataFrame(rng.normal(size=(25, 5)), index=index)
    prices = pd.DataFrame(rng.uniform(90, 110, size=(25, 5)), index=index)
    options = {"time_series": {"bootstrap_samples": 0}, "persistence": {"lags": [1, 3]}}
    original = evaluate(factor, prices, horizons=[1], **options)
    other = evaluate(factor, prices, horizons=[7], delay=2, vol_span=5, **options)
    for name, table in original.persistence.tables().items():
        pd.testing.assert_frame_equal(table, other.persistence.tables()[name])
    prices.iloc[18:] = np.nan
    changed = evaluate(factor, prices, horizons=[7], **options)
    for name in ("periods", "quantiles"):
        before = getattr(original.persistence, name)
        after = getattr(changed.persistence, name)
        pd.testing.assert_frame_equal(
            before.loc[before.timestamp < index[18]], after.loc[after.timestamp < index[18]]
        )
    assert original.persistence.periods.iloc[-1].status == "valid"


def test_minimum_pairs_and_summary_weighting():
    result = diagnostics([[1, 1], [1, np.nan], [1, -1], [1, 1]], min_pairs=2)
    assert result.assets.loc[1, "status"] == "insufficient_pairs"
    summary = result.summary.query("metric == 'normalized_change'").iloc[0]
    assert (summary["mean"], summary.n_valid, summary.n_total) == (0, 1, 2)


@pytest.mark.parametrize("lags", [[], [0], [-1], [True], [1, 1]])
def test_invalid_lags(lags):
    with pytest.raises(ValueError):
        PersistenceOptions(lags=lags)


def test_saved_tables_report_and_legacy_compatibility(tmp_path):
    index = pd.date_range("2026-01-01", periods=8, tz="UTC")
    factor = pd.DataFrame({"<script>bad()</script>": [1.0, -1.0] * 4}, index=index)
    prices = pd.DataFrame(100.0, index=index, columns=factor.columns)
    result = evaluate(factor, prices, time_series={"bootstrap_samples": 0})
    result.save(tmp_path)
    loaded = Evaluation.load(tmp_path)
    for name, table in result.persistence.tables().items():
        pd.testing.assert_frame_equal(loaded.persistence.tables()[name], table, check_dtype=False)
    assert loaded.metrics() == result.metrics()
    html = loaded.render_tearsheet()
    assert 'id="signal-persistence"' in html
    assert "<script>bad()</script>" not in html
    assert "&lt;script&gt;bad()&lt;/script&gt;" in html
    assert "Normalised change" in html
    result.persistence = None
    result.save(tmp_path)
    assert not list(tmp_path.glob("persistence_*.csv"))
    legacy = Evaluation.load(tmp_path)
    assert legacy.persistence is None
    assert "This saved evaluation has no signal persistence tables." in legacy.render_tearsheet()


@pytest.mark.parametrize("version", [1, 2])
def test_real_legacy_formats_have_no_persistence(tmp_path, version):
    import json

    index = pd.date_range("2026-01-01", periods=6, tz="UTC")
    scores = pd.DataFrame({"a": np.arange(6.0)}, index=index)
    result = evaluate(scores, scores + 100, time_series={"bootstrap_samples": 0})
    result.save(tmp_path)
    for path in tmp_path.glob("persistence_*.csv"):
        path.unlink()
    metadata_path = tmp_path / "evaluation.json"
    metadata = json.loads(metadata_path.read_text())
    metadata["format_version"] = version
    del metadata["config"]["persistence"]
    metadata_path.write_text(json.dumps(metadata))
    loaded = Evaluation.load(tmp_path)
    assert loaded.persistence is None
    assert not any(key.startswith("persistence.") for key in loaded.metrics())
    assert loaded.config.persistence.lags == (1, 5, 10)
    assert "no signal persistence tables" in loaded.render_tearsheet()
