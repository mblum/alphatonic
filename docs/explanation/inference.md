# Dependence and uncertainty

Alphatonic estimates uncertainty along the time axis. Adjacent forward returns can share price
changes, persistent scores can make neighbouring ICs similar, and assets can respond to the same
shock. Counting every bar or asset as an independent replication would miss those relationships.

The estimand—the quantity being estimated—determines the calculation:

| Result | Estimand | Uncertainty calculation |
| --- | --- | --- |
| Cross-sectional summary | Mean of the valid timestamp ICs | Newey–West standard error, normal test and interval |
| Full-period time-series asset | One asset's score–target association | Paired circular block percentile interval; separate EWC zero-IC test |
| Full-period time-series summary | Equal-weight mean of eligible asset ICs | Shared time blocks for the interval; EWC on aggregated bar contributions for the test |

Monthly and rolling ICs describe changes over time. Their dispersion is not a confidence interval
for the full-period estimate. See [evaluation methodology](methodology.md) for sample eligibility
and [results and metrics](../reference/results.md) for stored columns.

## What an interval describes

A 95% confidence interval describes the repeated-sampling coverage of a procedure under its
assumptions. It does not assign a 95% probability to the realised interval or forecast the next
period's IC. The time-series bootstrap interval describes the supplied asset set; its endpoints
are not cross-asset quartiles and do not sample a larger population of possible assets.

Intervals remain individual-trial intervals. The [study adjustment](research-validity.md#what-the-study-adjustment-means)
applies to p-values and does not make intervals simultaneous or selection-adjusted. An unavailable
test is not evidence for the null.

## Why overlapping labels matter

Two consecutive five-bar returns share four one-bar price changes. Even if one-bar returns are
independent, their sums are not: with equal one-bar variances, those two sums have correlation
$4/5$. Simple compounded returns need not have exactly that correlation. If scores also change
slowly, the score–return products used in
an IC can remain dependent across many bars. The horizon therefore provides a minimum scale to
consider, not a complete description of dependence.

For a covariance-stationary scalar series $x_t$ with autocovariance
$\gamma_k=\operatorname{cov}(x_t,x_{t-k})$, the variance of a mean over $T$ consecutive bars is

$$
\operatorname{var}(\bar x)
=\frac{1}{T}\left[\gamma_0+2\sum_{k=1}^{T-1}
\left(1-\frac{k}{T}\right)\gamma_k\right].
$$

An independent-observation standard error uses only $\gamma_0/T$. Positive autocovariances add
uncertainty; negative ones can reduce it. The infinite-sample counterpart of the bracketed sum
is the **long-run variance**, when the autocovariances are summable. HAC estimators approximate
it using a finite history; [Newey and West (1987)][nw] give the Bartlett-weighted construction.

## Cross-sectional mean: Newey–West

Let $c_t$ be the IC at grid row $t$, $m_t$ indicate whether it is available, and
$n=\sum_t m_t$. Alphatonic averages the $n$ valid ICs with equal weight. Define $q_t=c_t-\bar c$
on valid rows and $q_t=0$ elsewhere. For lag count $L$, the implementation computes

$$
\widehat{\operatorname{se}}(\bar c)^2
=\frac{\displaystyle\sum_{t=1}^{T}q_t^2+
2\sum_{k=1}^{L}\left(1-\frac{k}{L+1}\right)
\sum_{t=k+1}^{T}q_tq_{t-k}}{n(n-1)}.
$$

The denominator includes an $n/(n-1)$ correction relative to division by $n^2$. Missing rows
contribute no centred score, but retain their positions: two valid ICs separated by a missing bar
are two bars apart. This is bookkeeping for the variance calculation, not imputation of a zero IC.

The automatic lag count is

$$
L=\max\left(h-1,\left\lfloor4(n/100)^{2/9}\right\rfloor\right),
$$

where $h$ is the return horizon. An explicit `hac_lags` replaces the second term, and the
$h-1$ floor still applies. This is a rule of thumb, not a fitted dependence model. In particular,
it is not the larger-bandwidth procedure with fixed-b critical values recommended by
[Lazarus et al. (2018)][har]. Longer dependence can remain beyond the selected lag count.

The statistic is $z=\bar c/\widehat{\operatorname{se}}(\bar c)$. Its two-sided p-value and
$\bar c\pm1.959964\,\widehat{\operatorname{se}}(\bar c)$ interval use the standard normal
approximation. The interval estimates the mean IC and is not clipped to the correlation bounds.
Inference needs $n>L+1$, non-negligible sample variation and a positive standard
error. Those checks establish computability, not finite-sample accuracy. Short histories and
large lag counts relative to history can still produce unreliable inference.

## Time-series intervals: paired circular blocks

The circular bootstrap takes contiguous blocks from the observed sequence, allowing a block to
wrap from the end to the beginning. The construction originates with
[Politis and Romano (1992)][circular] and is described in
[Politis and White (2004, §3.1)][blocks]. Alphatonic applies it to rows containing scores and
already-computed targets:

1. Draw block starting rows uniformly with replacement.
2. Take `block_bars` consecutive rows from each start, wrapping at the end; concatenate and
   truncate to the original number of rows.
3. Use those same rows for every asset and method. Recompute each correlation, including the
   ranks for Spearman, on the resampled finite pairs.
4. Take the 2.5th and 97.5th percentiles of valid estimates for the interval.

Paired resampling keeps a score with its observed target. Shared row indices keep contemporaneous
cross-asset relationships together and retain temporal relationships within blocks. Resampling
each asset independently would remove common shocks from the uncertainty of the mean. Blocks
break relationships at their joins; they do not preserve the original series in full.

Targets, volatility estimates and fitted signals are not recomputed on a synthetic price path.
The interval describes the supplied score–target process. It does not repeat model training or
account for selecting this signal from many candidates.

### Block length and available draws

For $T$ rows whose labels can end inside the window, the default length is
$b=\max(h,\lceil T^{1/3}\rceil)$. A supplied `block_bars` replaces the cube-root term, with the
horizon floor retained. The cube-root rule is a heuristic; alphatonic does not implement the
data-dependent block selector studied by [Politis and White (2004)][blocks]. Short blocks can
miss dependence; long blocks leave fewer distinct stretches of history to resample.

Alphatonic requires $T\geq5b$ and at least
$\max(100,\lceil0.8B\rceil)$ valid draws, where $B$ is `bootstrap_samples` (default 1000).
An originally eligible asset contributes an interval only if enough resamples have a defined
correlation. The mean uses a fixed eligible asset set for each method, rejecting any draw in which
one of those assets has an undefined correlation. It never substitutes a smaller universe for a
failed draw. The validity count and status reveal how often the interval could be computed.

Interior missing rows are sampled along with the data; they are not deleted before blocks are
formed. This preserves their placement within sampled stretches, but does not correct
informative missingness. Frequent invalid draws can also make the retained bootstrap distribution
unrepresentative. Increasing $B$ reduces Monte Carlo variability in the interval endpoints; it
does not create additional historical information or fix a poor block length.

The local random generator uses `SeedSequence([seed, horizon])`. The same data and options give
the same interval. Check sensitivity to plausible block lengths before interpreting a narrow
interval as strong evidence.

## Time-series tests: EWC

The full-period tests address zero association. Pearson and Spearman test their respective
centred ICs. Cosine tests a zero mean score–target product: a positive mean exposure can reject
this null even without timing skill. Its test is not a test of profitability after costs. For
varying scores and targets, the cosine timing component is zero exactly when Pearson IC is zero;
alphatonic reports no separate test for the static component.

### Contributions from bars and assets

For asset $i$, let $n_i$ be its number of valid pairs. Standardise scores and targets on those
pairs using population moments: centre and divide by standard deviation for Pearson, do the
same to average ranks for Spearman, and divide by root mean square for cosine. Call the results
$u_{i,t}$ and $v_{i,t}$. Define

$$
e_{i,t}=\frac{u_{i,t}v_{i,t}}{n_i},\qquad
\widehat{\mathrm{IC}}_i=\sum_{t=1}^{T}e_{i,t},
$$

with zero contribution on a missing row. For $N$ eligible assets, the mean IC has bar
contribution $d_t=N^{-1}\sum_i e_{i,t}$. Unequal observation counts therefore do not change
the equal-asset weighting.

Aggregating at each timestamp before estimating temporal uncertainty follows the principle in
[Driscoll and Kraay (1998)][dk]: cross-asset covariance enters the variance of the aggregated
series. Alphatonic applies that principle to IC contributions, rather than fitting the panel
regression in their paper. A t-test across the asset ICs would instead assume independent asset
estimates, which is inappropriate when assets share shocks.

The aggregate null concerns the mean IC over eligible assets, not each asset separately.
Positive and negative asset associations can cancel. When interpreting a near-zero mean, inspect
the asset distribution as well as the aggregate test.

### Cosine projections and degrees of freedom

The EWC estimator projects the contribution series on low-frequency cosine functions, following
[Lazarus et al. (2018)][har]. Here “cosine” names the variance estimator's basis functions;
EWC is used for all three IC methods. For either an asset's $e_t$ or the aggregate $d_t$, it computes

$$
\Lambda_j=\sqrt{\frac{2}{T}}\sum_{t=1}^{T}
\cos\left(\frac{\pi j(t-1/2)}{T}\right)e_t,\qquad
\widehat\Omega=\frac{1}{\nu}\sum_{j=1}^{\nu}\Lambda_j^2.
$$

Because the contributions sum to the IC, its test denominator is
$\mathrm{SE}_0=\sqrt{T\widehat\Omega}$. Alphatonic reports
$t=\widehat{\mathrm{IC}}/\mathrm{SE}_0$ and a two-sided Student t p-value with $\nu$ degrees of
freedom. Missing rows remain zero on the $T$-row grid. A zero denominator or no available cosine
term produces no test.

The number of terms is

$$
\nu=\min\left(\left\lfloor0.4T^{2/3}\right\rfloor,
\left\lfloor\frac{T}{2h}\right\rfloor\right).
$$

The first term follows Lazarus et al.; the horizon cap is alphatonic's additional heuristic.
It makes the shortest cosine period at least four horizons. This limits how far the estimator
looks beyond frequencies close to zero, but does not establish that the remaining spectrum is
flat. Fewer terms also mean fewer degrees of freedom and heavier t tails.

The Student t reference is a fixed-smoothing asymptotic result under regularity conditions, not
an exact finite-sample distribution for arbitrary IC data. In the special case of independent
Gaussian observations, orthogonal cosine projections give exact t inference for a mean. Financial
score–target products, and especially estimated ranks, are not generally such observations.
Lazarus et al.'s regression experiments motivate this construction; they do not validate every
correlation test, missing-data pattern or horizon cap used here.

### Why the test and interval can disagree

The products above construct a zero-association test. They are not a general influence-function
variance estimate at an arbitrary nonzero correlation. For Spearman, empirical ranks introduce
additional estimation effects; a zero rank correlation alone does not imply independence or
justify every simplification available under an independence null.

The bootstrap instead recomputes the statistic in each draw and forms a percentile interval.
It is not an inversion of the EWC test, so an interval containing zero and a p-value below 0.05
can occur together. Report both when that happens; selecting whichever appears more favourable
adds a selection decision. Do not form an alternative interval as `ic ± 1.96 * hac_se` for these
time-series tests.

## Assumptions and failure modes

Dependence-aware uncertainty still needs a sufficiently stable process, finite relevant moments
and dependence that weakens over time. Circular resampling assumes stretches of the observed
history can stand in for one another; a structural break undermines that assumption. EWC needs
the selected low-frequency projections to represent the long-run variance. Near-unit-root
persistence can defeat both a short block length and a low-frequency approximation.

Changing the standard error also leaves estimation bias untouched. [Stambaugh (1999)][stambaugh]
shows finite-sample bias in predictive regressions when predictor innovations and return shocks
are correlated. That result concerns a specified regression model, not a universal bias formula
for rank IC or momentum. Alphatonic applies no predictive-regression bias correction.

Neither method repairs scores computed with future data, selection of the best result, or an
unrepresentative surviving universe. Those are [research-design problems](research-validity.md).

## What the repository validates

Formula tests and simulation calibration answer different questions. Scalar oracles check the
implemented arithmetic, shared bootstrap indices, ranks, gaps and weighting. Calibration asks
how often an inferential procedure rejects or covers under a specified data-generating process.
The current [calibration suite][calibration] contains:

| Experiment | Design | Scope of evidence |
| --- | --- | --- |
| Newey–West null tests | 2000 replications; 512 retained Gaussian AR(1) observations; persistence 0 or 0.5; 16 lags | Mean inference for those scalar processes; an upper rejection bound allowing 0.03 excess above 0.05 |
| EWC null test | 2000 independent Gaussian series of length 128; 8 terms | The Gaussian mean case and its t reference distribution |
| Expanded EWC test | 10000 Gaussian series of length 512; 16 terms; null and mean shift 0.3 | Rejection and power in that location model |
| Expanded paired bootstrap | 2000 replications; 60 bars, two assets, common return shocks; independent scores; blocks of 3 and 200 draws | Coverage and availability of the equal-asset Spearman interval in that design; an upper noncoverage bound allowing 0.04 excess |

The last two experiments are marked `slow` and run with `--extended`. Binomial bounds account for
Monte Carlo error; at a rejection probability of 0.05, 2000 replications have standard error
$\sqrt{0.05(1-0.05)/2000}\approx0.0049$. The bootstrap's 200 draws per replication are not 200
additional independent experiments.

These checks do not establish nominal coverage or test size for arbitrary overlapping horizons,
heavy tails, informative gaps, fitted signals or changing regimes. In particular, the Gaussian
EWC mean experiment does not calibrate the complete time-series rank-IC pipeline. See the
[testing guide][testing] for the distinction between formula verification and statistical
validation.

## References

- Newey, W. K. and West, K. D. (1987). [A Simple, Positive Semi-Definite, Heteroskedasticity and
  Autocorrelation Consistent Covariance Matrix][nw]. *Econometrica*, 55(3), 703–708, equation (5).
- Lazarus, E., Lewis, D. J., Stock, J. H. and Watson, M. W. (2018).
  [HAR Inference: Recommendations for Practice][har]. *Journal of Business & Economic Statistics*,
  36(4), 541–559. EWC construction, truncation rules and size–power trade-offs.
- Driscoll, J. C. and Kraay, A. C. (1998). [Consistent Covariance Matrix Estimation with Spatially
  Dependent Panel Data][dk]. *The Review of Economics and Statistics*, 80(4), 549–560.
  [Working-paper version][dk-working], §2, explains averaging across units before HAC estimation.
- Politis, D. N. and Romano, J. P. (1992). [A Circular Block-Resampling Procedure for Stationary
  Data][circular]. In *Exploring the Limits of Bootstrap*, 263–270. Link to the 1991 technical
  report record; the construction is also given in Politis and White below.
- Politis, D. N. and White, H. (2004). [Automatic Block-Length Selection for the Dependent
  Bootstrap][blocks]. *Econometric Reviews*, 23(1), 53–70, §§2–3.1 for assumptions and resampling.
  Alphatonic uses a heuristic block length, not this paper's automatic selector.
- Stambaugh, R. F. (1999). [Predictive Regressions][stambaugh]. *Journal of Financial Economics*,
  54(3), 375–421. Link to NBER Technical Working Paper 240.

[nw]: https://doi.org/10.2307/1913610
[har]: https://www.princeton.edu/~mwatson/papers/LLSW_har_JBES_Final_071418.pdf
[dk]: https://doi.org/10.1162/003465398557825
[dk-working]: https://documents1.worldbank.org/curated/en/944831468739460842/pdf/multi0page.pdf
[circular]: https://statistics.stanford.edu/technical-reports/circular-block-resampling-procedure-stationary-data
[blocks]: https://public.econ.duke.edu/~ap172/Politis_White_2004.pdf
[stambaugh]: https://www.nber.org/papers/t0240
[calibration]: https://github.com/mblum/alphatonic/blob/master/tests/statistical/test_calibration.py
[testing]: https://github.com/mblum/alphatonic/blob/master/TESTING.md#statistical-validation
