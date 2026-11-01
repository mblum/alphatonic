"""Install an sdist-built wheel offline; provision .test-wheelhouse first."""

import os
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def run(command, *, cwd, env=None):
    result = subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    return result


def test_sdist_wheel_clean_consumer_resources_and_render(tmp_path):
    wheelhouse = Path(os.environ.get("ALPHATONIC_WHEELHOUSE", ROOT / ".test-wheelhouse"))
    assert wheelhouse.is_dir(), "Provision the offline wheelhouse as described in TESTING.md"
    archives = tmp_path / "archives"
    run(
        [sys.executable, "-m", "build", "--sdist", "--no-isolation", "--outdir", str(archives)],
        cwd=ROOT,
    )
    sdist = next(archives.glob("*.tar.gz"))
    with tarfile.open(sdist) as archive:
        assert any(p.endswith("/LICENSE") for p in archive.getnames())
    environment = tmp_path / "consumer"
    run([sys.executable, "-m", "venv", str(environment)], cwd=tmp_path)
    python = environment / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    wheels = tmp_path / "wheels"
    wheels.mkdir()
    run(
        [
            str(python),
            "-m",
            "pip",
            "wheel",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            "--no-deps",
            "--wheel-dir",
            str(wheels),
            str(sdist),
        ],
        cwd=tmp_path,
    )
    wheel = next(wheels.glob("alphatonic*.whl"))
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        for resource in [
            "py.typed",
            "report/templates/tearsheet.html",
            "report/static/alphatonic.js",
            "report/static/d3.min.js",
            "report/static/plot.umd.min.js",
            "report/static/pico.LICENSE.md",
            "report/static/d3.LICENSE.md",
            "report/static/plot.LICENSE.md",
        ]:
            assert "alphatonic/" + resource in names
        metadata = archive.read(
            next(n for n in names if n.endswith(".dist-info/METADATA"))
        ).decode()
        for tool in ["hypothesis", "scipy", "playwright", "pytest"]:
            assert f"Requires-Dist: {tool}" not in metadata
    run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--no-index",
            "--find-links",
            str(wheelhouse),
            str(wheel),
        ],
        cwd=tmp_path,
    )
    code = """
from importlib.resources import files
from alphatonic import evaluate
from alphatonic.demo import synthetic_market
import alphatonic
assert 'site-packages' in alphatonic.__file__
r=evaluate(*synthetic_market(4,40),min_assets=3,horizons=[1],time_series={'bootstrap_samples':0})
assert 'chart-data' in r.render_tearsheet()
assert files('alphatonic').joinpath('report/static/pico.LICENSE.md').is_file()
"""
    run([str(python), "-c", code], cwd=tmp_path)
