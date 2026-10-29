# Save and reload results

An `Evaluation` is a set of tables. Save it to a directory of compressed CSV files, reload it later,
and rebuild the tearsheet with different display options, all without recomputing a statistic.

```python
from alphatonic import Evaluation, ReportOptions, evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, seed=2)
result = evaluate(factor, prices, horizons=[1, 5])

result.save("runs/momentum-20")

later = Evaluation.load("runs/momentum-20")
assert later.forward_returns == {}
assert later.volatility is None
assert later.persistence is not None
later.tearsheet("report.html", options=ReportOptions(rolling_window="14D"))
```

`load` restores the saved result tables and configuration. It does not restore inputs or
intermediate arrays: `forward_returns` is an empty dictionary and `volatility` is `None`. These are
not needed to rebuild a report. Saved floating-point values round-trip exactly. Use a new directory
for each run: `save` replaces existing result files at the same path. A [study](run-a-study.md)
gives each completed trial its own directory.

## What is written

| File | Contents |
| --- | --- |
| `evaluation.json` | The configuration, resolved window, bar spacing and format version. |
| `ic_by_timestamp.csv.gz` | `periods`: cross-sectional correlations, counts, coverage and status. |
| `ic_summary.csv.gz` | `summary`: cross-sectional statistics per horizon and method. |
| `ic_monthly.csv.gz` | `monthly_ic()`: monthly mean and count of cross-sectional IC. |
| `cs_quantiles.csv.gz` | `quantiles`: mean return per score bucket. |
| `persistence_periods.csv.gz`, `persistence_quantiles.csv.gz`, `persistence_assets.csv.gz`, `persistence_summary.csv.gz` | Score, rank and bucket changes at each configured lag. |
| `ts_assets.csv.gz`, `ts_monthly.csv.gz`, `ts_rolling.csv.gz`, `ts_summary.csv.gz`, `ts_quantiles.csv.gz` | The time-series tables, always written for new evaluations. |

The tables are gzip-compressed CSV, which `pandas.read_csv` reads as it is, and keep missing values
as empty cells. Compression matters because a table has a row for every timestamp: 20 assets of
hourly bars over five years take 22 MB this way and took 158 MB as plain CSV. Column definitions are
in [results and metrics](../reference/results.md).

## Load older results

If an older directory has no `evaluation.json`, pass the configuration used to compute its tables.
The files must still use alphatonic’s expected names and columns:

<!-- notest -->
```python
from alphatonic import EvaluationConfig

reloaded = Evaluation.load("old-run", EvaluationConfig(horizons=[1, 5]))
```

A configuration you pass replaces the stored settings; it does not recompute the tables. Do not use
this argument to change what an existing result means. A directory written by a newer, incompatible
format raises an error that names the version. Directories of format 1, written before the `target`
options existed, load with both targets set to `return`, which is what they were computed with;
their time-series tables have no `cosine` rows. Older configurations with `mode` still load: the
retired setting is ignored and tables are preserved without recomputing missing analyses. Older
cross-sectional-only directories can therefore have `time_series=None`. Formats 1 and 2 have no
persistence tables, so they load with `persistence=None`. Formats 1 to 3 wrote plain `.csv` files
and still load; saving over such a directory replaces them with `.csv.gz` files. Current saves use
format 4.

## Keep experiments reproducible

A saved evaluation records the settings, not the data. To reproduce a number later keep the inputs
fixed: store the factor and price tables you evaluated (for example as Parquet) next to the results,
or a hash of them, and the version of alphatonic (`evaluation.json` records it). Keep all evaluation
settings and dependency versions as well. The bootstrap is deterministic for fixed inputs, settings
and software versions, using `time_series.seed`. A [study](run-a-study.md) records the hash and the
versions with every trial.
