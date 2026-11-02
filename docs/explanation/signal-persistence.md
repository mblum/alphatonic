# Signal persistence

Signal persistence measures how scores change before any portfolio is constructed. It is independent
of forward-return horizons, delay, targets, volatility warmup and return availability. These
diagnostics do not compute positions, traded notional, costs or P&L.

## Available diagnostics

Every new evaluation computes `result.persistence`. For a runnable example and settings, see
[measure signal persistence](../how-to/configure-evaluation.md#signal-persistence). The definitions below explain how
missing observations and changing asset sets affect the results.

An eligible score has a finite score and a price **at its own timestamp**. Each comparison uses
endpoints exactly `lag` rows apart on the price grid. It never drops missing rows before shifting. A
lag of 5 compares endpoints five bars apart, even if an interior bar is missing; it neither measures
the intervening path nor sums five one-bar changes. A score that moves from positive to negative
and back between the endpoints can have zero endpoint change. Increasing the lag therefore
changes the comparison, rather than accumulating turnover. Both endpoints must be inside the
evaluation window; no score history before `start` is read. All timestamps through the last bar can contribute,
even when they have no future-return label.

### Cross-sectional rank persistence

Rank all eligible scores independently at each timestamp, using average ranks for ties. Compute
Pearson correlation of those ranks on the assets common to the two endpoints. This follows [Alphalens
Reloaded's rank-autocorrelation convention][alphalens]; with changing universes it need not equal
re-ranking only the common assets. The common sample needs `min_assets` and varying ranks at
both endpoints. Values range from −1 (reversed
ordering) to 1 (preserved ordering). High persistence does not establish low dollar turnover:
weights, leverage and volatility scaling can still change.

### Bucket membership

Assign scores at each timestamp to `ceil(quantiles * average_rank / n_eligible)`. Ties stay together
and some buckets can be empty. Each endpoint must have at least `min_assets` and distinct scores.
Following [Alphalens' membership comparison][alphalens], for bucket Q, entry fraction is
`|Q_now − Q_before| / |Q_now|`. A value of 0.2 means 20% of current members were absent from the
prior bucket. An empty current bucket is undefined; an empty prior
bucket at an otherwise eligible timestamp gives 1 for a nonempty current bucket.

Entry and exit counts are both reported: changes in bucket size can make them different. Counts of
bucket entrants absent from the prior eligible universe and exits absent from the current universe
distinguish availability changes from movement between buckets. These are observed score/price
availability changes, not confirmed listings, delistings or forced trades. Do not interpret the
first `lag` rows' structural counts as actual entries: their comparison status is
`boundary_excluded` because there is no earlier endpoint in the window.

### Time-series signal changes

For each asset, let S contain valid endpoint pairs `(a, b)` at the chosen lag:

$$
\begin{aligned}
\text{normalised change} &= \frac{\sum_S |a - b|}{\sum_S (|a| + |b|)/2} \\
\text{sign-change fraction} &= \frac{\#_S\{\operatorname{sign}(a)\operatorname{sign}(b) = -1\}}{|S|} \\
\text{zero-transition fraction} &= \frac{\#_S\{\text{exactly one endpoint equals zero}\}}{|S|}
\end{aligned}
$$

Normalised change is in **multiples of typical absolute signal over the lag**, without
annualisation. Its range is 0 to 2, and positive constant rescaling leaves it unchanged. It is a
ratio of sums, not an average of individual pair ratios. It depends on the signal's zero point.
Constant nonzero scores give zero; all-zero paired scores give `zero_signal` for normalised change
while both transition fractions are valid zeros. Pairs with two zero scores are included in
transition denominators. Too few pairs for `persistence.min_pairs` gives `insufficient_pairs` for
all three statistics. The default minimum is 2, a descriptive availability rule rather than a
statistical significance threshold.

## Aggregation and interpretation

Cross-sectional and bucket summary means weight valid timestamps equally; time-series summaries
weight assets with available statistics equally. They do not pool observations across assets. The
summary includes contributing and candidate counts. No confidence intervals or significance claims
are attached. Fractions are stored as decimals, lags as integer bars, and no quantity is annualised.
These diagnostics measure neither return nor portfolio turnover.

The older `time_series.assets.signal_autocorr_lag1` field remains unchanged for compatibility. It
uses that table's horizon-maturity sample and measures an asset's own score autocorrelation; the
cross-sectional rank statistic measures ordering across assets and uses all eligible endpoint pairs
independently of return horizons.

## Why score changes are not turnover

A score can stay constant while volatility scaling changes the position. Holdings also drift as
prices move, so the trade needed to reach a target depends on the holdings before the trade. Neither
effect is measured by score persistence. [Lim, Zohren and Roberts (2019, §VI)][lim] compute changes
in volatility-scaled exposure,
which depend on both the score and the volatility estimate. [Boyd et al. (2017, §§2.2–2.4)][boyd]
distinguish trades, transaction costs and holding costs in a portfolio accounting model. These
are quantities that score changes alone cannot supply; costs cannot be subtracted from IC.

The normalised-change statistic above is alphatonic's descriptive convention. Its symmetric
endpoint scale and lack of annualisation should be retained when comparing results. The cited
trading papers motivate examining exposure changes; they do not validate this statistic as a
cost estimator.

## References

- Alphalens Reloaded. [Performance source][alphalens], `factor_rank_autocorrelation` and
  `quantile_turnover`. Software conventions for endpoint ranks and bucket membership.
- Lim, B., Zohren, S. and Roberts, S. (2019). [Enhancing Time Series Momentum Strategies Using
  Deep Neural Networks][lim]. arXiv:1904.04912, revision 3 (2020), §VI.
- Boyd, S., Busseti, E., Diamond, S., Kahn, R. N., Koh, K., Nystrup, P. and Speth, J. (2017).
  [Multi-Period Trading via Convex Optimization][boyd]. *Foundations and Trends in Optimization*,
  3(1), 1–76, §§2.2–2.4.

[alphalens]: https://github.com/stefan-jansen/alphalens-reloaded/blob/main/src/alphalens/performance.py
[lim]: https://arxiv.org/html/1904.04912v3
[boyd]: https://web.stanford.edu/~boyd/papers/pdf/cvx_portfolio.pdf
