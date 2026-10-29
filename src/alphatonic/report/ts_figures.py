"""Chart specifications for the time-series part of a tearsheet, drawn from stored tables."""

from __future__ import annotations

from typing import cast

import pandas as pd

from alphatonic.report.figures import BLUE, CONTEXT, Spec, counts, milliseconds, values
from alphatonic.time_series import TimeSeriesEvaluation


def confidence_plot(frame: pd.DataFrame, labels: list[str], column: str) -> Spec:
    """Specify a point estimate per label with its bootstrap interval."""
    rows = [
        {"label": label, "estimate": value, "lower": lower, "upper": upper, "pairs": pairs}
        for label, value, lower, upper, pairs in zip(
            labels,
            values(frame[column]),
            values(frame["ci95_lower"]),
            values(frame["ci95_upper"]),
            counts(frame["n_pairs"]),
            strict=True,
        )
    ]
    return {
        "kind": "intervals",
        "label": "Asset Spearman IC with 95% confidence intervals",
        "x": {"label": "Spearman IC", "domain": [-1.05, 1.05]},
        "legend": [
            {"name": "95% confidence interval", "color": CONTEXT, "width": 3},
            {"name": "Spearman IC", "color": BLUE, "shape": "dot"},
        ],
        "rows": rows,
    }


def heatmap(frame: pd.DataFrame, x: str, y: str, z: str, count: str, label: str) -> Spec:
    """Specify `z` by `x` and `y`, with the pair count `count` in the tooltip."""
    matrix = frame.pivot(index=y, columns=x, values=z).sort_index()
    pairs = frame.pivot(index=y, columns=x, values=count).reindex_like(matrix)
    return {
        "kind": "heatmap",
        "label": label,
        "months": [str(v) for v in matrix.columns],
        "rows": [str(v) for v in matrix.index],
        "z": [values(row) for _, row in matrix.iterrows()],
        "counts": [counts(row) for _, row in pairs.iterrows()],
        "tip": {"value": "Spearman IC", "count": "Pairs", "first": "row"},
    }


def horizon_figures(result: TimeSeriesEvaluation) -> list[dict]:
    """Specify the asset and stability drilldowns for the primary rank-correlation view."""
    assets = result.assets.loc[result.assets.method == "spearman"].copy()
    horizons = []
    for horizon, group in assets.groupby("horizon", sort=True):
        group = group.sort_values("asset")
        label = str(int(cast(int, horizon)))
        monthly = result.monthly.loc[
            (result.monthly.method == "spearman") & (result.monthly.horizon == horizon)
        ].copy()
        monthly["month"] = pd.to_datetime(monthly.window_start, utc=True).dt.strftime("%Y-%m")
        eligible = monthly.groupby("month").ic.count()
        breadth: Spec = {
            "kind": "bars",
            "label": f"Monthly eligible assets · {label}",
            "height": 280,
            "categories": eligible.index.tolist(),
            "x": {"label": "UTC calendar month"},
            "y": {"label": "Eligible assets"},
            "series": [{"name": "Eligible assets", "color": BLUE, "values": counts(eligible)}],
        }
        rolling = result.rolling.loc[
            (result.rolling.method == "spearman") & (result.rolling.horizon == horizon)
        ].copy()
        # Alphabetical initial selection, not selected by apparent predictive performance.
        histories = [
            {
                "name": str(asset),
                "x": milliseconds(history.window_end),
                "y": values(history.ic),
                "columns": [
                    {"name": "Pairs", "values": counts(history.n_pairs), "format": "d"},
                    {"name": "Coverage", "values": values(history.pair_coverage), "format": ".1%"},
                    {"name": "Status", "values": [str(status) for status in history.status]},
                ],
            }
            for asset, history in rolling.groupby("asset", sort=True)
        ]
        horizons.append(
            {
                "horizon": int(cast(int, horizon)),
                "assets": group,
                "monthly": monthly,
                # The page shows one of these at a time, chosen in a menu above the chart.
                "rolling_assets": [history["name"] for history in histories],
                "figures": {
                    "assets": confidence_plot(group, group.asset.astype(str).tolist(), "ic"),
                    "monthly": heatmap(
                        monthly, "month", "asset", "ic", "n_pairs", f"Asset monthly IC · {label}"
                    ),
                    "breadth": breadth,
                    "rolling": {
                        "kind": "rolling",
                        "label": f"Asset rolling Spearman IC · {label}",
                        "height": 340,
                        "x": {"type": "utc", "label": "Evaluation window end (UTC, exclusive)"},
                        "y": {
                            "label": "Spearman IC",
                            "domain": [-1.05, 1.05],
                            "format": ".2~f",
                            "tip": ".3f",
                        },
                        "assets": histories,
                    },
                },
            }
        )
    return horizons
