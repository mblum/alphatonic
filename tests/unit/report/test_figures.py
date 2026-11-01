import numpy as np
import pandas as pd

from alphatonic import ReportOptions
from alphatonic.report.figures import (
    counts,
    horizon_label,
    method_figures,
    milliseconds,
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
