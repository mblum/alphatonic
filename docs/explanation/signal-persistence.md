# Signal persistence

Signal persistence measures how scores change before any portfolio is constructed. It is independent
of forward-return horizons, delay, targets, volatility warmup and return availability. These
diagnostics do not compute positions, traded notional, costs or P&L.

## Available diagnostics

Every new evaluation computes `result.persistence`. For a runnable example and settings, see
[measure signal persistence](../how-to/measure-persistence.md). The definitions below explain how
missing observations and changing asset sets affect the results.

An eligible score has a finite score and a price **at its own timestamp**. Each comparison uses
endpoints exactly `lag` rows apart on the price grid. It never drops missing rows before shifting. A
lag of 5 compares endpoints five bars apart, even if an interior bar is missing; it neither measures
the intervening path nor sums five one-bar changes. Both endpoints must be inside the evaluation
window; no score history before `start` is read. All timestamps through the last bar can contribute,
even when they have no future-return label.

### Cross-sectional rank persistence

Rank all eligible scores independently at each timestamp, using average ranks for ties. Compute
Pearson correlation of those ranks on the assets common to the two endpoints. This is the Alphalens
convention; with changing universes it need not equal re-ranking only the common assets. The common
sample needs `min_assets` and varying ranks at both endpoints. Values range from −1 (reversed
ordering) to 1 (preserved ordering). High persistence does not establish low dollar turnover:
weights, leverage and volatility scaling can still change.

### Bucket membership

Assign scores at each timestamp to `ceil(quantiles * average_rank / n_eligible)`. Ties stay together
and some buckets can be empty. Each endpoint must have at least `min_assets` and distinct scores.
For bucket Q, entry fraction is `|Q_now − Q_before| / |Q_now|`. A value of 0.2 means 20% of current
members were absent from the prior bucket. An empty current bucket is undefined; an empty prior
bucket at an otherwise eligible timestamp gives 1 for a nonempty current bucket.

Entry and exit counts are both reported: changes in bucket size can make them different. Counts of
bucket entrants absent from the prior eligible universe and exits absent from the current universe
distinguish availability changes from movement between buckets. These are observed score/price
availability changes, not confirmed listings, delistings or forced trades. Do not interpret the
first `lag` rows' structural counts as actual entries: their comparison status is
`boundary_excluded` because there is no earlier endpoint in the window.

### Time-series signal changes

For each asset, let S contain valid endpoint pairs `(a, b)` at the chosen lag:

```text
normalised change = sum_S |a − b| / sum_S ((|a| + |b|) / 2)
sign-change fraction = count_S(sign(a) * sign(b) == −1) / |S|
zero-transition fraction = count_S(exactly one endpoint equals zero) / |S|
```

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
effect is measured by score persistence. Costs require position rules, execution timing and an
asset-specific accounting model; they cannot be subtracted from IC.

The [reference-exposure proposal](../contributing/reference-exposures.md) records requirements for
possible future cost analysis. It is not implemented.

## Research basis

- [Alphalens performance source](https://github.com/stefan-jansen/alphalens-reloaded/blob/main/src/alphalens/performance.py): rank persistence and quantile membership conventions.
- [Lim, Zohren and Roberts, §VI](https://arxiv.org/html/1904.04912): changes in volatility-scaled exposure and cost sensitivity.
- [Boyd et al., §§2.2–2.4](https://web.stanford.edu/~boyd/papers/pdf/cvx_portfolio.pdf): traded notional, turnover conventions and separate trading/holding costs.
- [pysystemtrade turnover source](https://github.com/robcarver17/pysystemtrade/blob/master/syscore/pandas/strategy_functions.py): normalisation of position changes; its business-day annualisation is not used here.
