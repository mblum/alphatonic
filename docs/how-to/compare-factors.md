# Compare factors and parameters

To rank several factors or parameter values, evaluate each one on identical inputs and compare
the flat `metrics()` of each result. Metric names follow `<cs|ts>.h<horizon>.<method>.<statistic>`
(see [results and metrics](../reference/results.md)); undefined statistics are omitted rather than
reported as zero.

```python
import pandas as pd

from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=60, n_bars=900, ic=0.03, seed=5)


def smoothed(window):
    """A trailing mean of the raw score: a simple one-parameter family."""
    return factor.rolling(window).mean()


rows = {}
for window in (1, 5, 10, 20, 60):
    result = evaluate(smoothed(window), prices, horizons=[5], mode="cross_sectional")
    rows[window] = result.metrics()

board = pd.DataFrame(rows).T[
    ["cs.h5.spearman.mean", "cs.h5.spearman.hac_z", "cs.h5.spearman.n_periods"]
]
print(board.sort_values("cs.h5.spearman.mean", ascending=False).round(4))
```

Keep everything but the thing you vary fixed: the same prices, universe, window, horizons,
`delay` and eligibility settings. A fair comparison also uses the same evaluation timestamps; here
the smoothed factors are missing for the first rows, so the windows differ slightly. Pass `start`
to give every candidate the same sample.

## The more you try, the less a good number means

A p-value is a statement about one pre-specified test. Evaluate twenty factors that have no
skill and one of them will have p < 0.05 by chance:

```python
import numpy as np

rng = np.random.default_rng(0)
p_values = []
for _ in range(20):
    noise = pd.DataFrame(rng.normal(size=factor.shape), index=factor.index, columns=factor.columns)
    row = evaluate(noise, prices, horizons=[5], mode="cross_sectional").summary
    p_values.append(row.query("method == 'spearman'").hac_p_value.iloc[0])
print(f"smallest of 20 null p-values: {min(p_values):.3f}")
```

alphatonic does not correct for this, because it cannot know how many alternatives you
tried. Count them yourself, and:

- Hold out a final period that you evaluate **once**, after choosing, with `start` set to its
  first row and your factor computed only from data before it.
- Apply a multiple-testing correction (for example Bonferroni: compare p to `0.05 / number of
  candidates`) or report the number of candidates beside the best result.
- Prefer parameters whose neighbours also work. A sharp peak at one value of a parameter is
  usually noise.
- Overlapping labels are handled by the HAC estimate **within** one evaluation. They do not
  make different horizons independent evidence.
