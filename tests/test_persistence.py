import json

import pandas as pd
import pytest

from alphatonic import Evaluation, EvaluationConfig, evaluate
from conftest import regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 100, "rolling_window": "5D"}


@pytest.fixture
def result():
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 20, seed=21)
    return evaluate(factor, prices, horizons=[1, 3], time_series=FAST)


def test_round_trip_preserves_every_table(result, tmp_path):
    assert result.save(tmp_path / "run") == tmp_path / "run"
    loaded = Evaluation.load(tmp_path / "run")
    assert loaded.config == result.config
    assert (loaded.start, loaded.end, loaded.bar) == (result.start, result.end, result.bar)
    for name in ("periods", "summary", "quantiles"):
        pd.testing.assert_frame_equal(
            getattr(loaded, name), getattr(result, name), check_dtype=False, rtol=1e-12
        )
    for name, table in result.time_series.tables().items():
        pd.testing.assert_frame_equal(
            loaded.time_series.tables()[name], table, check_dtype=False, rtol=1e-12
        )
    assert loaded.forward_returns == {}
    assert loaded.metrics() == pytest.approx(result.metrics())


def test_files_and_metadata(result, tmp_path):
    result.save(tmp_path)
    names = {path.name for path in tmp_path.iterdir()}
    assert names == {
        "evaluation.json",
        "ic_by_timestamp.csv",
        "ic_summary.csv",
        "ic_monthly.csv",
        "cs_quantiles.csv",
        "ts_assets.csv",
        "ts_monthly.csv",
        "ts_rolling.csv",
        "ts_summary.csv",
        "ts_quantiles.csv",
    }
    metadata = json.loads((tmp_path / "evaluation.json").read_text())
    assert metadata["format_version"] == 1
    assert metadata["bar_seconds"] == 3600.0
    assert metadata["config"]["horizons"] == [1, 3]
    assert metadata["start"].startswith("2026-01-01")


def test_cross_sectional_evaluations_have_no_time_series_files(tmp_path):
    factor, prices = regular_panel(n_bars=60, freq="D")
    cs = evaluate(factor, prices, horizons=[1], mode="cross_sectional")
    cs.save(tmp_path)
    assert not list(tmp_path.glob("ts_*"))
    assert Evaluation.load(tmp_path).time_series is None


def test_irregular_grids_are_saved_without_a_bar(tmp_path):
    factor, prices = regular_panel(n_bars=60, freq="B")
    saved = evaluate(factor, prices, horizons=[1], mode="cross_sectional")
    saved.save(tmp_path)
    assert json.loads((tmp_path / "evaluation.json").read_text())["bar_seconds"] is None
    assert Evaluation.load(tmp_path).bar is None


def test_tables_without_metadata_need_a_configuration(result, tmp_path):
    result.save(tmp_path)
    (tmp_path / "evaluation.json").unlink()
    with pytest.raises(ValueError, match="pass the EvaluationConfig"):
        Evaluation.load(tmp_path)
    loaded = Evaluation.load(tmp_path, EvaluationConfig(horizons=[1, 3]))
    assert loaded.bar == pd.Timedelta(hours=1)
    assert loaded.start == result.start
    assert loaded.end == result.end


def test_a_given_configuration_overrides_the_stored_one(result, tmp_path):
    result.save(tmp_path)
    other = EvaluationConfig(horizons=[1, 3], mode="cross_sectional")
    assert Evaluation.load(tmp_path, other).config.mode == "cross_sectional"


def test_unknown_format_versions_are_rejected(result, tmp_path):
    result.save(tmp_path)
    path = tmp_path / "evaluation.json"
    path.write_text(path.read_text().replace('"format_version": 1', '"format_version": 99'))
    with pytest.raises(ValueError, match="format 99"):
        Evaluation.load(tmp_path)


def test_missing_tables_and_empty_metadata_are_reported(tmp_path):
    with pytest.raises(ValueError, match="pass the EvaluationConfig"):
        Evaluation.load(tmp_path)
    with pytest.raises(FileNotFoundError):
        Evaluation.load(tmp_path, EvaluationConfig())
    (tmp_path / "evaluation.json").write_text("{}")
    with pytest.raises(ValueError, match="format None"):
        Evaluation.load(tmp_path)


def test_saving_twice_replaces_files(result, tmp_path):
    result.save(tmp_path)
    result.save(tmp_path)
    assert Evaluation.load(tmp_path).summary.shape == result.summary.shape
