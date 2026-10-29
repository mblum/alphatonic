import json
import re

import pandas as pd
import pytest

from alphatonic import Study, evaluate
from alphatonic.config import ReportOptions
from alphatonic.report.board import render_board
from alphatonic.report.figures import (
    DARK,
    coverage_figures,
    dark_theme,
    method_figures,
    quantile_figure,
)
from alphatonic.report.page import PICO, stylesheet
from alphatonic.report.ts_figures import horizon_figures
from conftest import regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 0, "rolling_window": "5D"}
COLOUR = re.compile(r"#[0-9a-fA-F]{6}|rgba?\([^)]*\)")
TRANSPARENT = "rgba(0,0,0,0)"


@pytest.fixture(scope="module")
def result():
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 20, seed=11)
    return evaluate(factor, prices, horizons=[1, 4], time_series=FAST)


@pytest.fixture(scope="module")
def page(result):
    return result.render_tearsheet(
        title="<b>Momentum</b>",
        subtitle="window=20",
        context={"Universe": "<i>eight</i> assets"},
        footer=["<script>alert(1)</script>"],
    )


def test_the_page_carries_its_stylesheet_and_needs_no_network(page):
    assert "Pico CSS ✨ v2.1.1" in page and "alphatonic: additions" in page
    assert "<link" not in page
    assert not re.search(r"<script[^>]+src=", page)
    assert stylesheet().startswith("@charset") and PICO.endswith(".min.css")


def test_every_link_inside_the_page_has_a_target(page):
    targets = set(re.findall(r'href="#([^"]+)"', page))
    identifiers = set(re.findall(r'\sid="([^"]+)"', page))

    assert targets and targets <= identifiers, targets - identifiers


def test_caller_text_is_shown_literally(page):
    assert "&lt;b&gt;Momentum&lt;/b&gt;" in page and "<b>Momentum</b>" not in page
    assert "&lt;i&gt;eight&lt;/i&gt; assets" in page
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in page


def test_the_glance_shows_each_horizons_estimates_with_their_intervals(page):
    glance = page[page.index('id="at-a-glance"') : page.index('id="cross-section"')]

    assert "1 bar · 1h" in glance and "4 bars · 4h" in glance
    # Two analyses per horizon, each mean with its interval and no reading of it.
    assert glance.count("95% CI ") == 4
    assert "CI above 0" not in page and "CI includes 0" not in page


def test_the_bar_names_the_tool_and_no_label_sits_above_the_title(page):
    assert '<li class="brand">alphatonic</li>' in page
    assert 'class="eyebrow"' not in page


def test_each_horizon_has_a_tab_and_only_the_first_is_shown(page):
    tabs = re.findall(r'role="tab" id="ts-tab-h(\d+)"[^>]*aria-selected="(\w+)"', page)
    panels = re.findall(r'role="tabpanel" id="timing-h(\d+)"[^>]*?(hidden)?>', page)

    assert tabs == [("1", "true"), ("4", "false")]
    assert panels == [("1", ""), ("4", "hidden")]


def test_only_columns_of_numbers_align_right(page):
    assert '<th scope="col">Asset</th>' in page
    assert '<th scope="col" class="number">Usable pairs</th>' in page
    assert '<th scope="col" class="number">Spearman IC</th>' in page
    assert '<th scope="col">95% confidence interval</th>' in page
    assert '<th scope="col">Sample status</th>' in page


def test_every_right_aligned_column_shows_the_same_decimals_in_each_row(page):
    checked = 0
    for html in re.findall(r"<table aria-label=[^>]*>(.*?)</table>", page, flags=re.S):
        head, body = html.split("</thead>")
        numeric = [
            i
            for i, attrs in enumerate(re.findall(r"<th scope=\"col\"([^>]*)>", head))
            if "number" in attrs
        ]
        rows = [
            re.findall(r"<td[^>]*>(.*?)</td>", row) for row in re.findall(r"<tr>(.*?)</tr>", body)
        ]
        for i in numeric:
            texts = {row[i] for row in rows} - {"—"}
            places = {re.fullmatch(r"-?[\d,]+(?:\.(\d+))?%?", text) for text in texts}
            assert None not in places, texts
            assert len({len(match.group(1) or "") for match in places}) <= 1, texts
            checked += 1

    assert checked > 20


def test_the_study_design_link_returns_to_the_top_of_the_page(page):
    assert '<a href="#top" data-section="study-design">Study design</a>' in page
    assert '<header id="top">' in page
    assert page.index('id="top"') < page.index("<h1>") < page.index('id="study-design"')


def _colours(value, found=None):
    """Collect every colour string of a figure, leaving out Plotly's template."""
    found = set() if found is None else found
    if isinstance(value, str) and COLOUR.fullmatch(value):
        found.add(value)
    elif isinstance(value, dict):
        for key, item in value.items():
            if key != "template":
                _colours(item, found)
    elif isinstance(value, list | tuple):
        for item in value:
            _colours(item, found)
    return found


def test_both_pages_follow_the_system_theme_and_print_light(page, tmp_path):
    study = Study(tmp_path / "study", name="demo")
    for html in (page, render_board(study)):
        assert not re.search(r"<html[^>]*data-theme", html)
        assert "beforeprint" in html and "dataset.theme = 'light'" in html


def test_the_charts_are_redrawn_for_a_dark_system(page):
    assert "matchMedia('(prefers-color-scheme: dark)')" in page
    assert all(f'"{colour}"' in page for colour in DARK.values())
    # Plotly's dark template travels with the page, once.
    assert (
        page.count('"paper_bgcolor": "rgb(17,17,17)"')
        + page.count('"paper_bgcolor":"rgb(17,17,17)"')
        == 1
    )
    assert json.dumps(dark_theme())


def test_every_colour_in_a_chart_has_a_dark_counterpart(result):
    periods = result.periods.copy()
    periods["timestamp"] = pd.to_datetime(periods.timestamp, utc=True)
    periods = periods.sort_values(["horizon", "timestamp"])
    figures = [
        *method_figures(periods, "spearman", result.bar, ReportOptions()).values(),
        *coverage_figures(periods, result.bar).values(),
        quantile_figure(result.quantiles, unit="Timestamps", quantiles=5),
        quantile_figure(result.time_series.quantiles, unit="Assets", quantiles=5),
        *(fig for item in horizon_figures(result.time_series) for fig in item["figures"].values()),
    ]

    used = set().union(*(_colours(fig.to_plotly_json()) for fig in figures))

    assert len(figures) > 8 and used > {TRANSPARENT}
    assert used - {TRANSPARENT} <= set(DARK), used - {TRANSPARENT} - set(DARK)


def test_the_rolling_chart_shows_the_asset_chosen_in_a_menu(page, result):
    for horizon in (1, 4):
        menu = re.search(
            rf'<select data-chart="ts-h{horizon}-rolling">(.*?)</select>', page, flags=re.S
        )
        assert menu, horizon
        assert re.findall(r'<option value="(\d+)">(A\d+)</option>', menu.group(1)) == [
            (str(i), f"A{i}") for i in range(8)
        ]
    # Plotly's own menu highlights with a colour that no option changes, so it would not suit a
    # dark page.
    rolling = horizon_figures(result.time_series)[0]["figures"]["rolling"]
    assert not rolling.layout.updatemenus
