"""Run the Python examples in the README and the documentation.

Blocks of one page run in order in a shared namespace, inside a temporary directory, so later
blocks can use earlier results and files written by the examples do not litter the checkout.
A block preceded by an `<!-- notest -->` line is skipped.
"""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted([ROOT / "README.md", *(ROOT / "docs").rglob("*.md")])
OPEN = re.compile(r"^(\s*)```python\s*$")
CLOSE = re.compile(r"^(\s*)```\s*$")


def blocks(path: Path):
    """Yield `(line number, code)` for each runnable Python block of a Markdown file."""
    lines = path.read_text(encoding="utf-8").splitlines()
    i = 0
    while i < len(lines):
        opening = OPEN.match(lines[i])
        if not opening:
            i += 1
            continue
        indent = len(opening.group(1))
        previous = next((line.strip() for line in reversed(lines[:i]) if line.strip()), "")
        start = i + 1
        i += 1
        body = []
        while i < len(lines) and not CLOSE.match(lines[i]):
            body.append(lines[i][indent:])
            i += 1
        i += 1
        if previous != "<!-- notest -->":
            yield start + 1, "\n".join(body)


def pages_with_examples():
    return [p for p in PAGES if any(True for _ in blocks(p))]


@pytest.mark.parametrize("page", pages_with_examples(), ids=lambda p: str(p.relative_to(ROOT)))
def test_examples_run(page, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    namespace = {"__name__": "__docs__"}
    for line, code in blocks(page):
        try:
            exec(compile(code, f"{page.name}:{line}", "exec"), namespace)  # noqa: S102
        except Exception as error:
            error.add_note(f"in the example at {page.relative_to(ROOT)}:{line}")
            raise


def test_examples_exist_in_the_main_pages():
    names = {p.name for p in pages_with_examples()}
    assert {"README.md", "index.md", "first-evaluation.md", "prepare-inputs.md"} <= names
