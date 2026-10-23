"""The evaluation entry point and its result object."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from alphatonic.config import EvaluationConfig, ReportOptions
from alphatonic.cross_section import cross_sectional_ic
from alphatonic.inputs import prepare
from alphatonic.progress import ProgressFactory, silent
from alphatonic.returns import forward_returns
from alphatonic.time_series import TimeSeriesEvaluation, evaluate_time_series


@dataclass
class Evaluation:
    """The result of [`evaluate`][alphatonic.evaluate]: tables, not conclusions.

    Statistics that cannot be computed are `NaN`, never zero, and every row records why in its
    `status`. The results reference documents each column.
    """

    config: EvaluationConfig
    """The options the evaluation ran with."""

    start: pd.Timestamp
    """Inclusive start of the evaluation window (UTC)."""

    end: pd.Timestamp
    """Exclusive end of the evaluation window (UTC)."""

    bar: pd.Timedelta | None
    """Spacing of the bar grid if perfectly regular, otherwise `None`."""

    periods: pd.DataFrame
    """Cross-sectional IC per timestamp and horizon, with counts, coverage and a status."""

    summary: pd.DataFrame
    """Cross-sectional summary per horizon and method: mean, HAC inference, ICIR, counts."""

    quantiles: pd.DataFrame
    """Cross-sectional mean forward return per score bucket, timestamp and horizon."""

    time_series: TimeSeriesEvaluation | None = None
    """Time-series results, or `None` when the mode is `cross_sectional`."""

    forward_returns: dict[int, pd.DataFrame] = field(default_factory=dict, repr=False)
    """The labels by horizon. Empty after [`load`][alphatonic.Evaluation.load]."""

    def __repr__(self) -> str:
        """Describe the evaluation without printing its tables."""
        horizons = ", ".join(map(str, self.config.horizons))
        return (
            f"Evaluation(mode={self.config.mode!r}, horizons=[{horizons}], "
            f"window=[{self.start:%Y-%m-%d %H:%M}, {self.end:%Y-%m-%d %H:%M}), "
            f"time_series={'yes' if self.time_series is not None else 'no'})"
        )

    def ic(self, method: str = "spearman") -> pd.DataFrame:
        """Return the cross-sectional IC as a table of timestamps by horizon.

        Args:
            method: `spearman` (rank IC) or `pearson`.

        Returns:
            One column per horizon (in bars) and one row per timestamp; `NaN` where the IC is
            undefined. This is the layout of alphalens' `factor_information_coefficient`.
        """
        if method not in ("spearman", "pearson"):
            raise ValueError(f"method must be 'spearman' or 'pearson', not {method!r}")
        table = self.periods.pivot(index="timestamp", columns="horizon", values=method)
        return table.reindex(columns=list(self.config.horizons))

    def monthly_ic(self) -> pd.DataFrame:
        """Return the mean and count of cross-sectional IC in each UTC calendar month."""
        return (
            self.periods.set_index("timestamp")
            .groupby(["horizon", pd.Grouper(freq="MS")])[["spearman", "pearson"]]
            .agg(["mean", "count"])
        )

    def metrics(self) -> dict[str, float]:
        """Flatten the summaries into finite scalars, named `<cs|ts>.h<horizon>.<method>.<stat>`.

        Undefined statistics are omitted. The flat form suits parameter sweeps and experiment
        trackers. Cross-sectional metrics are absent in `time_series` mode.
        """
        values: dict[str, float] = {}
        if self.config.mode != "time_series":
            for row in self.summary.to_dict(orient="records"):
                prefix = f"cs.h{row['horizon']}.{row['method']}"
                for name, value in row.items():
                    if name not in {"horizon", "method"} and np.isfinite(value):
                        values[f"{prefix}.{name}"] = float(value)
        if self.time_series is not None:
            for row in self.time_series.summary.to_dict("records"):
                prefix = f"ts.h{row['horizon']}.{row['method']}"
                for name, value in row.items():
                    if (
                        name != "horizon"
                        and isinstance(value, int | float | np.integer | np.floating)
                        and not isinstance(value, bool)
                        and np.isfinite(value)
                    ):
                        values[f"{prefix}.{name}"] = float(value)
        return values

    def save(self, directory: str | Path) -> Path:
        """Write the tables as CSV files and the configuration as JSON.

        Forward returns are not saved; they follow from the prices and the configuration.
        Existing files of the same names are replaced.

        Returns:
            The directory.
        """
        from alphatonic.persistence import save

        return save(self, Path(directory))

    @classmethod
    def load(cls, directory: str | Path, config: EvaluationConfig | None = None) -> Evaluation:
        """Read an evaluation written by [`save`][alphatonic.Evaluation.save].

        Args:
            directory: The directory `save` wrote.
            config: The configuration to attach if the directory has no `evaluation.json`, for
                example one written by another tool.

        Raises:
            FileNotFoundError: If the tables are missing.
            ValueError: If there is no configuration to attach.
        """
        from alphatonic.persistence import load

        return load(Path(directory), config)

    def render_tearsheet(
        self,
        *,
        options: ReportOptions | None = None,
        title: str = "Factor tearsheet",
        eyebrow: str | None = "alphatonic · information coefficient",
        subtitle: str | None = None,
        context: dict[str, str] | None = None,
        footer: list[str] | None = None,
    ) -> str:
        """Render the tearsheet as a standalone HTML document. Needs `alphatonic[report]`.

        Args:
            options: Display options of the cross-sectional charts.
            title: Page heading.
            eyebrow: Small label above the heading; `None` hides it.
            subtitle: A line under the heading, such as the factor's name.
            context: Extra labelled facts shown under the heading, such as the universe.
            footer: Extra lines in the page footer.

        Returns:
            The HTML. Plotly's JavaScript is embedded, so the page works offline.
        """
        from alphatonic.report import render_tearsheet

        return render_tearsheet(
            self,
            options=options,
            title=title,
            eyebrow=eyebrow,
            subtitle=subtitle,
            context=context,
            footer=footer,
        )

    def tearsheet(self, path: str | Path, **options: Any) -> Path:
        """Write the tearsheet to `path` and return it. Needs `alphatonic[report]`.

        Accepts the keyword arguments of `render_tearsheet`. A directory writes
        `tearsheet.html` inside it.
        """
        target = Path(path)
        if target.is_dir():
            target = target / "tearsheet.html"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.render_tearsheet(**options), encoding="utf-8")
        return target


def evaluate(
    factor: pd.DataFrame | pd.Series,
    prices: pd.DataFrame,
    config: EvaluationConfig | None = None,
    *,
    progress: ProgressFactory = silent,
    **options: Any,
) -> Evaluation:
    """Evaluate how well `factor` predicts forward returns.

    Rows of `prices` are the bars of the evaluation: horizons and delays count rows, so a daily
    table of trading days, an hourly 24/7 grid and a table of rebalance dates all work, and a
    missing price is `NaN`. A score at a timestamp must be computable from information available
    at that timestamp's price; the label is the return from `delay` bars later over `horizon`
    bars. Timestamps are read as UTC when they are naive.

    Options come either as an [`EvaluationConfig`][alphatonic.EvaluationConfig] or as keyword
    arguments with the names of its fields, not both.

    Args:
        factor: Scores, larger meaning a higher expected return. A DataFrame with one row per
            timestamp and one column per asset, or a Series indexed by `(timestamp, asset)`.
            `NaN` (and infinity) mean no score.
        prices: Prices with one row per bar and one column per asset.
        config: The evaluation options.
        progress: A progress display; see `alphatonic.progress`. Silent by default.
        **options: Fields of `EvaluationConfig`, such as `horizons=[1, 5, 21]`.

    Returns:
        The [`Evaluation`][alphatonic.Evaluation] tables.

    Raises:
        TypeError: If an input has the wrong type or index.
        ValueError: If an input is malformed or the options are invalid.

    Example:
        >>> from alphatonic import evaluate
        >>> from alphatonic.demo import synthetic_market
        >>> factor, prices = synthetic_market(n_assets=20, n_bars=300, seed=1)
        >>> result = evaluate(factor, prices, horizons=[1, 5], time_series={"bootstrap_samples": 0})
        >>> result.summary.loc[result.summary.method == "spearman", "horizon"].tolist()
        [1, 5]
    """
    if config is not None and options:
        raise TypeError("pass either a config or keyword options, not both")
    config = config or EvaluationConfig(**options)
    panel = prepare(factor, prices, config)
    labels = {
        horizon: forward_returns(panel.prices, horizon, config.delay) for horizon in config.horizons
    }
    periods, summary, quantiles = cross_sectional_ic(
        panel.factor, labels, panel.prices, config, progress
    )
    time_series = (
        evaluate_time_series(
            panel.factor, labels, config, panel.factor.index, panel.start, panel.end, progress
        )
        if config.mode != "cross_sectional"
        else None
    )
    return Evaluation(
        config=config,
        start=panel.start,
        end=panel.end,
        bar=panel.bar,
        periods=periods,
        summary=summary,
        quantiles=quantiles,
        time_series=time_series,
        forward_returns=labels,
    )
