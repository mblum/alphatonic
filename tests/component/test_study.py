import json
from pathlib import Path

import pandas as pd
import pytest
from pydantic import ValidationError

from alphatonic import HoldoutError, Study, UnknownTrialError
from alphatonic.study import Trial, _fingerprint


def test_holdout_exact_boundary_and_crossing_rejection(tmp_path):
    s = Study(tmp_path, holdout_start="2024-02-01")
    boundary = pd.Timestamp("2024-02-01", tz="UTC")
    assert s.window() == (None, boundary)
    assert s.window(holdout=True) == (boundary, None)
    for kwargs in [
        {"end": "2024-02-02"},
        {"start": "2024-01-31", "holdout": True},
        {"start": "2024-02-01"},
        {"start": "2024-02-02", "end": "2024-02-01", "holdout": True},
    ]:
        with pytest.raises(HoldoutError):
            s.window(**kwargs)
    with pytest.raises(HoldoutError):
        Study(tmp_path).window(holdout=True)


def test_repeated_variants_preserve_family_counts_across_samples(panel, config, tmp_path):
    s = Study(tmp_path, holdout_start="2024-02-01", name="Research")
    records = [
        s.evaluate(
            *panel,
            config,
            signal="Signal / <name>",
            family="idea",
            parameters={"a": 1},
            holdout=holdout,
        )
        for holdout in [False, False, True]
    ]
    assert len({t.id for t in records}) == 3
    fresh = Study(tmp_path)
    assert len(fresh.trials()) == 3
    assert all(t.data_fingerprint == records[0].data_fingerprint for t in records)
    board = fresh.board(sort="adjusted_p")
    assert board.trials.tolist() == [3, 3, 3]
    assert board.holdout_uses.tolist() == [1, 1, 1]
    for row in board.itertuples():
        if pd.notna(row.cs_p):
            assert row.adjusted_p == pytest.approx(min(1, row.cs_p * 3))
    doc = fresh.to_dict()
    json.dumps(doc, allow_nan=False)
    assert doc["families"] == {"idea": {"trials": 3, "holdout_uses": 1}}
    assert set(doc["horizons"]) == set(config.horizons)
    for trial in records:
        loaded = fresh.evaluation(trial.id)
        assert loaded.start == trial.start and loaded.end == trial.end
    with pytest.raises(ValueError, match="sort"):
        fresh.board(sort="parameters")
    with pytest.raises(ValueError, match="board columns"):
        s.evaluate(*panel, config, signal="x", context={"id": "bad"})
    with pytest.raises(TypeError):
        s.evaluate(*panel, config, signal="x", horizons=[1])


@pytest.mark.parametrize("identifier", ["../x", "%2e%2e", "unknown", "/etc/passwd", "a/b", ""])
def test_unknown_and_unsafe_identifiers_refused(tmp_path, identifier):
    with pytest.raises(UnknownTrialError):
        Study(tmp_path).trial(identifier)


def test_unreadable_partial_legacy_future_and_extra_records(tmp_path, panel, config):
    s = Study(tmp_path)
    assert s.trials() == [] and s.board().empty
    trial = s.evaluate(*panel, config, signal="a")
    data = trial.model_dump(mode="json")
    data.pop("family")
    data["extra"] = "allowed"
    assert Trial.model_validate(data).family == "a"
    data["format_version"] = 99
    with pytest.raises(ValidationError):
        Trial.model_validate(data)
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "record.json").write_text("{")
    partial = tmp_path / "abandoned"
    partial.mkdir()
    (partial / "record.json.partial").write_text("{}")
    assert len(s.trials()) == 1
    assert s.unreadable() == [bad / "record.json"]
    assert s.to_dict()["unreadable"] == ["bad/record.json"]


def test_failure_before_record_commit_does_not_count(panel, config, tmp_path, monkeypatch):
    from alphatonic import Evaluation

    s = Study(tmp_path)
    original = s.evaluate(*panel, config, signal="ok")
    record = tmp_path / original.id / "record.json"
    before = record.read_bytes()

    def fail(*args, **kwargs):
        raise OSError("injected save failure")

    monkeypatch.setattr(Evaluation, "save", fail)
    with pytest.raises(OSError, match="injected"):
        s.evaluate(*panel, config, signal="fails")
    assert [t.id for t in s.trials()] == [original.id]
    assert record.read_bytes() == before


def test_fingerprint_tracks_raw_values_index_and_labels(panel):
    x, p = panel
    expected = _fingerprint(x, p)
    assert expected == _fingerprint(x.copy(), p.copy())
    for changed in [
        x + 1,
        x.rename(columns=lambda c: c + "new"),
        x.set_axis(x.index + pd.Timedelta("1h")),
    ]:
        assert _fingerprint(changed, p) != expected


def test_forced_identifier_collision_refuses_overwrite(panel, config, tmp_path, monkeypatch):
    from datetime import UTC, datetime
    from types import SimpleNamespace

    class FixedClock:
        @classmethod
        def now(cls, tz):
            return datetime(2024, 6, 1, tzinfo=UTC)

    monkeypatch.setattr("alphatonic.study.datetime", FixedClock)
    monkeypatch.setattr("alphatonic.study.uuid4", lambda: SimpleNamespace(hex="abcdef012345"))
    s = Study(tmp_path)
    first = s.evaluate(*panel, config, signal="collision")
    before = {p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()}
    with pytest.raises(FileExistsError):
        s.evaluate(panel[0] * -1, panel[1], config, signal="collision")
    assert [t.id for t in s.trials()] == [first.id]
    assert before == {
        p.relative_to(tmp_path): p.read_bytes() for p in tmp_path.rglob("*") if p.is_file()
    }


@pytest.mark.parametrize("failure", ["report", "rename"])
def test_failed_report_or_record_rename_has_no_commit(
    panel, config, tmp_path, monkeypatch, failure
):
    from alphatonic import Evaluation

    def fail(*args, **kwargs):
        raise OSError("injected commit failure")

    if failure == "report":
        monkeypatch.setattr(Evaluation, "tearsheet", fail)
    else:
        monkeypatch.setattr(Path, "replace", fail)
    study = Study(tmp_path)
    with pytest.raises(OSError, match="injected"):
        study.evaluate(*panel, config, signal="failed", report=failure == "report")
    assert study.trials() == []
    assert not list(tmp_path.glob("*/record.json"))
    if failure == "rename":
        assert list(tmp_path.glob("*/record.json.partial"))


def test_holdout_clamps_actual_end_and_rejects_empty_data_window(panel, config, tmp_path):
    study = Study(tmp_path, holdout_start="2030-01-01")
    trial = study.evaluate(*panel, config, signal="clamped")
    assert trial.end == panel[1].index[-1] + pd.Timedelta("1D")
    with pytest.raises(ValueError, match="prices end"):
        study.evaluate(*panel, config, signal="outside", holdout=True)
    assert "Study(" in repr(study)


def test_hand_authored_record_loaded_by_fresh_study(tmp_path):
    import shutil

    source = Path(__file__).parents[1] / "data/studies/v1"
    shutil.copytree(source, tmp_path / "records")
    study = Study(tmp_path / "records")
    records = study.trials()
    assert len(records) == 1 and records[0].family == "manual"
    assert records[0].metrics["cs.h1.spearman.mean"] == 0.5
    assert study.board().trials.item() == 1
