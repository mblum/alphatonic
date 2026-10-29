# Read a tearsheet

A tearsheet is a single HTML file with interactive charts and tables. Install the report extra using
the [installation command](../index.md#install), then write a report:

```python
from alphatonic import ReportOptions, evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, seed=2)
result = evaluate(factor, prices, horizons=[1, 5])
result.tearsheet(
    "report.html",
    title="Demo signal",
    subtitle="Simulated business-day prices and scores",
    context={"Universe": "30 synthetic assets", "Data": "demo"},
    options=ReportOptions(rolling_window="30D", min_periods=5),
)
```

Open `report.html` in a browser. It works offline and needs no server. The report uses the result
tables without rerunning inference. `result.render_tearsheet(...)` returns the HTML as a string
instead. Supplied text is escaped and shown literally.

## 1. Check the study design

Confirm the UTC evaluation window, horizons, delay and return targets at the top of the page. The
window end is exclusive. Horizons count price rows; chart windows such as `"30D"` count calendar
time. Context fields are facts supplied by the caller, not checks performed by the library.

## 2. Read the overview

**At a glance** shows both analyses at every configured horizon:

- **Mean Spearman rank IC** measures association. Read its 95% confidence interval alongside
  the estimate. An interval excluding zero does not account for other signals you tried.
- **Quantile spread** is the highest score bucket's mean target minus the lowest bucket's.
  Raw returns appear in basis points; volatility-scaled returns appear in estimated-volatility
  units. These are sample summaries, not portfolio returns after costs.

Cross-sectional mean IC averages timestamps. Time-series mean IC averages eligible assets. The two
means describe different samples and answer different questions.

## 3. Check coverage before comparing results

In each analysis, read the sample rows of **Metrics by horizon**. Open **Coverage** and
**Sample status** to see which observations were excluded. A result based on a small part of
the sample may not represent the whole period or universe.

A dash means unavailable. **Sample status** explains missing correlations; **Inference status**
explains missing intervals. Missing final labels are expected when a horizon extends past the
window. See [troubleshooting](troubleshooting.md) for each status.

## 4. Inspect the cross-section

The quantile chart orders buckets from lowest to highest score. Look for a pattern across buckets,
rather than relying only on the top-minus-bottom spread. Ties stay together and can leave buckets
empty.

Compare Spearman and Pearson in the metric table. Then open **Monthly mean IC** and **IC over time**
to see whether the average hides changes in direction. The rolling line uses
`ReportOptions.rolling_window` and `min_periods`; these affect display only.

## 5. Inspect each asset over time

Under **Time series**, select a horizon and open the asset, monthly and rolling diagnostics. The
mean gives eligible assets equal weight. The middle half of asset ICs describes differences between
assets; it is not a confidence interval for the mean.

Check the bootstrap status if an interval is missing. The default monthly and rolling sample
requirements often exclude daily data; [configure the windows](configure-evaluation.md) if needed.
Monthly time-series IC uses only labels ending inside that month. Cross-sectional monthly IC instead
averages timestamp-level correlations.

Read cosine's **timing** and **static** components together. A positive cosine can come from an
average long position in a rising asset, without successful timing. The **long fraction** is the
share of usable observations with positive scores. See [targets and
scaling](../explanation/targets-and-scaling.md) for interpretation.

## 6. Inspect signal persistence

**Persistence by lag** shows rank persistence, bucket entry fractions, normalised score changes
and sign/zero transitions. Check the contributing counts below each value. The expandable asset,
timestamp and bucket tables show up to 200 rows each; use the result tables for all rows. These
measures describe score changes, not trades or costs. See [measure signal
persistence](measure-persistence.md).

## Navigate and share

Use the section links at the top and arrow keys within horizon tabs. Wide tables and charts scroll
horizontally on small screens. Printing includes all tabs and diagnostics. Share the HTML file
itself; its chart code and styles are included.

The **Methods and interpretation** section defines the report's metrics. For fields absent from the
report, including HAC lag counts and p-values, use the [result tables](../reference/results.md). The
[report design](../explanation/report-design.md) explains the choice of panels.
