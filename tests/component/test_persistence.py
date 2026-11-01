import json
from pathlib import Path

import pytest

from alphatonic import Evaluation
from tests.support.assertions import same_frame

DATA = Path(__file__).parents[1] / "data" / "evaluations"


def test_roundtrip_every_table_metadata_and_deterministic_gzip(result, tmp_path):
    result.save(tmp_path)
    first = {p.name: p.read_bytes() for p in tmp_path.glob("*.gz")}
    loaded = Evaluation.load(tmp_path)
    for name in ["periods", "summary", "quantiles"]:
        same_frame(getattr(loaded, name), getattr(result, name))
    for subsystem in ["time_series", "persistence"]:
        for name, table in getattr(result, subsystem).tables().items():
            same_frame(getattr(loaded, subsystem).tables()[name], table)
    assert (
        loaded.config == result.config and loaded.start == result.start and loaded.end == result.end
    )
    assert loaded.bar == result.bar and loaded.forward_returns == {} and loaded.volatility is None
    result.save(tmp_path)
    assert first == {p.name: p.read_bytes() for p in tmp_path.glob("*.gz")}
    json.dumps(loaded.to_dict(), allow_nan=False)


@pytest.mark.parametrize("version", [1, 2, 3, 4, 5])
def test_immutable_historical_evaluations_readable(version):
    result = Evaluation.load(DATA / f"v{version}")
    assert result.periods.n_pairs.tolist() == [3, 0]
    assert result.periods.status.tolist() == ["valid", "insufficient_assets"]
    assert result.periods.spearman.iloc[0] == 1
    assert result.time_series is None and result.persistence is None
    if version == 1:
        assert result.config.target == result.config.time_series.target == "return"


def test_metadata_errors_missing_tables_fallback_and_compressed_preference(result, tmp_path):
    with pytest.raises(ValueError, match="EvaluationConfig"):
        Evaluation.load(tmp_path)
    result.save(tmp_path)
    metadata = tmp_path / "evaluation.json"
    data = json.loads(metadata.read_text())
    metadata.write_text("{")
    with pytest.raises(json.JSONDecodeError):
        Evaluation.load(tmp_path)
    metadata.write_text(json.dumps({**data, "format_version": 999}))
    with pytest.raises(ValueError, match="format"):
        Evaluation.load(tmp_path)
    metadata.unlink()
    loaded = Evaluation.load(tmp_path, result.config)
    assert loaded.start == result.start and loaded.end == result.end and loaded.bar == result.bar
    (tmp_path / "ic_by_timestamp.csv").write_text("corrupt")
    assert len(Evaluation.load(tmp_path, result.config).periods) == len(result.periods)
    (tmp_path / "ic_by_timestamp.csv.gz").unlink()
    (tmp_path / "ic_by_timestamp.csv").unlink()
    with pytest.raises(FileNotFoundError):
        Evaluation.load(tmp_path, result.config)


def test_repeated_save_removes_plain_and_stale_persistence(result, tmp_path):
    result.save(tmp_path)
    (tmp_path / "ic_by_timestamp.csv").write_text("stale")
    result.persistence = None
    result.save(tmp_path)
    assert not (tmp_path / "ic_by_timestamp.csv").exists()
    assert not list(tmp_path.glob("persistence_*"))
    assert Evaluation.load(tmp_path).persistence is None


def test_table_write_failure_is_visible_and_not_transactional(result, tmp_path, monkeypatch):
    import alphatonic.persistence as storage

    def fail(*args, **kwargs):
        raise OSError("injected table failure")

    monkeypatch.setattr(storage, "_write", fail)
    with pytest.raises(OSError, match="injected"):
        result.save(tmp_path)
    assert not (tmp_path / "evaluation.json").exists()


def test_replacing_evaluation_without_time_series_removes_stale_tables(result, tmp_path):
    result.save(tmp_path)
    result.time_series = None
    result.save(tmp_path)
    assert not list(tmp_path.glob("ts_*.csv*"))
    assert Evaluation.load(tmp_path).time_series is None
