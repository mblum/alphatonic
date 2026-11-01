import importlib.metadata
import subprocess
import sys
from importlib.resources import files

import pytest

import alphatonic


def test_public_exports_version_and_typing_marker():
    for name in alphatonic.__all__:
        assert getattr(alphatonic, name) is not None
    assert alphatonic.__version__ == importlib.metadata.version("alphatonic")
    assert files("alphatonic").joinpath("py.typed").is_file()


@pytest.mark.parametrize("module", ["alphatonic", "alphatonic.server", "alphatonic.cli"])
def test_imports_in_fresh_interpreter_are_lazy(module, tmp_path):
    code = (
        f"import {module}; import sys; "
        "assert 'jinja2' not in sys.modules; "
        "assert 'alphatonic.report' not in sys.modules"
    )
    result = subprocess.run(
        [sys.executable, "-c", code], capture_output=True, text=True, cwd=tmp_path, timeout=15
    )
    assert result.returncode == 0, result.stderr
