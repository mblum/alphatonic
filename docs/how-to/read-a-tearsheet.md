# Read a tearsheet

`result.tearsheet("report.html")` writes one HTML file. Plotly's JavaScript is embedded once,
so the report opens offline in any browser, without a notebook or server. It needs the `report`
extra (`pip install "alphatonic[report]"`). Everything in it is drawn from the result's tables; nothing
is recomputed, and missing values stay missing.

```python
from alphatonic import ReportOptions, evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, seed=2)
result = evaluate(factor, prices, horizons=[1, 5])
result.tearsheet(
    "report.html",
    title="Momentum 20",  # page heading
    subtitle="20-day return, US large caps",  # shown under it
    context={"Universe": "30 synthetic assets", "Data": "demo"},
    footer=["Prices are adjusted close."],
    options=ReportOptions(rolling_window="30D", min_periods=5),
)
```

All text you supply is escaped, so a factor name containing HTML or markup is shown literally.
`result.render_tearsheet(...)` returns the same document as a string.

## Cross-sectional section

The report opens with Spearman IC; expand Pearson IC for the linear association view. Each
method includes:

- **Summary by horizon:** mean IC, its 95% interval, standard deviation, ICIR, positive
  fraction, valid and skipped periods, pair coverage and the HAC lag count, standard error,
  z-statistic and p-value.
- **IC by horizon:** mean IC with the Newey–West 95% interval.
- **IC through time:** the IC at each timestamp and a rolling mean over `ReportOptions.rolling_window`
  that needs `min_periods` valid observations. Missing IC stays missing, including in the rolling
  line, so smoothing cannot hide gaps.
- **Monthly stability:** a heatmap of calendar-month mean IC with period counts on hover.
- **IC distribution** and **IC dependence** (autocorrelation of IC, which tells you whether
  more HAC lags might be warranted).

The cross-sectional signal response chart shows the mean forward return of each score bucket
(5 by default, `quantiles=` to change), with equal timestamp weights. Ties stay together and empty
buckets stay empty. The buckets are formed retrospectively from the sample: they are not
thresholds you could have traded.

## Time-series section

When the mode includes the time-series view, the report adds a summary by horizon (mean asset IC,
median, quartiles, positive assets, bootstrap interval, monthly ICIR and its status), an
asset-by-horizon heatmap, and for each horizon: each asset's IC with its interval, a monthly
heatmap with eligible-asset counts, a rolling-IC chart with an asset selector, and tables with
the sample size, coverage, exclusions and score autocorrelation behind every number.

## Diagnostics

Shared diagnostics show available, scored and paired assets over time, pair coverage, and the
count of each evaluation status. Start here when something looks wrong.

## How to read it

1. Check **status, pair counts and coverage** for each horizon before looking at any IC.
2. Compare Spearman and Pearson. A large gap means outliers or a nonlinear relation.
3. Inspect **stability through time**: a positive mean built from two good months is not a
   signal.
4. Check how many assets support the time-series summary.
5. Remember that a blank cell is an unavailable statistic, never a zero correlation.

The definitions and limitations are in the [methodology](../explanation/methodology.md); the
[troubleshooting](troubleshooting.md) page explains every status.
