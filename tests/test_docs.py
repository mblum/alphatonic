"""Run the Python examples in the README and the documentation.

Blocks of one page run in order in a shared namespace, inside a temporary directory, so later
blocks can use earlier results and files written by the examples do not litter the checkout.
A block preceded by an `<!-- notest -->` line is skipped.
"""

import re
from pathlib import Path
from urllib.parse import unquote, urlsplit

import pytest
from jinja2 import Environment, FileSystemLoader, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
PAGES = sorted({p.resolve() for p in [*ROOT.glob("*.md"), *(ROOT / "docs").rglob("*.md")]})
SHARED_PAGES = (
    ROOT / "docs/index.md",
    ROOT / "docs/changelog.md",
    ROOT / "docs/contributing/development.md",
)
TEMPLATES = Environment(loader=FileSystemLoader(ROOT / "docs/_includes"), undefined=StrictUndefined)


def page_text(path: Path) -> str:
    """Expand shared root files with the same Jinja includes used by Zensical."""
    if path in SHARED_PAGES:
        return TEMPLATES.from_string(path.read_text(encoding="utf-8")).render()
    return path.read_text(encoding="utf-8")


OPEN = re.compile(r"^(\s*)```python\s*$")
CLOSE = re.compile(r"^(\s*)```\s*$")


def blocks(path: Path):
    """Yield `(line number, code)` for each runnable Python block of a Markdown file."""
    lines = page_text(path).splitlines()
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


@pytest.mark.parametrize("page", SHARED_PAGES, ids=lambda p: str(p.relative_to(ROOT)))
def test_shared_page_links_resolve_inside_docs(page):
    """Included GitHub links must point to site sources after path adaptation."""
    text = page_text(page)
    assert "{%" not in text
    assert "# " in text
    for target in re.findall(r"\]\(([^)]+)\)", text):
        url = urlsplit(target)
        if url.scheme or url.netloc or not url.path:
            continue
        destination = (page.parent / unquote(url.path)).resolve()
        assert destination.is_relative_to(ROOT / "docs"), target
        assert destination.is_file(), target


def test_home_page_uses_readme_example():
    """Changing the README example must change the site's example as well."""
    assert [code for _, code in blocks(ROOT / "docs/index.md")] == [
        code for _, code in blocks(ROOT / "README.md")
    ]
