import subprocess
import sys

import pytest

from alphatonic import Study
from alphatonic.cli import main
from test_study import record, saved


@pytest.fixture
def study(tmp_path):
    study = Study(tmp_path / "study")
    saved(
        study,
        record("first", hours=1, cs_ic=0.02, p=0.01),
        record("second", hours=2, cs_ic=None, p=None),
    )
    return study


def test_list_prints_the_trials_sorted_by_a_column(study, capsys):
    assert main(["list", str(study.directory), "--sort", "cs_ic"]) == 0

    out = capsys.readouterr().out
    assert out.startswith("Horizon: 1 bar\n")
    assert out.index("first") < out.index("second")
    assert "0.0200" in out and "–" in out


def test_list_takes_a_direction_and_a_limit(study, capsys):
    main(["list", str(study.directory), "--sort", "created_at", "--ascending", "--limit", "1"])

    out = capsys.readouterr().out
    assert "first" in out and "second" not in out


def test_list_refuses_an_unknown_column(study, capsys):
    with pytest.raises(SystemExit) as exit:
        main(["list", str(study.directory), "--sort", "sharpe"])

    assert exit.value.code == 2
    assert "sort by one of created_at" in capsys.readouterr().err


def test_list_of_an_empty_directory_says_so(tmp_path, capsys):
    main(["list", str(tmp_path)])

    assert "No trials in" in capsys.readouterr().out


def test_serve_serves_the_study_at_the_address_given(study, monkeypatch, capsys):
    calls = []
    monkeypatch.setattr("alphatonic.server.serve", lambda *args: calls.append(args))

    assert main(["serve", str(study.directory), "--port", "8123", "--name", "demo"]) == 0

    ((served, host, port),) = calls
    assert (served.directory, served.name, host, port) == (
        study.directory,
        "demo",
        "127.0.0.1",
        8123,
    )
    assert "http://127.0.0.1:8123" in capsys.readouterr().out


def test_the_module_runs_the_command(study):
    completed = subprocess.run(
        [sys.executable, "-m", "alphatonic", "list", str(study.directory)],
        capture_output=True,
        text=True,
        check=True,
    )

    assert "first" in completed.stdout
