# Targets, scaling and the cosine IC

A score can answer two different questions: do higher scores accompany higher subsequent targets,
and would its average direction have benefited from the asset's return? Spearman and Pearson
address the first question. Cosine also includes the second.

alphatonic reports all three for time series. It uses raw returns by default in the cross-section
and volatility-scaled returns in time series. This page explains how the target and score scale
determine what an association means. See [configure an evaluation](../how-to/configure-evaluation.md#choose-the-target)
to change them.

## Timing and average exposure

[Spearman (1904)][spearman] measures association through ranks. Pearson measures linear association
after subtracting the means. Adding a constant to every score changes neither correlation.
A signal that is always long therefore receives
no extra credit just because the asset rose over the sample.

Cosine keeps the means. For scores `s` and targets `r`, it is:

$$
\text{cosine} = \frac{\operatorname{mean}(s r)}{\operatorname{rms}(s)\,\operatorname{rms}(r)}
$$

Here `rms` means root mean square. Adding a constant to the scores can change cosine because it
changes the signal's average position. Multiplying every score by the same positive constant leaves
it unchanged.

The numerator splits into covariance and the product of the means:

$$
\text{cosine} = \underbrace{\frac{\operatorname{cov}(s, r)}{\operatorname{rms}(s)\,\operatorname{rms}(r)}}_{\text{timing}}
+ \underbrace{\frac{\bar s\,\bar r}{\operatorname{rms}(s)\,\operatorname{rms}(r)}}_{\text{static}}
$$

These use population moments over valid pairs. The timing part reflects how scores and targets vary
together. The static part reflects the average score and average target. Both are signed, and they
sum to cosine. They are not percentages of portfolio profit. This decomposition follows directly
from the identity $E[sr]=\operatorname{cov}(s,r)+E[s]E[r]$, where $E$ here denotes the average over
valid sample pairs; it does not require a model of returns.
For varying scores and targets, the timing component is Pearson IC multiplied by `sd/rms`
for scores and targets. Alphatonic
reports the components as `ic_timing` and `ic_static`; `long_fraction` is the share of valid pairs
with a positive score.

The means describe realised sample exposure and targets, not a separately estimated risk premium.

For example, a constant positive score on an asset with a positive average target has a positive
cosine, all of it static. Spearman and Pearson report `constant_signal` because the score never
varies. Cosine is undefined if all paired scores (`zero_signal`) or all paired targets
(`zero_returns`) are zero. The [sample-size and coverage requirements](methodology.md#time-series-evaluation)
still apply.

### Cosine is not a Sharpe ratio

If `x = s · r` is a hypothetical excess payoff, its per-bar Sharpe ratio is `mean(x) / sd(x)`.
Cosine has the same numerator but divides by `rms(s) · rms(r)`. Those denominators need not be
equal. They can
be close when the mean payoff is small and squared scores and squared targets have little
dependence. Using population moments, the exact relationship behind that comparison is

$$
\operatorname{var}(sr)=E[s^2]E[r^2]+\operatorname{cov}(s^2,r^2)-E[sr]^2.
$$

The last two terms explain why the denominators can differ, even when the cosine is defined.
[Lo (2002)][lo] studies Sharpe-ratio inference and shows why serial dependence matters for time
aggregation. Alphatonic's ICIR and cosine are not the Sharpe estimator studied there.

That approximation is not a trading result. Overlapping multi-bar labels, changing exposure,
execution and costs require separate accounting. Do not annualise cosine or read it as a strategy
Sharpe ratio. The [simulation script](targets_and_scaling.py) explores examples where the measures
are close; it does not establish a general identity.

### Why cosine is absent from the cross-section

Cross-sectional IC compares assets at one timestamp. Shifting every score by the same amount should
not change that comparison. Cosine would change, and it would also respond to the market's common
direction. Spearman and Pearson avoid those effects by centring their inputs. If both scores and
targets are centred, cosine equals Pearson.

## Volatility-scaled targets

Each analysis builds its target from the [forward-return label](methodology.md#forward-return-labels):

| `target` | Value | Default for |
| --- | --- | --- |
| `return` | The forward-return label | Cross-section (`target`) |
| `vol_scaled` | The label divided by estimated horizon volatility | Time series (`time_series.target`) |

A raw return of 2% means something different for a quiet asset than for a volatile one. A
volatility-scaled target measures the return relative to estimated risk:

$$
\text{target}_t = \frac{\text{forward return}_t}{\text{volatility}_t \sqrt{\text{horizon}}}
$$

Volatility scaling also appears in trading research. [Lim, Zohren and Roberts (2019, §III)][lim]
use signals multiplied by inverse ex-ante volatility and estimate volatility with a 60-day
exponentially weighted standard deviation. This motivates expressing a target in risk units;
it does not transfer their strategy results to an IC evaluation. Alphatonic's span is in bars,
so 60 hourly bars and 60 daily bars encode different histories.

The volatility estimate is the exponentially weighted standard deviation of one-bar returns. By
default `vol_span` is 60 bars and `vol_min_bars` requires at least 20 returns. It includes the return
ending at the score's timestamp and can use prices before the evaluation window. It never uses future prices. A
missing or zero estimate produces a missing target. `Evaluation.volatility` holds the estimate
on the evaluation grid. Scaling can reduce the influence of volatile periods, but does not
eliminate outliers or errors in the volatility estimate.

The square-root adjustment makes horizons more comparable when variance grows roughly in proportion
to the horizon. It does not guarantee unit variance. Volatility clustering, serial correlation and
estimation error can all affect the scale. For a stationary one-bar return $R_t$ with variance
$\gamma_0$ and lag-$k$ autocovariance $\gamma_k$,

$$
\operatorname{var}\left(\sum_{j=1}^{h}R_{t+j}\right)
=h\gamma_0+2\sum_{k=1}^{h-1}(h-k)\gamma_k.
$$

The square-root rule drops the autocovariance terms. This identity is exact for a sum, as in
[Lo (2002, equations 16–19)][lo]; alphatonic's price-ratio simple return compounds one-bar returns,
so using the sum adds an approximation. Neither volatility normalisation nor the horizon factor
makes the resulting target independent over time.

Time-series IC uses this target by default so large raw returns in volatile periods have less
influence. The cross-sectional default uses raw returns: it asks whether scores rank the returns
themselves. Choose the target that matches what your score predicts. Neither choice is universally
better.

Supply earlier prices if you want volatility estimates ready at `start`. Otherwise, the first 20
bars have no scaled target under the defaults. Across gaps, the estimate can carry forward, but a
return label still needs an unbroken price path.

## Signal scaling

alphatonic does not rescale scores. A transformation can change what is being evaluated:

| Transformation within a paired sample | Spearman | Pearson | Cosine |
| --- | --- | --- | --- |
| Multiply by one positive constant | Unchanged | Unchanged | Unchanged |
| Add one constant | Unchanged | Unchanged | Can change |
| Strictly increasing transform | Unchanged | Can change | Can change |
| Cap scores or take their sign | Can change: creates ties | Can change | Can change |
| Divide by volatility that varies across observations | Can change | Can change | Can change |

Ranking preserves Spearman when it preserves the same ties. Cross-sectional z-scoring leaves both
cross-sectional correlations unchanged when the scale is nonzero. Cross-sectional ranking preserves
Spearman but can change Pearson. Either transformation can change time-series IC because it changes
the scores differently at different timestamps.

If scores represent positions, give zero a clear meaning and choose their units before interpreting
cosine. The [research-validity explanation](research-validity.md#what-the-chronological-boundary-protects)
covers look-ahead from fitted scaling.

## Why keep Spearman and Pearson?

Cosine includes average exposure; it does not replace a measure of timing. Spearman is useful when
ordering matters more than magnitude. Pearson helps reveal linear relationships and is more
sensitive to large values. Reading them together can expose a result driven by outliers or a few
large scores. Replacing magnitudes by ranks limits the effect of an extreme value's size, but
does not protect against data leakage, selective missingness or a small number of informative
observations. A zero Pearson or Spearman IC also does not rule out every nonlinear relationship.

Kendall's tau is another rank-association measure. alphatonic does not currently report it. The
supported methods and their columns are listed in the [results reference](../reference/results.md).

## References

- Spearman, C. (1904). [The Proof and Measurement of Association between Two Things][spearman].
  *The American Journal of Psychology*, 15(1), 72–101. Rank association.
- Lim, B., Zohren, S. and Roberts, S. (2019). [Enhancing Time Series Momentum Strategies Using
  Deep Neural Networks][lim]. arXiv:1904.04912; linked text is revision 3 (2020).
  §III defines volatility-scaled exposure; §VI examines position changes and costs.
- Lo, A. W. (2002). [The Statistics of Sharpe Ratios][lo]. *Financial Analysts Journal*,
  58(4), 36–52. Sharpe-ratio uncertainty and time aggregation with serial dependence.

[spearman]: https://doi.org/10.2307/1412159
[lim]: https://arxiv.org/html/1904.04912v3
[lo]: https://traders.studentorg.berkeley.edu/papers/The-Statistics-of-Sharpe-Ratios.pdf
