import numpy as np
import pandas as pd

from alphatonic.report.ts_figures import confidence_plot, heatmap, horizon_figures


def test_intervals_use_stored_bounds_and_heatmap_gaps():
    frame = pd.DataFrame(
        {
            "ic": [0.2, np.nan],
            "ci95_lower": [-0.1, np.nan],
            "ci95_upper": [0.5, np.nan],
            "n_pairs": [10, 0],
        }
    )
    plot = confidence_plot(frame, ["a", "b"], "ic")
    assert plot["rows"] == [
        {"label": "a", "estimate": 0.2, "lower": -0.1, "upper": 0.5, "pairs": 10},
        {"label": "b", "estimate": None, "lower": None, "upper": None, "pairs": 0},
    ]
    frame = pd.DataFrame(
        {
            "month": ["Jan", "Feb", "Jan"],
            "asset": ["a", "a", "b"],
            "ic": [0.2, 0.3, np.nan],
            "n": [3, 4, 0],
        }
    )
    plot = heatmap(frame, "month", "asset", "ic", "n", "IC")
    assert len(plot["z"]) == len(plot["rows"]) == 2
    assert plot["z"][1] == [None, None]


def test_rolling_assets_initial_selection_alphabetical(result):
    plots = horizon_figures(result.time_series)
    for group in plots:
        assert group["rolling_assets"] == sorted(group["rolling_assets"])
        assert group["figures"]["rolling"]["kind"] == "rolling"
