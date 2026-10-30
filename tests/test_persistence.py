import gzip
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
    assert loaded.forward_returns == {} and loaded.volatility is None
    assert loaded.metrics() == pytest.approx(result.metrics())


def test_files_and_metadata(result, tmp_path):
    result.save(tmp_path)
    names = {path.name for path in tmp_path.iterdir()}
    assert names == {
        "evaluation.json",
        "ic_by_timestamp.csv.gz",
        "ic_summary.csv.gz",
        "ic_monthly.csv.gz",
        "cs_quantiles.csv.gz",
        "ts_assets.csv.gz",
        "ts_monthly.csv.gz",
        "ts_rolling.csv.gz",
        "ts_summary.csv.gz",
        "ts_quantiles.csv.gz",
        "persistence_periods.csv.gz",
        "persistence_quantiles.csv.gz",
        "persistence_assets.csv.gz",
        "persistence_summary.csv.gz",
    }
    metadata = json.loads((tmp_path / "evaluation.json").read_text())
    assert metadata["format_version"] == 4
    assert metadata["bar_seconds"] == 3600.0
    assert metadata["config"]["horizons"] == [1, 3]
    assert "mode" not in metadata["config"]
    assert metadata["start"].startswith("2026-01-01")


@pytest.mark.parametrize("mode", ["both", "cross_sectional", "time_series"])
def test_legacy_modes_load_without_recomputing_tables(result, tmp_path, mode):
    result.save(tmp_path)
    path = tmp_path / "evaluation.json"
    metadata = json.loads(path.read_text())
    metadata["config"]["mode"] = mode
    path.write_text(json.dumps(metadata))
    if mode == "cross_sectional":
        for table in tmp_path.glob("ts_*.csv.gz"):
            table.unlink()
    elif mode == "time_series":
        # Older time-series-only runs saved disabled cross-sectional rows.
        periods = result.periods.copy()
        periods[["spearman", "pearson"]] = float("nan")
        periods["status"] = "disabled"
        periods.to_csv(tmp_path / "ic_by_timestamp.csv.gz", index=False)
        summary = result.summary.copy()
        summary["n_periods"] = 0
        summary[["mean", "ci95_lower", "ci95_upper"]] = float("nan")
        summary.to_csv(tmp_path / "ic_summary.csv.gz", index=False)
    loaded = Evaluation.load(tmp_path)
    assert "mode" not in loaded.config.model_dump()
    assert (loaded.time_series is None) == (mode == "cross_sectional")
    if mode == "time_series":
        assert loaded.periods.status.eq("disabled").all()
        assert loaded.periods.spearman.isna().all()
    else:
        pd.testing.assert_frame_equal(loaded.periods, result.periods, check_dtype=False)
    assert "Evaluation mode" not in loaded.render_tearsheet()
    loaded.save(tmp_path)
    assert "mode" not in json.loads(path.read_text())["config"]


def test_irregular_grids_are_saved_without_a_bar(tmp_path):
    factor, prices = regular_panel(n_bars=60, freq="B")
    saved = evaluate(factor, prices, horizons=[1], time_series={"bootstrap_samples": 0})
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
    other = EvaluationConfig(horizons=[1, 3], min_assets=3)
    assert Evaluation.load(tmp_path, other).config == other


def test_unknown_format_versions_are_rejected(result, tmp_path):
    result.save(tmp_path)
    path = tmp_path / "evaluation.json"
    path.write_text(path.read_text().replace('"format_version": 4', '"format_version": 99'))
    with pytest.raises(ValueError, match="format 99"):
        Evaluation.load(tmp_path)


def test_format_1_is_read_as_raw_return_targets(result, tmp_path):
    # Format 1 predates the target options; its time-series IC was computed on returns.
    result.save(tmp_path)
    path = tmp_path / "evaluation.json"
    metadata = json.loads(path.read_text())
    metadata["format_version"] = 1
    metadata["config"]["mode"] = "both"
    for key in ("target", "vol_span", "vol_min_bars"):
        del metadata["config"][key]
    del metadata["config"]["time_series"]["target"]
    path.write_text(json.dumps(metadata))
    loaded = Evaluation.load(tmp_path)
    assert loaded.config.target == "return"
    assert loaded.config.time_series.target == "return"
    assert loaded.config.horizons == result.config.horizons


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


def test_tables_are_gzip_compressed_csv_that_pandas_reads_as_they_are(result, tmp_path):
    result.save(tmp_path)

    tables = sorted(tmp_path.glob("*.csv.gz"))
    assert len(tables) == 13
    for path in tables:
        assert path.read_bytes()[:2] == b"\x1f\x8b"
    rolling = pd.read_csv(tmp_path / "ts_rolling.csv.gz")
    assert len(rolling) == len(result.time_series.rolling)
    assert gzip.decompress((tmp_path / "ic_summary.csv.gz").read_bytes()).startswith(b"horizon,")


def test_saving_the_same_evaluation_twice_writes_the_same_bytes(result, tmp_path):
    result.save(tmp_path / "first")
    result.save(tmp_path / "second")

    for path in (tmp_path / "first").glob("*.csv.gz"):
        assert path.read_bytes() == (tmp_path / "second" / path.name).read_bytes()
        # The gzip header's modification time is zero, so it does not depend on when it was saved.
        assert path.read_bytes()[4:8] == bytes(4)


def _as_format_3(directory):
    """Rewrite a saved evaluation as format 3 wrote it: plain CSV files."""
    for path in directory.glob("*.csv.gz"):
        path.with_suffix("").write_bytes(gzip.decompress(path.read_bytes()))
        path.unlink()
    metadata = json.loads((directory / "evaluation.json").read_text())
    metadata["format_version"] = 3
    (directory / "evaluation.json").write_text(json.dumps(metadata))


def test_a_format_3_directory_of_plain_csv_files_still_loads(result, tmp_path):
    result.save(tmp_path)
    _as_format_3(tmp_path)
    assert not list(tmp_path.glob("*.gz"))

    loaded = Evaluation.load(tmp_path)

    assert loaded.config == result.config
    for name in ("periods", "summary", "quantiles"):
        pd.testing.assert_frame_equal(
            getattr(loaded, name), getattr(result, name), check_dtype=False, rtol=1e-12
        )
    for name, table in result.time_series.tables().items():
        pd.testing.assert_frame_equal(
            loaded.time_series.tables()[name], table, check_dtype=False, rtol=1e-12
        )
    for name, table in result.persistence.tables().items():
        pd.testing.assert_frame_equal(
            loaded.persistence.tables()[name], table, check_dtype=False, rtol=1e-12
        )
    assert loaded.metrics() == pytest.approx(result.metrics())


def test_saving_over_a_format_3_directory_replaces_its_plain_files(result, tmp_path):
    result.save(tmp_path)
    _as_format_3(tmp_path)

    result.save(tmp_path)

    assert not list(tmp_path.glob("*.csv"))
    assert json.loads((tmp_path / "evaluation.json").read_text())["format_version"] == 4
    assert Evaluation.load(tmp_path).metrics() == pytest.approx(result.metrics())
