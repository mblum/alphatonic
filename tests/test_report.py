import json
import re

import numpy as np
import pandas as pd
import pytest

from alphatonic import Study, evaluate
from alphatonic.config import ReportOptions
from alphatonic.report.board import render_board
from alphatonic.report.figures import (
    STATUSES,
    coverage_figures,
    method_figures,
    milliseconds,
    quantile_figure,
    status_slots,
    values,
)
from alphatonic.report.page import PICO, environment, static, stylesheet
from alphatonic.report.ts_figures import confidence_plot, horizon_figures
from conftest import regular_panel

FAST = {"min_pairs": 20, "min_horizons": 2, "bootstrap_samples": 0, "rolling_window": "5D"}


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


def _specs(page):
    """Read the chart specifications of a page, refusing NaN and infinities as JavaScript does."""
    blob = re.search(r'<script type="application/json" id="chart-data">(.*?)</script>', page, re.S)
    assert blob

    def refuse(constant):
        raise AssertionError(f"{constant} is not JSON")

    return json.loads(blob.group(1), parse_constant=refuse)


def test_both_pages_follow_the_system_theme_and_print_light(page, tmp_path):
    study = Study(tmp_path / "study", name="demo")
    for html in (page, render_board(study)):
        assert not re.search(r"<html[^>]*data-theme", html)
        assert "beforeprint" in html and "dataset.theme = 'light'" in html


def test_the_page_draws_its_charts_with_the_libraries_it_carries(page):
    assert "@observablehq/plot v0.6.17" in page and "https://d3js.org v7.9.0" in page
    assert "plotly" not in page.lower()
    assert "charts drawn with Observable Plot and d3 (ISC)" in page


def test_every_chart_has_a_place_on_the_page_and_a_kind_the_script_draws(page):
    places = re.findall(r'<div class="host" id="([^"]+)" data-chart="\1"></div>', page)
    specs = _specs(page)
    drawn = re.search(r"const kinds = \{([^}]*)\};", static("alphatonic.js"))
    assert drawn

    assert len(places) == len(set(places)) > 8
    assert set(places) == set(specs)
    # No spec the script cannot draw, and no renderer that nothing uses.
    assert {spec["kind"] for spec in specs.values()} == set(re.findall(r"\w+", drawn.group(1)))


def test_chart_data_refuses_nan_instead_of_writing_invalid_json():
    assert environment().policies["json.dumps_kwargs"]["allow_nan"] is False
    with pytest.raises(ValueError):
        environment().from_string("{{ x | tojson }}").render(x=float("nan"))


def test_the_rolling_chart_shows_the_asset_chosen_in_a_menu(page, result):
    for horizon in (1, 4):
        menu = re.search(
            rf'<select data-chart="ts-h{horizon}-rolling">(.*?)</select>', page, flags=re.S
        )
        assert menu, horizon
        assert re.findall(r'<option value="(\d+)">(A\d+)</option>', menu.group(1)) == [
            (str(i), f"A{i}") for i in range(8)
        ]
    spec = horizon_figures(result.time_series)[0]["figures"]["rolling"]
    assert [asset["name"] for asset in spec["assets"]] == [f"A{i}" for i in range(8)]
    for asset in spec["assets"]:
        assert len(asset["x"]) == len(asset["y"]) > 0
        assert all(len(column["values"]) == len(asset["x"]) for column in asset["columns"])


def test_timestamps_are_written_as_utc_milliseconds_whatever_the_pandas_unit():
    expected = [1704067200000]
    assert milliseconds(pd.DatetimeIndex(["2024-01-01"])) == expected
    assert milliseconds(pd.DatetimeIndex(["2024-01-01T01:00:00+01:00"])) == expected
    assert milliseconds(pd.DatetimeIndex(["2024-01-01"]).as_unit("s")) == expected
    assert milliseconds(pd.Series(pd.to_datetime(["2024-01-01"], utc=True))) == expected


def test_a_missing_value_is_null_and_the_rest_is_rounded():
    assert values([0.123456789, np.nan, np.inf, -np.inf, 1]) == [0.123457, None, None, None, 1.0]


def _periods(spearman):
    index = pd.date_range("2024-01-01", periods=len(spearman), freq="D", tz="UTC")
    return pd.DataFrame({"horizon": 1, "timestamp": index, "spearman": spearman})


def test_a_month_without_a_valid_ic_is_empty_in_the_heatmap_never_zero():
    spearman = [0.1] * 31 + [np.nan] * 29 + [-0.2] * 31

    spec = method_figures(_periods(spearman), "spearman", None, ReportOptions())["monthly"]

    assert spec["months"] == ["2024-01", "2024-02", "2024-03"]
    assert spec["z"] == [[0.1, None, -0.2]]
    assert spec["counts"] == [[31, 0, 31]]


def test_the_rolling_mean_leaves_a_gap_where_the_ic_is_missing():
    spearman = [0.1, 0.2, np.nan, np.nan, 0.3, 0.4, 0.5, 0.6]
    options = ReportOptions(rolling_window="3D", min_periods=1)

    panel = method_figures(_periods(spearman), "spearman", None, options)["timeseries"]["panels"][0]
    raw, mean = panel["series"]

    assert raw["y"][2:4] == [None, None] and mean["y"][2:4] == [None, None]
    assert all(v is not None for v in mean["y"][:2] + mean["y"][4:])
    assert panel["empty"] is None and len(panel["x"]) == len(raw["y"]) == len(mean["y"])


def test_a_panel_without_any_ic_says_so_instead_of_drawing_zeros():
    panel = method_figures(_periods([np.nan] * 5), "spearman", None, ReportOptions())["timeseries"][
        "panels"
    ][0]

    assert panel["empty"] == "No valid cross-sectional observations"
    assert panel["series"][0]["y"] == [None] * 5


def test_quantile_returns_are_in_basis_points_or_in_sigma_and_an_empty_bucket_is_a_gap():
    frame = pd.DataFrame(
        {
            "horizon": 1,
            "quantile": [1, 3],
            "mean_return": [-0.0005, 0.0012],
            "n_pairs": [40, 44],
        }
    )

    bps = quantile_figure(frame, unit="Timestamps", quantiles=3)
    sigma = quantile_figure(frame, unit="Timestamps", quantiles=3, vol_scaled=True)

    series = bps["panels"][0]["series"][0]
    assert series["y"] == [-5.0, None, 12.0] and bps["panels"][0]["y"]["unit"] == " bps"
    assert sigma["panels"][0]["series"][0]["y"] == [-0.0005, None, 0.0012]
    assert bps["x"]["ticks"] == [1, 2, 3]
    # The number of pairs behind an empty bucket is a count, so it is zero.
    assert series["columns"][0]["values"] == [40, 0, 44]


def test_a_status_keeps_its_colour_whichever_other_statuses_are_present():
    assert status_slots(["valid", "low_coverage"]) == {"valid": 1, "low_coverage": 5}
    assert status_slots(list(STATUSES))["constant_returns"] == 3
    assert status_slots(["valid", "zebra", "aardvark"]) == {"valid": 1, "zebra": 7, "aardvark": 6}


def test_the_status_chart_counts_every_period_once():
    periods = pd.DataFrame(
        {
            "horizon": [1] * 4 + [4] * 4,
            "timestamp": list(pd.date_range("2024-01-01", periods=4, tz="UTC")) * 2,
            "status": ["valid", "valid", "constant_signal", "valid"] * 2,
            "n_available": 5.0,
            "n_signal": 5.0,
            "n_pairs": 5.0,
            "pair_coverage": 1.0,
        }
    )
    periods.loc[7, "status"] = "low_coverage"

    spec = coverage_figures(periods, None)["statuses"]

    assert spec["categories"] == ["1 bar", "4 bars"]
    series = {item["name"]: item for item in spec["series"]}
    assert [item["name"] for item in spec["series"]] == ["valid", "constant signal", "low coverage"]
    assert series["valid"]["values"] == [3, 2] and series["valid"]["color"] == 1
    assert series["constant signal"]["color"] == 2 and series["low coverage"]["color"] == 5
    assert sum(sum(item["values"]) for item in spec["series"]) == len(periods)


def test_an_asset_without_an_estimate_has_no_marker_and_no_interval():
    frame = pd.DataFrame(
        {
            "ic": [0.05, np.nan],
            "ci95_lower": [-0.02, np.nan],
            "ci95_upper": [0.12, np.nan],
            "n_pairs": [300, 12],
        }
    )

    rows = confidence_plot(frame, ["A", "B"], "ic")["rows"]

    assert rows[0] == {"label": "A", "estimate": 0.05, "lower": -0.02, "upper": 0.12, "pairs": 300}
    assert rows[1] == {"label": "B", "estimate": None, "lower": None, "upper": None, "pairs": 12}
