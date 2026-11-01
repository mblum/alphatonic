import json
from html.parser import HTMLParser

import pytest

from alphatonic import ReportOptions


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
