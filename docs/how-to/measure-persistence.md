# Measure signal persistence

Use persistence diagnostics to check how quickly scores and asset rankings change. Choose lags in
price rows, independently of the return horizons:

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=8, n_bars=100, seed=7)
result = evaluate(
    factor,
    prices,
    horizons=[1, 5],
    persistence={"lags": [1, 5, 10], "min_pairs": 2},
    time_series={"bootstrap_samples": 0},
)
persistence = result.persistence
print(persistence.summary)
print(persistence.assets.query("lag == 1"))
```

`lag=5` compares scores five price rows apart. Both endpoints need a finite score and a price, but
an interior gap does not invalidate the comparison. The final bars can contribute even when they
have no forward-return label.

Choose the table for your question:

| Question | Table and field |
| --- | --- |
| Do assets keep their relative ranking? | `periods.rank_autocorrelation` |
| How many members are new to a score bucket? | `quantiles.entry_fraction` |
| How much does each asset's score change? | `assets.normalized_change` |
| How often does a score switch between positive and negative? | `assets.sign_change_fraction` |
| How often does a score move to or from zero? | `assets.zero_transition_fraction` |

Inspect `status` before interpreting a value. For normalised change, also inspect `change_status`:
all-zero scores have no normalised change but can have valid zero transition fractions. Increase
`persistence.min_pairs` if you want more endpoint pairs per asset. Cross-sectional comparisons use
the evaluation's `min_assets` setting.

The summary weights valid timestamps equally for cross-sectional measures and eligible assets
equally for time-series measures. Check `n_valid` against `n_total`; an average can be based on only
part of the sample. These are descriptive statistics with no confidence intervals.

Persistence is included in the tearsheet, saved results and `metrics()`. Older saved results may
have `persistence=None`. See the [table reference](../reference/results.md#signal-persistence) for
fields and [signal persistence](../explanation/signal-persistence.md) for formulas and limits.
