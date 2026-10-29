import re

import pytest

from alphatonic import evaluate
from alphatonic.report.page import PICO, stylesheet
from conftest import regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 0, "rolling_window": "5D"}


@pytest.fixture(scope="module")
def page():
    factor, prices = regular_panel(n_assets=8, n_bars=24 * 20, seed=11)
    result = evaluate(factor, prices, horizons=[1, 4], time_series=FAST)
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
