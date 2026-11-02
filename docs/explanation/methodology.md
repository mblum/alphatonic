# Evaluation methodology

This page explains how alphatonic measures predictive association and why its uncertainty estimates
account for dependence. For table columns, see [results and metrics](../reference/results.md). The
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

Each analysis correlates the scores with a **target** built from the label:

| `target` | Value | Default for |
| --- | --- | --- |
| `return` | The label. | Cross-section (`target`) |
| `vol_scaled` | $\text{label} / (\hat\sigma_t \sqrt{h})$ | Time series (`time_series.target`) |

$\hat\sigma_t$ is the exponentially weighted standard deviation of one-bar returns ending at or before row
`t` (`vol_span`, default 60 bars), available once `vol_min_bars` (20) returns have been seen. It
uses only prices known at the observation, including prices before `start`, so it adds no
look-ahead; across a gap the last estimate carries forward, and an estimate of zero (constant
prices) is missing. The $\sqrt{h}$ factor approximates horizon scaling when return variance grows
proportionally to the horizon; it does not guarantee unit variance. A label without an estimate is
missing, so when prices begin at `start` the first bars have no
vol-scaled target. `Evaluation.volatility` holds `σ̂` on the evaluation grid.

Scaling expresses returns in estimated risk units. It can reduce the influence of volatile periods,
but does not eliminate outliers or errors in the volatility estimate. Choose this target when your
score predicts returns relative to risk. [Targets, scaling and the cosine
IC](targets-and-scaling.md) explains the defaults.

## Cross-sectional evaluation

At each timestamp and horizon, the finite score/return pairs produce:

- **Spearman IC**, the Pearson correlation of average ranks, ties included. This is the primary
  metric.
- **Pearson IC**, the linear association, useful beside the rank IC.
- Counts of available assets, scored assets and pairs, pair coverage, and a skip reason.

A constant score or return, or fewer than `min_assets` pairs, gives an undefined IC and never zero.
Correlations whose magnitude is below 1e-12 are floating-point noise and are returned as exact zero;
this matters for small cross-sections, where rank correlations take few discrete values and some are
exactly zero. Pair coverage divides valid pairs by assets with a price at the timestamp. It does not
measure coverage against a historical universe.

### Summary statistics and inference

Timestamps are weighted equally. Reported: mean, sample standard deviation, positive fraction, and
**ICIR = mean / standard deviation**, without annualisation.

The standard error of the mean uses the Bartlett-weighted estimator of
[Newey and West (1987)][nw], with a finite-sample correction. Its lag count is at least
`horizon - 1`; missing periods retain their positions on the bar grid. The reported test is
two-sided and uses a normal approximation. The 95% interval estimates the mean IC, not the range
of future ICs. It is not clipped to the correlation bounds.

[Dependence and uncertainty](inference.md#cross-sectional-mean-neweywest) gives the formula,
lag-selection rule and assumptions. A long horizon or persistent series can require more history
and longer lags than the defaults provide. An unavailable test is not evidence for the null.

## Time-series evaluation

For each asset and horizon, correlate scores with the time-series target **over time**, with three
methods:

- **Spearman**, ranks recomputed within each paired sample: monotone timing, with magnitudes
  replaced by ranks.
- **Pearson**, linear timing.
- **Cosine**, the uncentred correlation $\sum s r \big/ \sqrt{\sum s^2 \sum r^2}$. It treats the score as a
  position, so its zero point matters: a signal that is long on average earns the asset's drift.
  It can resemble a per-bar Sharpe ratio in some settings, but it is not a portfolio Sharpe
  ratio. See [the distinction](targets-and-scaling.md#cosine-is-not-a-sharpe-ratio).

The cosine splits exactly into two parts, reported as `ic_timing` and `ic_static`:

$$
\text{cosine} = \underbrace{\frac{\operatorname{cov}(s, r)}{\operatorname{rms}(s)\,\operatorname{rms}(r)}}_{\text{timing}}
+ \underbrace{\frac{\bar s\,\bar r}{\operatorname{rms}(s)\,\operatorname{rms}(r)}}_{\text{static}}
$$

with population moments over the valid pairs. The **timing** part is the covariance, Pearson's
correlation rescaled by `sd/rms` on both sides. The **static** part is what the average position
earns from the average target, which needs no prediction. A constant, non-zero score is a valid
position for the cosine (all static); Spearman and Pearson call it `constant_signal`. The cosine is
undefined when every score (`zero_signal`) or every target (`zero_returns`) is zero. The usual
sample-size and coverage checks also apply. `long_fraction` is the share of valid pairs with a
positive score.

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

### Block bootstrap

Full-period asset ICs and their equal-asset mean receive percentile intervals from paired circular
blocks of time, following the resampling construction described by
[Politis and White (2004, §3.1)][blocks]. All assets share the sampled indices so that common shocks
remain together. Scores and targets are resampled as pairs, and Spearman ranks are recomputed.
The eligible asset set is fixed per method. This estimates uncertainty for the supplied assets;
it does not sample a larger population of possible assets.

The [bootstrap explanation](inference.md#time-series-intervals-paired-circular-blocks) describes
block length, rejected draws and the stationarity assumptions. It also explains why increasing the
number of draws cannot compensate for a short historical sample.

### Time-series tests

Full-period time-series tests use an equal-weighted cosine (EWC) long-run variance estimator and
Student t reference distribution, based on [Lazarus et al. (2018)][har]. For the equal-asset mean,
contributions are averaged across assets at each bar before estimating temporal uncertainty,
following the aggregation principle of [Driscoll and Kraay (1998)][dk].

The reported `hac_se` is the denominator of a zero-IC test, not the standard error used to form
the bootstrap interval. Alphatonic's application to correlations, missing pairs and the additional
horizon-based cap are implementation choices; the cited papers do not establish their validity
for every signal. See [the test construction and calibration limits](inference.md#time-series-tests-ewc).

## Quantile response

Score buckets (`quantiles`, default 5) are formed from average ranks within each timestamp
(cross-sectional) or within each eligible asset's full sample (time series), and average each
analysis's target: returns, or vol-scaled returns in multiples of $\hat\sigma \sqrt{h}$. Tied scores share
a bucket, and empty buckets stay missing. In the report, buckets are averaged with equal weight per
timestamp or per asset. They are retrospective: they describe what happened in the sample and are
not trading thresholds.

## Trials and the holdout

A `Study` counts every saved evaluation in a family, including repeated variants and holdout
uses. Its board reports `min(1, trial_count * p)` beside each of three p-values. This is a
Bonferroni adjustment, discussed for factor research by [Harvey, Liu and Zhu (2016)][hlz].
It requires valid individual p-values and an adequately specified testing family; the count
alone does not make adaptive research confirmatory.

The boundary prevents in-sample labels from ending in the holdout. It cannot prevent the caller
from using holdout information to construct scores. [Trials, selection and the holdout](research-validity.md)
explains what is counted, which searches remain unadjusted, and why repeated holdout use changes
its interpretation.

## Interpretation and limitations

These statistics measure predictive association. Close-to-close labels do not mean a trade could
execute at the observed price, and returns exclude fees, slippage, financing and market impact.
Inspect monthly stability and coverage, use samples long enough for the horizon, and reserve
chronological holdout periods before tuning. If you fit models, purge training labels that overlap a
validation period.

HAC and the block bootstrap handle temporal dependence under their assumptions. They do **not**
correct for trying many signals (a [study](../how-to/run-a-study.md) scales the p-values by the
trials it holds), selection bias, structural breaks, look-ahead in the factor, or a universe that
excludes delisted assets. The normal approximation for the cross-sectional interval is
asymptotic and can be optimistic for short samples or a large number of lags relative to the sample.
Missingness also changes the population being described. If missing returns concentrate around
suspensions or distress, complete pairs need not represent the intended universe. Keeping gaps on
the grid preserves lag meaning; it does not correct selection caused by those gaps. The
[inference](inference.md#assumptions-and-failure-modes) and
[research-validity](research-validity.md) pages separate sampling uncertainty from these other
sources of error.

## Signal persistence

Signal persistence is descriptive and independent of forward-return horizons and label availability.
It compares scores with prices available at their own endpoints on the original bar grid:
cross-sectional rank persistence and bucket entry fractions, plus normalised score changes and
sign/zero transitions per asset. Summaries weight valid timestamps equally in the cross-section and
eligible assets equally in time series. No annualisation or inference is applied. See [signal
persistence](signal-persistence.md) for formulas, units, eligibility rules, research sources and the
distinction between score changes and trading costs.

## References

- Spearman, C. (1904). [The Proof and Measurement of Association between Two Things][spearman].
  *The American Journal of Psychology*, 15(1), 72–101. Basis of rank association.
- Newey, W. K. and West, K. D. (1987). [A Simple, Positive Semi-Definite, Heteroskedasticity and
  Autocorrelation Consistent Covariance Matrix][nw]. *Econometrica*, 55(3), 703–708.
- Lazarus, E., Lewis, D. J., Stock, J. H. and Watson, M. W. (2018).
  [HAR Inference: Recommendations for Practice][har]. *Journal of Business & Economic Statistics*,
  36(4), 541–559.
- Driscoll, J. C. and Kraay, A. C. (1998). [Consistent Covariance Matrix Estimation with Spatially
  Dependent Panel Data][dk]. *The Review of Economics and Statistics*, 80(4), 549–560.
- Politis, D. N. and White, H. (2004). [Automatic Block-Length Selection for the Dependent
  Bootstrap][blocks]. *Econometric Reviews*, 23(1), 53–70, §3.1 for the circular construction.
- Harvey, C. R., Liu, Y. and Zhu, H. (2016). [… and the Cross-Section of Expected Returns][hlz].
  *The Review of Financial Studies*, 29(1), 5–68, §§3.3–3.4 on multiple testing.
- Alphalens Reloaded. [Performance API][alphalens]. Software conventions for rank IC and buckets.

[spearman]: https://doi.org/10.2307/1412159
[nw]: https://doi.org/10.2307/1913610
[har]: https://www.princeton.edu/~mwatson/papers/LLSW_har_JBES_Final_071418.pdf
[dk]: https://doi.org/10.1162/003465398557825
[blocks]: https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf
[hlz]: https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF
[alphalens]: https://alphalens.ml4trading.io/api-reference.html#alphalens.performance.factor_information_coefficient
