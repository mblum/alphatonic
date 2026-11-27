import json
from html.parser import HTMLParser

import pytest

from alphatonic import ReportOptions, Study
from alphatonic.report.board import render_board


class Page(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.external = []
        self.capture = False
        self.payload = ""
        self.scripts = 0
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag in ["script", "link"] and ("src" in values or "href" in values):
            self.external.append(values)
        if tag == "script":
            self.scripts += 1
            self.capture = values.get("id") == "chart-data"

    def handle_data(self, data):
        if self.capture:
            self.payload += data

    def handle_endtag(self, tag):
        if tag == "script":
            self.capture = False


def test_report_offline_strict_payload_escapes_custom_text_and_chart_kinds(result):
    attack = '</script><script>alert("x")</script>'
    page = result.render_tearsheet(
        title=attack, subtitle=attack, context={attack: attack}, footer=[attack], eyebrow=attack
    )
    parsed = Page(page)
    assert parsed.external == []
    assert attack not in page and "&lt;/script&gt;" in page
    specs = json.loads(parsed.payload)
    assert specs and {s["kind"] for s in specs.values()} == {
        "lines",
        "heatmap",
        "bars",
        "rolling",
        "intervals",
    }
    assert "\\u003c" in parsed.payload or attack not in parsed.payload
    for spec in specs.values():
        json.dumps(spec, allow_nan=False)
    assert result.config.horizons[0] in result.ic().columns


def test_report_legacy_missing_analyses_and_empty_rejection(result, tmp_path):
    result.persistence = None
    result.time_series = None
    assert "chart-data" in result.render_tearsheet(options=ReportOptions(min_periods=1))
    path = result.tearsheet(tmp_path / "nested" / "report.html")
    assert path.is_file()
    result.periods = result.periods.iloc[:0]
    with pytest.raises(ValueError):
        result.render_tearsheet()


def test_all_unavailable_report_keeps_nulls(result):
    result.periods[["spearman", "pearson"]] = float("nan")
    result.periods["status"] = "constant_signal"
    page = Page(result.render_tearsheet())
    specs = json.loads(page.payload)
    lines = [s for s in specs.values() if s["kind"] == "lines" and "panels" in s]
    assert any(
        panel.get("empty") == "No valid cross-sectional observations"
        for spec in lines
        for panel in spec["panels"]
    )


class Board(HTMLParser):
    """The headings of the list's columns and how many trials it lists."""

    def __init__(self, text):
        super().__init__()
        self.headings = []
        self.trials = 0
        self.scripts = []
        self.column = False
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        self.column = self.column or (tag == "th" and values.get("scope") == "col")
        if tag == "tr" and "trial" in (values.get("class") or "").split():
            self.trials += 1
        if tag == "script":
            self.scripts.append(values)

    def handle_data(self, data):
        if self.column and self.lasttag == "a" and data.strip():
            self.headings.append(data.strip())
            self.column = False


def test_board_overview_views_horizon_search_and_escaping(panel, config, tmp_path):
    study = Study(tmp_path)
    one = config.model_copy(update={"horizons": (1,)})
    study.evaluate(*panel, one, signal="trend", parameters={"length": 5, "scale": "atr"})
    study.evaluate(
        *panel,
        config,
        signal="trend",
        parameters={"length": 20, "scale": "atr"},
        note="neighbour <b>",
    )
    overview = ["Rank IC", "z", "p × trials", "Rank IC", "p × trials", "Cosine", "p × trials"]

    page = render_board(study)
    parsed = Board(page)
    assert parsed.headings == ["Signal", *overview, "Trials"] and parsed.trials == 2
    assert all("src" not in script for script in parsed.scripts)
    assert "neighbour &lt;b&gt;" in page and "neighbour <b>" not in page
    assert '<span class="varied">length=20</span>' in page and ">scale=atr<" not in page

    assert Board(render_board(study, show="data")).headings[:2] == ["Signal", "Window"]
    assert Board(render_board(study, show="")).headings == ["Signal"]
    assert len(Board(render_board(study, show="cs,ts,cosine,data,testing")).headings) == 20
    # A column the list is sorted by joins the overview, so the order is never unexplained.
    assert Board(render_board(study, sort="cs_p")).headings[:4] == ["Signal", "Rank IC", "z", "p ▲"]

    later = render_board(study, horizon=3)
    assert Board(later).trials == 1 and "1 more was not evaluated at this horizon" in later
    assert Board(render_board(study, horizon=3, rows="all")).trials == 2
    assert Board(render_board(study, search="LENGTH=20 neighbour")).trials == 1
    absent = render_board(study, search="absent")
    assert Board(absent).trials == 0 and "Clear the filter" in absent
