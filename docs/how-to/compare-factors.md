# Compare factors and parameters

To rank several factors or parameter values, evaluate each one on identical inputs and compare the
flat `metrics()` of each result. Metric names follow `<cs|ts>.h<horizon>.<method>.<statistic>` (see
[results and metrics](../reference/results.md)); undefined statistics are omitted rather than
reported as zero.

```python
import pandas as pd

from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=60, n_bars=900, ic=0.03, seed=5)


def smoothed(window):
    """A trailing mean of the raw score: a simple one-parameter family."""
    return factor.rolling(window).mean()


start = prices.index[59]  # all smoothing windows have scores from this bar
rows = {}
for window in (1, 5, 10, 20, 60):
    result = evaluate(
        smoothed(window),
        prices,
        start=start,
        horizons=[5],
        time_series={"bootstrap_samples": 0},
    )
    rows[window] = result.metrics()

board = pd.DataFrame(rows).T[
    ["cs.h5.spearman.mean", "cs.h5.spearman.hac_z", "cs.h5.spearman.n_periods"]
]
print(board.sort_values("cs.h5.spearman.mean", ascending=False).round(4))
```

Keep everything but the thing you vary fixed: the same prices, universe, window, horizons, `delay`
and eligibility settings. The shared `start` above excludes the warm-up rows of the longest
smoothing window. Also compare coverage: a shared window does not guarantee the same usable pairs
when candidates have different missing scores.

## The more you try, the less a good number means

A p-value is a statement about one pre-specified test. Evaluate twenty factors that have no skill
and you may see p < 0.05 by chance:

```python
import numpy as np

rng = np.random.default_rng(0)
p_values = []
for _ in range(20):
    noise = pd.DataFrame(rng.normal(size=factor.shape), index=factor.index, columns=factor.columns)
    row = evaluate(noise, prices, horizons=[5], time_series={"bootstrap_samples": 0}).summary
    p_values.append(row.query("method == 'spearman'").hac_p_value.iloc[0])
print(f"smallest of 20 null p-values: {min(p_values):.3f}")
```

One call to `evaluate` cannot know how many alternatives you tried. Run the candidates through a
[study](run-a-study.md), which counts them, and:

- Hold out a final period that you evaluate **once**, after choosing: the study's
  `holdout_start`. Fix the model and parameter choices before the holdout; compute each holdout
  score using information available at its own timestamp.
- Apply a multiple-testing correction, such as the study's `adjusted_p` (Bonferroni: p times the
  number of candidates), or report the number of candidates beside the best result.
- Prefer parameters whose neighbours also work. An isolated peak deserves more scrutiny than a broad range of similar results.
- Overlapping labels are handled by the HAC estimate **within** one evaluation. They do not
  make different horizons independent evidence.
