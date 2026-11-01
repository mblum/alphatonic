# Evaluation methodology

This page explains how alphatonic measures predictive association and why its uncertainty estimates
account for dependence. For table columns, see [results and metrics](../reference/results.md). The
defaults named here are those of `EvaluationConfig` and `TimeSeriesOptions`.

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
prices) is missing. The $\sqrt{h}$ factor gives the target roughly unit variance at every horizon. A
label without an estimate is missing, so when prices begin at `start` the first bars have no
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

The standard error of the mean is Newey–West with Bartlett weights and an `n/(n−1)` correction,
using at least `horizon − 1` lags (automatically `max(horizon − 1, floor(4·(n/100)^(2/9)))`). The
reason is the overlap of labels: with `h`-bar labels and persistent scores, the ICs of adjacent
timestamps are dependent, so a plain standard error is too small. In a simulation of 20 assets and
300 bars with a factor that has no skill, 0.9 score persistence and a 5-bar horizon, a plain t-test
rejects the null in about a third of runs at the 5% level, while the Newey–West estimate rejects in
under a tenth (see `tests/test_inference.py`). Missing IC periods keep their positions in the grid,
so a lag of `k` always means `k` bars, and the denominator counts valid observations. The
z-statistic, two-sided p-value and 95% interval use the normal approximation. Inference is omitted
when the series is constant or shorter than the lag count permits. The interval is for the mean, so
it is not clipped to the correlation bounds.

## Time-series evaluation

For each asset and horizon, correlate scores with the time-series target **over time**, with three
methods:

- **Spearman**, ranks recomputed within each paired sample: monotone timing, robust to fat tails.
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

The full-period IC of each asset and the mean asset IC get 95% **percentile intervals from a
circular block bootstrap** of paired score/return rows. One set of resampled time indices is shared
by all assets and all methods, preserving cross-asset dependence, and ranks are recomputed in every
draw. Interior gaps keep their positions. The set of eligible assets stays fixed while bootstrapping
the mean. The default block length is `max(h, ceil(n^(1/3)))` for `n` bars with labels that end
inside the window; this is a heuristic, so set `block_bars` to examine the sensitivity to long
dependence. An interval needs at least five blocks of history and at least `max(100, ceil(0.8 ·
bootstrap_samples))` valid draws. The generator is seeded with `(seed, horizon)`, so results are
reproducible and independent between horizons.

### Time-series tests

Each eligible asset's full-period IC, and the mean IC over the eligible assets, comes with a
t-statistic and a two-sided p-value (`hac_t` and `hac_p_value`).

**The null hypothesis.** For Spearman and Pearson, the null is that the scores do not time the
target: the IC is zero. For the cosine, it is that the mean of $s \cdot r$ is zero: held as a
position, the score earns nothing in units of the target. This is a test of the per-bar Sharpe ratio
of the payoff $s \cdot r$, with a standard error that allows for dependence (Lo 2002, "The
Statistics of Sharpe Ratios", *Financial Analysts Journal* 58(4)). A score that is long on average
on a rising asset rejects it, as it should, because the cosine credits the average position. The
timing part of the cosine is zero exactly when Pearson's correlation is, so the Pearson test is its
test. The static part has no test of its own: it is the mean score times the asset's realised drift,
and a drift is hard to tell from zero.

**The statistic.** Standardise an asset's scores $s_t$ and targets $r_t$ over its $n$ valid pairs as
the method correlates them: subtract the mean and divide by the standard deviation (for Spearman, of
the ranks), or, for the cosine, divide by the root mean square. With the standardised values $u_t$
and $v_t$, the IC is the mean of $u_t v_t$, so bar $t$ contributes

$$
e_t = \frac{u_t v_t}{n}, \qquad \text{IC} = \sum_t e_t,
$$

and a bar without a pair contributes zero. Under the null the contributions have mean zero. They
are the first-order terms of the IC at zero association; using them rather than the terms at the
estimated IC keeps the test's size in short samples. The mean IC over $N$ eligible assets adds their
contributions bar by bar, $d_t = \frac{1}{N} \sum_i e_{i,t}$, as Driscoll and Kraay (1998,
"Consistent Covariance Matrix Estimation with Spatially Dependent Panel Data", *Review of Economics
and Statistics* 80(4)) do for panels. Assets that share a signal and a market factor then count as
the correlated draws they are, where a t-test across the assets' ICs would treat them as
independent.

**The standard error.** Overlapping labels and persistent scores make neighbouring contributions
dependent. Their long-run variance is estimated with the equal-weighted cosine (EWC) estimator of
Lazarus, Lewis, Stock and Watson (2018, "HAR Inference: Recommendations for Practice", *Journal of
Business & Economic Statistics* 36(4)), over the $T$ bars whose label ends inside the window, with
missing bars as zeros so that every bar keeps its place in time:

$$
\hat\Omega = \frac{1}{\nu} \sum_{j=1}^{\nu} \Lambda_j^2, \qquad
\Lambda_j = \sqrt{\frac{2}{T}} \sum_{t=1}^{T} \cos\left(\frac{\pi j (t - 1/2)}{T}\right) e_t.
$$

The standard error is $\sqrt{T \hat\Omega}$ (`hac_se`), the t-statistic is the IC divided by it,
and the p-value comes from Student's t with $\nu$ degrees of freedom (`hac_dof`). With $\nu$ fixed,
that is the distribution of the ratio when the long-run variance is about flat over the frequencies
of the cosines. The number of cosines is

$$
\nu = \min\left(\left\lfloor 0.4\, T^{2/3} \right\rfloor, \left\lfloor \frac{T}{2h} \right\rfloor\right).
$$

The first term is the rule Lazarus et al. recommend. The second is alphatonic's: the products of
overlapping $h$-bar labels are dependent over about $h$ bars, so the estimator must average over
slower movements than that, and the cap makes the shortest cosine span at least four horizons. With
fewer than $2h$ bars there is no cosine, and the test is omitted. Because $\hat\Omega$ is computed
under the null, `hac_se` is the IC's spread when there is no association: it is the test's
denominator, not the basis of an interval.

A Newey–West estimate with about $h$ lags, as the cross-section uses, gives these autocovariances
too little weight, and Ang and Bekaert (2007, "Stock Return Predictability: Is It There?", *Review
of Financial Studies* 20(3)) find that such standard errors over-reject in overlapping long-horizon
regressions. In fixed-seed simulations of scores that are independent of returns
(`tests/test_inference.py`):

- With 20 assets, 300 bars, score persistence 0.9 and a 5-bar horizon, a correlation t-test that
  treats every bar as independent rejects for about a third of the assets. The asset tests reject in
  5–6% of cases, and the mean-IC tests in 6–8%.
- With 20 assets, 400 bars, score persistence 0.98, half the variance of both scores and returns
  shared by all assets, and a 20-bar horizon, a t-test of the mean IC across assets rejects in about
  40% of samples, and the mean-IC tests in 6–8%. With Lazarus et al.'s rule alone, the asset tests
  reject in 8–9% of cases; with the cap, in 5–7%.

The test and the bootstrap interval are computed differently, the interval by resampling blocks of
bars, so near the 5% level they can disagree. The p-value asks whether there is any association;
the interval says how large it is.

## Quantile response

Score buckets (`quantiles`, default 5) are formed from average ranks within each timestamp
(cross-sectional) or within each eligible asset's full sample (time series), and average each
analysis's target: returns, or vol-scaled returns in multiples of $\hat\sigma \sqrt{h}$. Tied scores share
a bucket, and empty buckets stay missing. In the report, buckets are averaged with equal weight per
timestamp or per asset. They are retrospective: they describe what happened in the sample and are
not trading thresholds.

## Trials and the holdout

A `Study` counts the trials of each family: every evaluation it saved under that family's name,
across parameters and both samples. With `n` trials, its board reports `min(1, n × p)` for each
p-value `p` of a trial: the cross-sectional one as `adjusted_p`, and the time-series rank and cosine
ones as `ts_adjusted_p` and `ts_cosine_adjusted_p`. This is Bonferroni's bound: if each of `n` tests rejects
a true null with probability at most `α`, the chance that any of them does is at most `n × α`,
whatever the dependence between them. Comparing `n × p` with `α` therefore keeps the chance of at
least one false rejection in that fixed family at `α` or below, provided the individual p-values are
valid. alphatonic uses approximate p-values and counts recorded trials; this is not a guarantee for
an adaptive search or repeated inspection of the results. It is conservative when the trials are
correlated, as parameter variants of one signal usually are. Harvey, Liu and Zhu (2016, "… and the
Cross-Section of Expected Returns", *Review of Financial Studies* 29(1)) apply the same reasoning to
published factors and ask a new factor for a t-statistic above 3.

The count is a lower bound. Variants evaluated outside the study, or dropped before evaluation, are
not in it, and nothing but the family name pools signals that test one idea. Each p-value is
adjusted for the trials alone, not for the trial's other two p-values: picking trials by whichever
of the three is smallest makes `3 × n` tests, and the same bound then asks for `3 × n × p` at or
below `α`. ICs and their intervals are reported as estimated.

An in-sample evaluation ends at the holdout boundary, and labels end before the window does, so no
in-sample label reads a holdout price. A holdout evaluation starts at the boundary; its volatility
estimate for `vol_scaled` targets may read prices before it, which is information available at the
time. Each holdout evaluation is counted per family, because a holdout tests a choice only while
that choice was made without it.

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
The time-series tests assume that the long-run variance is about flat over the frequencies of their
cosines. They do not correct the IC itself: with a persistent score built from past returns, such as
momentum, the score's changes are correlated with the returns it predicts, and the sample IC is
biased in finite samples (Stambaugh 1999, "Predictive Regressions", *Journal of Financial
Economics* 54(3)).

## Signal persistence

Signal persistence is descriptive and independent of forward-return horizons and label availability.
It compares scores with prices available at their own endpoints on the original bar grid:
cross-sectional rank persistence and bucket entry fractions, plus normalised score changes and
sign/zero transitions per asset. Summaries weight valid timestamps equally in the cross-section and
eligible assets equally in time series. No annualisation or inference is applied. See [signal
persistence](signal-persistence.md) for formulas, units, eligibility rules, research sources and the
distinction between score changes and trading costs.
