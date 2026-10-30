"""Run the Python examples in the README and the documentation.

Blocks of one page run in order in a shared namespace, inside a temporary directory, so later
blocks can use earlier results and files written by the examples do not litter the checkout.
A block preceded by an `<!-- notest -->` line is skipped.
"""

import re
from pathlib import Path
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
PAGES = sorted({p.resolve() for p in [*ROOT.glob("*.md"), *DOCS.rglob("*.md")]})
# Pages of the site that are symlinks to root files, which GitHub and PyPI also show.
SHARED_PAGES = {
    "docs/changelog.md": "CHANGELOG.md",
    "docs/contributing/development.md": "CONTRIBUTING.md",
}
ROOT_PAGES = ["README.md", *SHARED_PAGES.values()]
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


@pytest.mark.parametrize("page, source", SHARED_PAGES.items(), ids=list(SHARED_PAGES))
def test_shared_pages_are_symlinks_to_the_root_files(page, source):
    """A copy under `docs/` would drift from the root file, and its examples would run twice."""
    assert (ROOT / page).resolve() == ROOT / source


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
