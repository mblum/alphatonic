# Evaluation methodology

This page defines what alphatonic computes and what its uncertainty estimates assume. The
defaults named here are those of `EvaluationConfig` and `TimeSeriesOptions`.

## Bars and the evaluation window

The rows of the price table are the **bars**. A horizon of `h` is `h` rows. The evaluation window
is `[start, end)` in UTC: scores are evaluated at bars inside it, and only prices inside it are read,
so no label reaches beyond `end`.

## Forward-return labels

For a score observed at row `t`, horizon `h` and delay `d`, the label is

```text
price[t + d + h] / price[t + d] - 1
```

The whole path from `t` through `t + d + h` must have prices. A gap never turns an `h`-bar label
into a longer return, and a delisted or suspended asset has no labels across its gap. Labels must
end before `end`, so the final `d + h` bars have none. Non-finite returns (for example from a
price that jumps from `1e-300` to `1e300`) are missing.

## Cross-sectional evaluation

At each timestamp and horizon, the finite score/return pairs produce:

- **Spearman IC**, the Pearson correlation of average ranks, ties included. This is the primary
  metric.
- **Pearson IC**, the linear association, useful beside the rank IC.
- Counts of available assets, scored assets and pairs, pair coverage, and a skip reason.

A constant score or return, or fewer than `min_assets` pairs, gives an undefined IC and never
zero. Correlations whose magnitude is below 1e-12 are floating-point noise and are returned as exact
zero; this matters for small cross-sections, where rank correlations take few discrete values and
some are exactly zero. Pair coverage divides valid pairs by assets with a price at the timestamp. It
does not measure coverage against a historical universe.

### Summary statistics and inference

Timestamps are weighted equally. Reported: mean, sample standard deviation, positive fraction, and
**ICIR = mean / standard deviation**, without annualisation.

The standard error of the mean is Newey–West with Bartlett weights and an `n/(n−1)` correction,
using at least `horizon − 1` lags (automatically `max(horizon − 1, floor(4·(n/100)^(2/9)))`). The
reason is the overlap of labels: with `h`-bar labels and persistent scores, the ICs of adjacent
timestamps are dependent, so a plain standard error is too small. In a simulation of
20 assets and 300 bars with a factor that has no skill, 0.9 score persistence and a 5-bar horizon,
a plain t-test rejects the null in about a third of runs at the 5% level, while the Newey–West
estimate rejects in under a tenth (see `tests/test_inference.py`). Missing IC periods keep their positions in the grid, so a lag of
`k` always means `k` bars, and the denominator counts valid observations. The z-statistic,
two-sided p-value and 95% interval use the normal approximation. Inference is omitted when the
series is constant or shorter than the lag count permits. The interval is for the mean, so it is
not clipped to the correlation bounds.

## Time-series evaluation

For each asset and horizon, correlate scores with forward returns **over time**. Spearman ranks
are recomputed within each paired sample. The universe summary reports the equal-asset mean IC,
median, quartiles, positive fraction and number of eligible assets. It does not pool
asset-time observations into one correlation, and the quartiles describe dispersion, not
confidence.

**Windows.** The full period, each UTC calendar month, and trailing windows (30 days by default,
sampled daily) are evaluated independently. A bar takes part in a window only if the **label
also ends inside it**: a month never uses a return that settles in the next month. Months that are
not fully inside the evaluation period are `partial_window`. Rolling endpoints fall every `rolling_step`
after `start`, through `end`.

**Eligibility.** A window needs `min_pairs` (100) finite pairs, `min_coverage` (80%) of its
expected bars, and a length of at least `min_horizons` (20) horizons. Expected bars are those whose
label can end inside the window, so the deterministic end-of-window exclusion is not counted as
missing data, but missing prices and scores are. These are sample-size heuristics, not
significance thresholds.

**Monthly TS ICIR** is an asset's mean monthly IC divided by its sample standard deviation,
unannualised. It needs `min_months` (6) valid months and is marked `preliminary` below twelve.
The separately named *universe* ratio first averages the eligible assets' ICs within each month, then
takes mean over standard deviation across months, so the asset set can change between months. No
confidence interval or significance test is claimed for ICIR.

**Rolling IC** is descriptive. It is not used for any ratio or interval, and overlapping
windows are strongly dependent.

### Block bootstrap

The full-period IC of each asset and the mean asset IC get 95% **percentile intervals from a circular
block bootstrap** of paired score/return rows. One set of resampled time indices is shared by all
assets and by both methods, preserving cross-asset dependence, and ranks are recomputed in every
draw. Interior gaps keep their positions. The set of eligible assets stays fixed while bootstrapping
the mean. The default block length is `max(h, ceil(n^(1/3)))` for `n` bars with labels that end
inside the window; this is a heuristic, so set `block_bars` to examine the sensitivity to long
dependence. An interval needs at least five blocks of history and at least
`max(100, ceil(0.8 · bootstrap_samples))` valid draws. The generator is seeded with
`(seed, horizon)`, so results are reproducible and independent between horizons.

## Quantile response

Score buckets (`quantiles`, default 5) are formed from average ranks within each timestamp
(cross-sectional) or within each eligible asset's full sample (time series). Tied scores share a
bucket, and empty buckets stay missing. In the report, buckets are averaged with equal weight per
timestamp or per asset. They are retrospective: they describe what happened in the sample and are
not trading thresholds.

## Interpretation and limitations

These statistics measure predictive association. Close-to-close labels do not mean a trade
could execute at the observed price, and returns exclude fees, slippage, financing and market
impact. Inspect monthly stability and coverage, use samples long enough for the horizon, and reserve
chronological holdout periods before tuning. If you fit models, purge training labels that
overlap a validation period.

HAC and the block bootstrap handle temporal dependence under their assumptions. They do **not**
correct for trying many signals (see [compare factors](../how-to/compare-factors.md)), selection
bias, structural breaks, look-ahead in the factor, or a universe that excludes delisted assets.
The normal approximation for the cross-sectional interval is asymptotic and can be optimistic for
short samples or a large number of lags relative to the sample.
