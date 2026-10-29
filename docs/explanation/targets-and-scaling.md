# Targets, scaling and the cosine IC

A score can answer two different questions: does it predict changes in returns, and would its
average direction have benefited from the asset's return? Spearman and Pearson address the first
question. Cosine also includes the second.

alphatonic reports all three for time series. It uses raw returns by default in the cross-section
and volatility-scaled returns in time series. This page explains those choices. See [configure an
evaluation](../how-to/configure-evaluation.md#choose-the-target) to change them.

## Timing and average exposure

Spearman compares ranks. Pearson measures linear association after subtracting the means. Adding a
constant to every score changes neither correlation. A signal that is always long therefore receives
no extra credit just because the asset rose over the sample.

Cosine keeps the means. For scores `s` and targets `r`, it is:

```text
cosine = mean(s · r) / (rms(s) · rms(r))
```

Here `rms` means root mean square. Adding a constant to the scores can change cosine because it
changes the signal's average position. Multiplying every score by the same positive constant leaves
it unchanged.

The numerator splits into covariance and the product of the means:

```text
cosine = cov(s, r) / (rms(s) · rms(r)) + mean(s) · mean(r) / (rms(s) · rms(r))
         └──────── timing ──────────┘   └────────── static ─────────────┘
```

These use population moments over valid pairs. The timing part reflects how scores and targets vary
together. The static part reflects the average score and average target. Both are signed, and they
sum to cosine. They are not percentages of portfolio profit.

For example, a constant positive score on an asset with a positive average target has a positive
cosine, all of it static. Spearman and Pearson are undefined because the score never varies. Cosine
is undefined if all paired scores or all paired targets are zero. Sample-size and coverage
requirements still apply.

### Cosine is not a Sharpe ratio

If `x = s · r` is a hypothetical payoff, its per-bar Sharpe ratio is `mean(x) / sd(x)`. Cosine has
the same numerator but divides by `rms(s) · rms(r)`. Those denominators need not be equal. They can
be close when the mean payoff is small and squared scores and squared targets have little
dependence.

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

A raw return of 2% means something different for a quiet asset than for a volatile one. A
volatility-scaled target measures the return relative to estimated risk:

```text
target[t] = forward_return[t] / (volatility[t] · sqrt(horizon))
```

The volatility estimate is the exponentially weighted standard deviation of one-bar returns. By
default its span is 60 bars and it needs at least 20 returns. It includes the return ending at the
score's timestamp and can use prices before the evaluation window. It never uses future prices. A
missing or zero estimate produces a missing target.

The square-root adjustment makes horizons more comparable when variance grows roughly in proportion
to the horizon. It does not guarantee unit variance. Volatility clustering, serial correlation and
estimation error can all affect the scale.

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
cosine. Estimate any fitted scaling using information available at the time. Full-sample
normalisation can introduce look-ahead.

## Why keep Spearman and Pearson?

Cosine includes average exposure; it does not replace a measure of timing. Spearman is useful when
ordering matters more than magnitude. Pearson helps reveal linear relationships and is more
sensitive to large values. Reading them together can expose a result driven by outliers or a few
large scores.

Kendall's tau is another rank-association measure. alphatonic does not currently report it. The
supported methods and their columns are listed in the [results reference](../reference/results.md).

## Further reading

These works discuss time-series signals, volatility scaling and the distinction between timing and
average exposure. Their strategies and estimators are not identical to alphatonic's:

- Moskowitz, Ooi and Pedersen (2012), “Time Series Momentum”, *Journal of Financial Economics* 104.
- Anatolyev and Gerko (2005), “A Trading Approach to Testing for Predictability”,
  *Journal of Business & Economic Statistics* 23.
- Lim, Zohren and Roberts (2019), “Enhancing Time Series Momentum Strategies Using Deep Neural
  Networks”, arXiv:1904.04912.
- Grinold (1994), “Alpha Is Volatility Times IC Times Score”, *Journal of Portfolio Management*.

The [methodology](methodology.md) describes the exact calculations used by alphatonic.
