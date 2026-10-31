"""Run the Python examples in the README and the documentation.

Blocks of one page run in order in a shared namespace, inside a temporary directory, so later
blocks can use earlier results and files written by the examples do not litter the checkout.
A block preceded by an `<!-- notest -->` line is skipped.

It also checks the docstrings in `src/`, which mkdocstrings renders as the API reference.
"""

import ast
import re
import textwrap
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = sorted({p.resolve() for p in [*ROOT.glob("*.md"), *DOCS.rglob("*.md")]})
# Root files that GitHub and PyPI show, and that are not part of the site.
ROOT_PAGES = ["README.md", "CONTRIBUTING.md", "CHANGELOG.md"]
SRC = ROOT / "src" / "alphatonic"
SITE = "https://mblum.github.io/alphatonic/"
SOURCES = "https://github.com/mblum/alphatonic/blob/master/"


OPEN = re.compile(r"^(\s*)```python\s*$")
CLOSE = re.compile(r"^(\s*)```\s*$")
FENCED = re.compile(r"^[ \t]*(`{3,}|~{3,}).*?^[ \t]*\1[ \t]*$", re.MULTILINE | re.DOTALL)
LINK = re.compile(
    r"\]\(\s*<?([^)\s>]+)"  # [text](destination "title")
    r"|^ {0,3}\[(?!\^)[^\]]+\]:\s*<?([^\s>]+)"  # [label]: destination
    r"|\b(?:href|src)\s*=\s*[\"']([^\"']+)[\"']",  # <a href="destination">
    re.MULTILINE | re.IGNORECASE,
)


def link_targets(text: str) -> list[str]:
    """Return the destination of every link in Markdown text, ignoring code."""
    prose = re.sub(r"`[^`\n]*`", "", FENCED.sub("", text))
    return [next(group for group in match.groups() if group) for match in LINK.finditer(prose)]


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
    assert {"README.md", "first-evaluation.md", "prepare-inputs.md"} <= names


def test_link_targets_finds_every_link_form_outside_code():
    text = (
        '[a](docs/a.md) and [b](<docs/b.md> "title")\n\n'
        "[c]: docs/c.md\n[^1]: A footnote.\n\n"
        '<a href="docs/d.md">d</a>\n\n'
        "`f[0](1)` is code.\n\n```python\nf[0](1)\n```\n"
    )
    assert link_targets(text) == ["docs/a.md", "docs/b.md", "docs/c.md", "docs/d.md"]


@pytest.mark.parametrize("source", ROOT_PAGES)
def test_root_page_links_work_outside_the_repository(source):
    """Shared pages must not rely on repository-relative link resolution."""
    for target in link_targets((ROOT / source).read_text(encoding="utf-8")):
        url = urlsplit(target)
        assert url.scheme or url.netloc or not url.path, target


@pytest.mark.parametrize("source", ROOT_PAGES)
def test_root_page_links_into_the_project_name_existing_files(source):
    """Absolute links to the site and the sources must not outlive the page or file they name."""
    for target in link_targets((ROOT / source).read_text(encoding="utf-8")):
        path = urlsplit(target).path
        if target.startswith(SITE):
            page = path.removeprefix(urlsplit(SITE).path).strip("/")
            candidates = [DOCS / page, DOCS / f"{page}.md", DOCS / page / "index.md"]
        elif target.startswith(SOURCES):
            candidates = [ROOT / path.removeprefix(urlsplit(SOURCES).path)]
        else:
            continue
        assert any(candidate.is_file() for candidate in candidates), target


def test_documentation_home_is_independent():
    home = DOCS / "index.md"
    assert not home.is_symlink()
    assert home.read_text() != (ROOT / "README.md").read_text()


# The Google-style headings that mkdocstrings (Griffe) reads as sections. Any other `Word:` line
# followed by an indented block becomes an admonition, which renders its content as Markdown.
DOCSTRING_SECTIONS = {"args", "attributes", "examples", "raises", "returns", "yields"}
HEADING = re.compile(r"^\s*(\w[\w -]*):\s*$")
FENCE = re.compile(r"^[ ]*```python\n(.*?)^[ ]*```", re.MULTILINE | re.DOTALL)


def docstrings():
    """Yield `(location, text)` for each docstring in `src/`, dedented."""
    for path in sorted(SRC.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Module | ast.ClassDef | ast.FunctionDef | ast.AsyncFunctionDef):
                text = ast.get_docstring(node)
                if text:
                    name = getattr(node, "name", "module")
                    yield f"{path.relative_to(ROOT)}:{node.body[0].lineno} ({name})", text


def test_docstrings_have_no_doctest_prompts():
    """`>>>` lines render as nested quotations and cannot be pasted; use a fenced block."""
    found = [where for where, text in docstrings() if re.search(r"^\s*(>>>|\.\.\. )", text, re.M)]
    assert not found, f"use a fenced ```python block instead of `>>>` in {found}"


def test_docstring_headings_are_sections_mkdocstrings_knows():
    """`Example:` is not a section, so mkdocstrings makes it an admonition; write `Examples:`."""
    found = []
    for where, text in docstrings():
        in_code = False
        for line in text.splitlines():
            in_code ^= line.lstrip().startswith("```")
            heading = HEADING.match(line)
            if heading and not in_code and heading.group(1).lower() not in DOCSTRING_SECTIONS:
                found.append(f"{where}: {line.strip()}")
    assert not found, f"headings that mkdocstrings reads as admonitions: {found}"


def test_docstring_examples_run(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    count = 0
    for where, text in docstrings():
        for match in FENCE.finditer(text):
            try:
                exec(
                    compile(textwrap.dedent(match.group(1)), where, "exec"),
                    {"__name__": "__docs__"},
                )  # noqa: S102
            except Exception as error:
                error.add_note(f"in the docstring example at {where}")
                raise
            count += 1
    assert count, "no docstring has an example"


def test_docstring_checks_catch_the_mistakes_they_guard_against():
    assert HEADING.match("    Example:") and "example" not in DOCSTRING_SECTIONS
    assert HEADING.match("Examples:") and "examples" in DOCSTRING_SECTIONS
    assert not HEADING.match("Returns: a value")
    assert FENCE.search("Examples:\n    ```python\n    x = 1\n    ```\n")
