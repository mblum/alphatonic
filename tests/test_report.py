import importlib
import sys
from html.parser import HTMLParser

import numpy as np
import pandas as pd
import pytest

from alphatonic import Evaluation, EvaluationConfig, ReportOptions, evaluate
from alphatonic.report import render_tearsheet
from alphatonic.report.figures import horizon_label, method_figures
from conftest import regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 100, "rolling_window": "5D"}


def crafted(periods=None, summary=None, **config):
    """An evaluation with hand-written cross-sectional tables."""
    if periods is None:
        periods = pd.DataFrame(
            {
                "timestamp": pd.date_range("2026-01-01", periods=5, freq="h", tz="UTC"),
                "horizon": 1,
                "spearman": [0.2, np.nan, 0.6, -0.2, np.nan],
                "pearson": [0.1, np.nan, 0.7, -0.2, np.nan],
                "n_available": 5,
                "n_signal": 5,
                "n_pairs": [5, 2, 5, 5, 0],
                "pair_coverage": [1, 0.4, 1, 1, 0],
                "status": ["valid", "insufficient_assets", "valid", "valid", "insufficient_assets"],
            }
        )
    if summary is None:
        summary = pd.DataFrame(
            [
                {
                    "horizon": 1,
                    "method": method,
                    "mean": 0.2,
                    "ci95_lower": -0.1,
                    "ci95_upper": 0.5,
                    "n_periods": 3,
                    "skipped_periods": 2,
                    "mean_pair_coverage": 0.68,
                }
                for method in ("spearman", "pearson")
            ]
        )
    return Evaluation(
        config=EvaluationConfig(horizons=[1], mode="cross_sectional", **config),
        start=pd.Timestamp("2026-01-01", tz="UTC"),
        end=pd.Timestamp("2026-01-01 05:00", tz="UTC"),
        bar=pd.Timedelta(hours=1),
        periods=periods,
        summary=summary,
        quantiles=pd.DataFrame(
            columns=["timestamp", "horizon", "quantile", "mean_return", "n_pairs"]
        ),
    )


class ReportParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.external_scripts, self.ids, self.tables, self.links = [], [], [], []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and "src" in attrs:
            self.external_scripts.append(attrs["src"])
        if tag == "link" and "href" in attrs:
            self.links.append(attrs["href"])
        if "id" in attrs:
            self.ids.append(attrs["id"])
        if tag == "table" and "aria-label" in attrs:
            self.tables.append(attrs["aria-label"])


@pytest.mark.parametrize("window", ["2h", "0 days 02:00:00"])
def test_figures_preserve_missing_ic_counts_and_stored_uncertainty(window):
    evaluation = crafted()
    figures = method_figures(
        evaluation.periods,
        evaluation.summary,
        "spearman",
        evaluation.bar,
        ReportOptions(rolling_window=window, min_periods=2),
    )
    raw, rolling = figures["timeseries"].data
    assert list(raw.y) == [0.2, None, 0.6, -0.2, None]
    assert raw.connectgaps is False
    assert list(rolling.y)[:3] == [None, None, None]
    assert rolling.y[3] == pytest.approx(0.2)
    assert rolling.y[4] is None
    assert list(rolling.customdata) == [1, 1, 1, 2, 1]
    assert list(figures["distribution"].data[0].x) == [0.2, 0.6, -0.2]
    assert figures["monthly"].data[0].z[0][0] == pytest.approx(0.2)
    assert figures["monthly"].data[0].customdata[0][0] == 3
    assert figures["comparison"].data[0].y[0] == 0.2
    assert figures["comparison"].data[0].error_y.array[0] == pytest.approx(0.3)
    assert figures["comparison"].data[0].error_y.arrayminus[0] == pytest.approx(0.3)


def test_rolling_window_uses_elapsed_time_not_row_count():
    evaluation = crafted()
    evaluation.periods.loc[2:, "timestamp"] += pd.Timedelta(days=1)
    figures = method_figures(
        evaluation.periods,
        evaluation.summary,
        "spearman",
        evaluation.bar,
        ReportOptions(rolling_window="2h", min_periods=2),
    )
    assert figures["timeseries"].data[1].y[2] is None
    assert figures["timeseries"].data[1].y[3] == pytest.approx(0.2)


def test_report_is_offline_escaped_and_self_contained():
    html = render_tearsheet(
        crafted(),
        title="<b>Title</b>",
        eyebrow="<i>eyebrow</i>",
        subtitle='<script>alert("subtitle")</script>',
        context={"<k>": "<v>&"},
        footer=["<img src=x onerror=alert(1)>"],
    )
    for raw in ("<b>Title</b>", "<i>eyebrow</i>", 'alert("subtitle")', "<k>", "<v>&", "<img src=x"):
        assert raw not in html
    for escaped in (
        "&lt;b&gt;Title",
        "&lt;script&gt;",
        "&lt;k&gt;",
        "&lt;v&gt;&amp;",
        "&lt;img src=x",
    ):
        assert escaped in html
    assert "0.2" in html and "68.0%" in html
    parser = ReportParser()
    parser.feed(html)
    assert not parser.external_scripts and not parser.links
    assert parser.tables == ["spearman summary", "pearson summary"]
    assert len(parser.ids) == len(set(parser.ids))
    assert "<title>&lt;b&gt;Title&lt;/b&gt; · " in html


def test_header_states_the_window_and_options():
    html = render_tearsheet(crafted(delay=2, min_assets=4), subtitle="my factor")
    assert "2026-01-01 00:00 → 2026-01-01 05:00 · end exclusive · UTC timestamps" in html
    assert "1 bars · delay 2 bars" in html and "4 valid pairs" in html
    assert "my factor" in html and "alphatonic" in html


def test_all_invalid_horizon_renders_diagnostics():
    evaluation = crafted()
    evaluation.periods[["spearman", "pearson"]] = np.nan
    evaluation.periods["status"] = "constant_signal"
    evaluation.summary = pd.DataFrame(
        [
            {"horizon": 1, "method": method, "n_periods": 0, "skipped_periods": 5}
            for method in ("spearman", "pearson")
        ]
    )
    html = render_tearsheet(evaluation)
    assert "No valid IC periods for horizons 1" in html
    assert "constant signal" in html
    figures = method_figures(
        evaluation.periods, evaluation.summary, "spearman", evaluation.bar, ReportOptions()
    )
    assert list(figures["distribution"].data[0].x) == []
    assert list(figures["comparison"].data[0].y) == [None]
    assert figures["monthly"].data[0].z[0][0] is None


def test_empty_evaluations_cannot_be_rendered():
    evaluation = crafted()
    evaluation.periods = evaluation.periods.iloc[:0]
    with pytest.raises(ValueError, match="without evaluation periods"):
        render_tearsheet(evaluation)


@pytest.fixture(scope="module")
def full():
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 25, seed=31)
    return evaluate(factor, prices, horizons=[1, 4], time_series=FAST)


def test_full_report_covers_both_views(full):
    html = full.render_tearsheet()
    assert "Cross-sectional evaluation" in html and "Time-series evaluation" in html
    assert "Monthly TS ICIR" in html and "Rolling TS IC" in html
    assert "1 bar · 1h" in html and "4 bars · 4h" in html
    assert "Score buckets (5)" in html
    assert "Block-bootstrap" in html
    parser = ReportParser()
    parser.feed(html)
    assert not parser.external_scripts
    assert len(parser.ids) == len(set(parser.ids))
    assert parser.tables[:2] == ["spearman summary", "pearson summary"]


def test_modes_select_the_sections(full):
    factor, prices = regular_panel(n_assets=6, n_bars=24 * 25, seed=31)
    cs = evaluate(factor, prices, horizons=[1], mode="cross_sectional").render_tearsheet()
    assert "Cross-sectional evaluation" in cs and "Time-series evaluation" not in cs
    ts = evaluate(factor, prices, horizons=[1], mode="time_series", time_series=FAST)
    html = ts.render_tearsheet()
    assert "Time-series evaluation" in html and "Cross-sectional evaluation" not in html
    assert "spearman summary" not in html


def test_quantile_count_and_irregular_calendar_are_reflected():
    factor, prices = regular_panel(n_assets=12, n_bars=200, freq="B", seed=2)
    result = evaluate(factor, prices, horizons=[1, 5], quantiles=4, time_series=FAST)
    html = result.render_tearsheet()
    assert "Score buckets (4)" in html and "Score bucket of 4" in html
    assert "1 bar · " not in html  # no nominal duration on a business-day calendar


def test_horizon_labels():
    hour = pd.Timedelta(hours=1)
    assert horizon_label(1) == "1 bar" and horizon_label(5) == "5 bars"
    assert horizon_label(1, hour) == "1 bar · 1h"
    assert horizon_label(24, hour) == "24 bars · 1d"
    assert horizon_label(3, pd.Timedelta(minutes=15)) == "3 bars · 45min"
    assert horizon_label(5, pd.Timedelta(days=1)) == "5 bars · 5d"
    assert horizon_label(7, pd.Timedelta(seconds=10)) == "7 bars · 70s"


def test_tearsheet_writes_a_file_or_into_a_directory(full, tmp_path):
    path = full.tearsheet(tmp_path / "nested" / "report.html", title="Mine")
    assert path == tmp_path / "nested" / "report.html"
    assert "<title>Mine" in path.read_text(encoding="utf-8")
    inside = full.tearsheet(tmp_path)
    assert inside == tmp_path / "tearsheet.html" and inside.is_file()


def test_loaded_evaluations_render_the_same_report(full, tmp_path):
    full.save(tmp_path)
    loaded = Evaluation.load(tmp_path)
    options = ReportOptions(rolling_window="3D", min_periods=2)
    first = full.render_tearsheet(options=options)
    second = loaded.render_tearsheet(options=options)
    # Only the generation time differs.
    strip = lambda text: "\n".join(line for line in text.splitlines() if "Generated" not in line)  # noqa: E731
    assert strip(first) == strip(second)


def test_a_helpful_error_without_the_reporting_extra(monkeypatch):
    for name in [n for n in sys.modules if n.startswith(("alphatonic.report", "plotly"))]:
        monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "plotly", None)
    with pytest.raises(ImportError, match=r"alphatonic\[report\]"):
        importlib.import_module("alphatonic.report")
