"""What the tearsheet and the list of trials share: templates and one inlined stylesheet.

The stylesheet is [Pico CSS](https://picocss.com) (classless build, MIT licence, vendored in
`static/` with its licence) followed by `static/alphatonic.css`. Both are written into each page,
so a page needs no network and no other file.

The tearsheet's charts are drawn by [Observable Plot](https://observablehq.com/plot/) and
[d3](https://d3js.org) (both ISC licence, vendored in `static/` with their licences), and by
`static/alphatonic.js`, which turns the chart specifications of `figures.py` into Plot calls. They
too are written into the page.
"""

from __future__ import annotations

from functools import cache
from importlib.resources import files

from jinja2 import Environment, PackageLoader, select_autoescape

PICO = "pico.classless.min.css"
"""The vendored Pico build: classless, version 2.1.1. `alphatonic.css` sets its accent colour."""
D3 = "d3.min.js"
"""The vendored d3 build, version 7.9.0, which Observable Plot needs."""
PLOT = "plot.umd.min.js"
"""The vendored Observable Plot build, version 0.6.17."""
CHARTS = "alphatonic.js"
"""The script that draws the chart specifications."""


@cache
def environment() -> Environment:
    """Return the Jinja environment of the report templates, with HTML escaping on.

    The `tojson` filter refuses `NaN` and infinities: a chart specification holds `None` for a
    value that is missing, and a page must not hide one that slipped through as invalid JSON.
    """
    environment = Environment(
        loader=PackageLoader("alphatonic.report", "templates"),
        autoescape=select_autoescape(["html"]),
    )
    environment.policies["json.dumps_kwargs"] = {"sort_keys": True, "allow_nan": False}
    environment.globals["stylesheet"] = stylesheet()
    environment.globals["libraries"] = libraries()
    environment.globals["chart_script"] = static(CHARTS)
    return environment


def static(name: str) -> str:
    """Return a file of the package's `static` directory as text."""
    return (files("alphatonic.report") / "static" / name).read_text(encoding="utf-8")


@cache
def stylesheet() -> str:
    """Return Pico's stylesheet followed by alphatonic's additions."""
    return "\n".join(static(name) for name in (PICO, "alphatonic.css"))


@cache
def libraries() -> str:
    """Return d3 followed by Observable Plot, which needs it."""
    return "\n".join(static(name) for name in (D3, PLOT))


__all__ = ["CHARTS", "D3", "PICO", "PLOT", "environment", "libraries", "static", "stylesheet"]
