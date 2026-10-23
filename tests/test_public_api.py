import importlib
import re

import alphatonic


def test_public_names_are_importable_and_documented():
    for name in alphatonic.__all__:
        assert hasattr(alphatonic, name)
    assert {"evaluate", "Evaluation", "EvaluationConfig", "forward_returns"} <= set(
        alphatonic.__all__
    )
    for name in (
        "evaluate",
        "Evaluation",
        "EvaluationConfig",
        "TimeSeriesOptions",
        "ReportOptions",
    ):
        assert getattr(alphatonic, name).__doc__


def test_version_is_a_pep_440_release():
    assert re.fullmatch(r"\d+\.\d+\.\d+.*", alphatonic.__version__)


def test_core_import_does_not_pull_in_the_reporting_dependencies():
    import subprocess
    import sys

    code = (
        "import sys, alphatonic; "
        "assert 'plotly' not in sys.modules and 'jinja2' not in sys.modules; "
        "assert 'alphatonic.report' not in sys.modules"
    )
    subprocess.run([sys.executable, "-W", "error", "-c", code], check=True)


def test_every_module_imports_cleanly():
    for module in (
        "config",
        "cross_section",
        "demo",
        "evaluation",
        "inputs",
        "persistence",
        "progress",
        "returns",
        "stats",
        "time_series",
        "report",
    ):
        importlib.import_module(f"alphatonic.{module}")
