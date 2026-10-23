# Save and reload results

An `Evaluation` is a set of tables. Save it to a directory of CSV files, reload it later, and
rebuild the tearsheet with different display options, all without recomputing a statistic.

```python
from alphatonic import Evaluation, ReportOptions, evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, seed=2)
result = evaluate(factor, prices, horizons=[1, 5])

result.save("runs/momentum-20")

later = Evaluation.load("runs/momentum-20")
later.tearsheet("report.html", options=ReportOptions(rolling_window="14D"))
```

`load` returns an `Evaluation` equal to the saved one, except that `forward_returns` is empty:
labels follow from the prices and the configuration, so they are not stored. Loading is exact;
floating-point values round-trip bit for bit.

## What is written

| File | Contents |
| --- | --- |
| `evaluation.json` | The configuration, resolved window, bar spacing and format version. |
| `ic_by_timestamp.csv` | `periods`: cross-sectional correlations, counts, coverage and status. |
| `ic_summary.csv` | `summary`: cross-sectional statistics per horizon and method. |
| `ic_monthly.csv` | `monthly_ic()`: monthly mean and count of cross-sectional IC. |
| `cs_quantiles.csv` | `quantiles`: mean return per score bucket. |
| `ts_assets.csv`, `ts_monthly.csv`, `ts_rolling.csv`, `ts_summary.csv`, `ts_quantiles.csv` | The time-series tables; absent in `cross_sectional` mode. |

CSVs keep missing values as empty cells. Column definitions are in
[results and metrics](../reference/results.md).

## Tables from another tool

If the directory has no `evaluation.json`, pass the configuration the tables came from:

<!-- notest -->
```python
from alphatonic import EvaluationConfig

reloaded = Evaluation.load("old-run", EvaluationConfig(horizons=[1, 5], mode="both"))
```

A configuration you pass takes precedence over a stored one. A directory written by a newer,
incompatible format raises an error that names the version.

## Keep experiments reproducible

A saved evaluation records the settings, not the data. To reproduce a number later keep the
inputs fixed: store the factor and price tables you evaluated (for example as Parquet) next to
the results, or a hash of them, and the version of alphatonic (`evaluation.json` records it).
Results are deterministic for fixed inputs and `time_series.seed`.
