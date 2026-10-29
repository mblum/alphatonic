"""What the tearsheet and the list of trials share: templates and one inlined stylesheet.

The stylesheet is [Pico CSS](https://picocss.com) (classless build, MIT licence, vendored in
`static/` with its licence) followed by `static/alphatonic.css`. Both are written into each page,
so a page needs no network and no other file.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

from jinja2 import Environment, PackageLoader, select_autoescape

PICO = "pico.classless.min.css"
"""The vendored Pico build: classless, version 2.1.1. `alphatonic.css` sets its accent colour."""


@cache
def environment() -> Environment:
    """Return the Jinja environment of the report templates, with HTML escaping on."""
    environment = Environment(
        loader=PackageLoader("alphatonic.report", "templates"),
        autoescape=select_autoescape(["html"]),
    )
    environment.globals["stylesheet"] = stylesheet()
    return environment


@cache
def stylesheet() -> str:
    """Return Pico's stylesheet followed by alphatonic's additions."""
    static = files("alphatonic.report") / "static"
    return "\n".join(
        (static / name).read_text(encoding="utf-8") for name in (PICO, "alphatonic.css")
    )


__all__ = ["PICO", "environment", "stylesheet"]
