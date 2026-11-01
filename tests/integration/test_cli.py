import shutil
import subprocess
import sys

import pytest

from alphatonic import Study
from alphatonic.cli import main


@pytest.mark.parametrize(
    "entry", [[sys.executable, "-m", "alphatonic"], [shutil.which("alphatonic")]]
)
def test_cli_fresh_process_help_empty_and_invalid_sort(entry, tmp_path):
    for args, code, expected in [
        (["--help"], 0, "List or serve"),
        (["list", str(tmp_path)], 0, "No trials"),
        (["list", str(tmp_path), "--sort", "bad"], 2, "cannot sort"),
        ([], 2, "required"),
    ]:
        result = subprocess.run(
            [*entry, *args], capture_output=True, text=True, timeout=15, cwd=tmp_path
        )
        assert result.returncode == code and expected in result.stdout + result.stderr


def test_cli_populated_limits_direction_and_serve_dispatch(
    panel, config, tmp_path, capsys, monkeypatch
):
    s = Study(tmp_path)
    trial = s.evaluate(*panel, config, signal="cli")
    assert (
        main(
            [
                "list",
                str(tmp_path),
                "--horizon",
                "1",
                "--sort",
                "cs_ic",
                "--ascending",
                "--limit",
                "1",
            ]
        )
        == 0
    )
    assert trial.id in capsys.readouterr().out
    calls = []
    monkeypatch.setattr(
        "alphatonic.server.serve", lambda study, host, port: calls.append((host, port, study.name))
    )
    assert (
        main(["serve", str(tmp_path), "--host", "127.0.0.1", "--port", "8123", "--name", "Test"])
        == 0
    )
    assert calls == [("127.0.0.1", 8123, "Test")]


def test_cli_reports_unreadable_records(tmp_path, capsys):
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "record.json").write_text("{")
    assert main(["list", str(tmp_path)]) == 0
    assert "1 records could not be read" in capsys.readouterr().out
