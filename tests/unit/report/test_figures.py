import numpy as np
import pandas as pd

from alphatonic import ReportOptions
from alphatonic.report.figures import (
    counts,
    horizon_label,
    method_figures,
    milliseconds,
    quantile_figure,
    span,
    values,
)


def test_chart_conversions_units_and_missingness():
    assert values([1.23456789, np.nan, np.inf]) == [1.234568, None, None]
    assert counts([2, 0]) == [2, 0]
    assert milliseconds(pd.date_range("1970-01-01", periods=2, freq="s", tz="UTC")) == [0, 1000]
    assert "bar" in horizon_label(3, None)
    assert span(3600) == "1h"


def test_rolling_chart_gap_masking_and_monthly_counts(result):
    result.periods.loc[2, "spearman"] = np.nan
    plots = method_figures(result.periods, "spearman", result.bar, ReportOptions(min_periods=1))
    panel = plots["timeseries"]["panels"][0]
    assert panel["series"][0]["y"][2] is None
    assert panel["series"][1]["y"][2] is None
    assert len(panel["x"]) == len(panel["series"][0]["y"])
    assert (
        plots["monthly"]["counts"][0][0]
        == result.periods.loc[
            (result.periods.horizon == 1) & (result.periods.timestamp.dt.month == 1), "spearman"
        ].count()
    )


def test_quantile_chart_gives_each_horizon_its_own_panel_and_scale():
    # Hand-written bucket means: the 480-bar returns are about a hundred times the 1-bar ones.
    frame = pd.DataFrame(
        {
            "horizon": [1, 1, 1, 1, 480, 480, 480, 480],
            "timestamp": [0, 0, 1, 1, 0, 0, 1, 1],
            "quantile": [1, 2, 1, 2, 1, 2, 1, 2],
            "mean_return": [-0.0002, 0.0004, 0.0, np.nan, 0.01, 0.08, 0.03, 0.04],
            "n_pairs": [5, 5, 5, 0, 5, 5, 5, 5],
        }
    )
    spec = quantile_figure(frame, unit="Timestamps", quantiles=3)
    assert [panel["title"] for panel in spec["panels"]] == ["1 bar", "480 bars"]
    assert spec["columns"] == 2
    short, long = (panel["series"] for panel in spec["panels"])
    assert len(short) == len(long) == 1
    # Basis points, averaged with equal weight per timestamp; an empty bucket is a gap, not zero.
    assert short[0]["y"] == [-1.0, 4.0, None]
    assert long[0]["y"] == [200.0, 600.0, None]
    assert short[0]["columns"][0]["values"] == [10, 5, 0]
    assert short[0]["columns"][1]["values"] == [2, 1, 0]
    # No panel fixes a y domain, so each is drawn to the range of its own horizon.
    assert all("domain" not in panel["y"] for panel in spec["panels"])
