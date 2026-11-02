# Evaluation methodology

This page explains which observations enter an IC and how alphatonic aggregates them across
assets and time. For table columns, see [results and metrics](../reference/results.md). The
defaults named here are those of `EvaluationConfig` and `TimeSeriesOptions`.

## What an IC estimates

An information coefficient (IC) measures association between scores and subsequent targets. The
axis of the calculation determines the question:

| Analysis | Observations in one correlation | Summary weights | Question |
| --- | --- | --- | --- |
| Cross-sectional | Assets at one timestamp | Equal weight per valid timestamp | Do higher-scored assets subsequently have higher targets? |
| Time-series | Bars for one asset | Equal weight per eligible asset | Does an asset have higher targets when its own score is higher? |

These summaries estimate different quantities. A signal can rank assets well without timing any
one asset, or time a common market move without distinguishing assets. Pooling all asset-bar pairs
would mix between-asset differences with within-asset variation; alphatonic does not use that
pooled correlation. Neither IC establishes causality or a tradeable return.

[Spearman (1904)][spearman] introduced rank association; alphatonic computes it as Pearson
correlation of average ranks on the surviving pairs. [Alphalens][alphalens] provides the related
cross-sectional factor-analysis convention. The exact sampling and missingness rules below are
alphatonic's, and need not match another package's defaults.

## Bars and the evaluation window

The rows of the price table are the **bars**. A horizon of `h` is `h` rows. The evaluation window is
`[start, end)` in UTC: scores and their return labels must lie inside it. Prices before `start` may
be used to estimate volatility; prices at or after `end` never enter a label.

Counting rows keeps the calculation free of market-specific calendars: business-day tables,
24/7 hourly grids and irregular rebalance dates follow the same rule. A missing *row* therefore
looks like a shorter gap than a missing *price*. The [input guide](../how-to/prepare-inputs.md#calendars)
explains how to put missing bars on the grid. Calendar-month and rolling-window views use
timestamps to select their samples.

## Forward-return labels

For a score observed at row `t`, horizon `h` and delay `d`, the label is

$$
\text{label}_t = \frac{\text{price}_{t+d+h}}{\text{price}_{t+d}} - 1
$$

The whole path from `t` through `t + d + h` must have prices. A gap never turns an `h`-bar label
into a longer return, and a delisted or suspended asset has no labels across its gap. Labels must
end before `end`, so the final `d + h` bars have none. Non-finite returns (for example from a price
that jumps from `1e-300` to `1e300`) are missing.

## Targets

Each analysis correlates scores with a target derived from the forward-return label. The
[target definitions](targets-and-scaling.md#volatility-scaled-targets) explain raw and
volatility-scaled returns, their defaults and the volatility warmup that can make targets missing.

## Cross-sectional evaluation

At each timestamp and horizon, the finite score/target pairs produce:

- **Spearman IC**, the Pearson correlation of average ranks, ties included. This is the primary
  metric.
- **Pearson IC**, the linear association, useful beside the rank IC.
- Counts of available assets, scored assets and pairs, pair coverage, and a skip reason.

A constant score or target, or fewer than `min_assets` pairs, gives an undefined IC and never zero.
Correlations whose magnitude is below 1e-12 are floating-point noise and are returned as exact zero;
this matters for small cross-sections, where rank correlations take few discrete values and some are
exactly zero. Pair coverage divides valid pairs by assets with a price at the timestamp. It does not
measure coverage against a historical universe.

### Summary statistics { #summary-statistics-and-inference }

Timestamps are weighted equally. Reported: mean, sample standard deviation, positive fraction, and
**ICIR = mean / standard deviation**, without annualisation.

The [Newey–West explanation](inference.md#cross-sectional-mean-neweywest) covers uncertainty
for this mean, including its test, interval, lag count and missing-period handling.

## Time-series evaluation

For each asset and horizon, correlate scores with the time-series target **over time**, with three
methods:

- **Spearman**, ranks recomputed within each paired sample: monotone timing, with magnitudes
  replaced by ranks.
- **Pearson**, linear timing.
- **Cosine**, the uncentred association, including both timing and average exposure. Its
  [definition and timing/static split](targets-and-scaling.md#timing-and-average-exposure)
  explain why a constant non-zero score can still have a defined cosine.

The universe summary reports the equal-asset mean IC (and, for the cosine, the mean timing and
static parts), median, quartiles, positive fraction and number of eligible assets. It does not pool
asset-time observations into one correlation, and the quartiles describe dispersion, not confidence.

**Windows.** The full period, each UTC calendar month, and trailing windows (30 days by default,
sampled daily) are evaluated independently. A bar takes part in a window only if the **label also
ends inside it**: a month never uses a return that settles in the next month. Months that are not
fully inside the evaluation period are `partial_window`. Rolling endpoints fall every `rolling_step`
after `start`, through `end`.

**Eligibility.** A window needs `min_pairs` (100) finite pairs, `min_coverage` (80%) of its
expected bars, and a length of at least `min_horizons` (20) horizons. Expected bars are those whose
label can end inside the window, so the deterministic end-of-window exclusion is not counted as
missing data, but missing prices and scores are. These are sample-size heuristics, not significance
thresholds.

**Monthly TS ICIR** is an asset's mean monthly IC divided by its sample standard deviation,
unannualised. It needs `min_months` (6) valid months and is marked `preliminary` below twelve. The
separately named *universe* ratio first averages the eligible assets' ICs within each month, then
takes mean over standard deviation across months, so the asset set can change between months. No
confidence interval or significance test is claimed for ICIR.

**Rolling IC** is descriptive. It is not used for any ratio or interval, and overlapping
windows are strongly dependent.

### Full-period uncertainty { #block-bootstrap }

Full-period asset estimates and their equal-asset mean have
[paired block-bootstrap intervals](inference.md#time-series-intervals-paired-circular-blocks).

<span id="time-series-tests"></span>
The separate [EWC tests](inference.md#time-series-tests-ewc) assess zero association. Monthly
and rolling estimates remain descriptive; their dispersion is not uncertainty for the full-period IC.

## Quantile response

Score buckets (`quantiles`, default 5) are formed from average ranks within each timestamp
(cross-sectional) or within each eligible asset's full sample (time series), and average each
analysis's target: returns, or vol-scaled returns in multiples of $\hat\sigma \sqrt{h}$. Tied scores share
a bucket, and empty buckets stay missing. In the report, buckets are averaged with equal weight per
timestamp or per asset. They are retrospective: they describe what happened in the sample and are
not trading thresholds.

## Related explanations

<span id="trials-and-the-holdout"></span>
[Trials, selection and the holdout](research-validity.md) explains how the research process
changes the interpretation of an evaluation, including trial counts and chronological boundaries.

<span id="interpretation-and-limitations"></span>
[Dependence and uncertainty](inference.md#assumptions-and-failure-modes) covers inferential
assumptions; [research validity](research-validity.md#missingness-and-the-research-population)
covers selection through missing data. [Scope and alternatives](scope.md) explains what an IC
can establish about an investment strategy.

<span id="signal-persistence"></span>
[Signal persistence](signal-persistence.md) measures score changes independently of return labels.
Its sampling rules and diagnostic definitions are maintained on that page.

## References

- Spearman, C. (1904). [The Proof and Measurement of Association between Two Things][spearman].
  *The American Journal of Psychology*, 15(1), 72–101. Basis of rank association.
- Alphalens Reloaded. [Performance API][alphalens]. Software conventions for rank IC and buckets.

[spearman]: https://doi.org/10.2307/1412159
[alphalens]: https://alphalens.ml4trading.io/api-reference.html#alphalens.performance.factor_information_coefficient
