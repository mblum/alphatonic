"""Execute each page in its own working directory, preserving block order."""

import ast
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PAGES = [ROOT / "README.md", ROOT / "CONTRIBUTING.md", *sorted((ROOT / "docs").rglob("*.md"))]
PAGES = [p for p in PAGES if "```python" in p.read_text()]


@pytest.mark.parametrize("page", PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_documentation_python_examples_execute(page, tmp_path):
    blocks = re.findall(r"^[ \t]*```python[ \t]*\n(.*?)^[ \t]*```", page.read_text(), re.M | re.S)
    code = "\n\n".join(textwrap.dedent(block) for block in blocks)
    result = subprocess.run(
        [sys.executable, "-c", code], cwd=tmp_path, capture_output=True, text=True, timeout=60
    )
    assert result.returncode == 0, f"{page}\n{result.stdout}\n{result.stderr}"


def test_public_docstring_examples_execute(tmp_path):
    for path in (ROOT / "src/alphatonic").rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                continue
            doc = ast.get_docstring(node) or ""
            blocks = re.findall(r"```python\s*\n(.*?)```", doc, re.S)
            if not blocks:
                continue
            result = subprocess.run(
                [sys.executable, "-c", "\n".join(textwrap.dedent(block) for block in blocks)],
                cwd=tmp_path,
                capture_output=True,
                text=True,
                timeout=60,
            )
            assert result.returncode == 0, f"{path}:{node.name}\n{result.stderr}"
