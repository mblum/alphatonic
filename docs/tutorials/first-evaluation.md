# Your first evaluation

In this tutorial you evaluate a factor on a simulated market, read the results, and write a
tearsheet. It takes about five minutes and needs no data. You need Python 3.11+ and:

```sh
pip install "alphatonic[report] @ git+https://github.com/mblum/alphatonic"
```

## 1. Get a factor and prices

An evaluation needs two tables of the same shape: a **factor** (a score per asset and
timestamp, larger meaning a higher expected return) and **prices** (one row per bar, one column
per asset). `alphatonic.demo` simulates both, with a factor that really does predict the
next-bar return:

```python
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=50, n_bars=750, ic=0.04, seed=7)
print(factor.iloc[:3, :3])
print(prices.shape, prices.index[0].date(), prices.index[-1].date())
```

The rows are 750 business days, the columns are 50 assets. The factor's population correlation
with the next day's return is 0.04, a realistic strength for a good signal. With your own data you
would pass your own tables; see [prepare factor and prices](../how-to/prepare-inputs.md).

## 2. Evaluate

```python
from alphatonic import evaluate

result = evaluate(factor, prices, horizons=[1, 5, 21])
print(result)
```

`horizons` are in bars. Here the label of a score is the return over the next 1, 5 or 21 rows
of `prices`. This takes about ten seconds, most of it the bootstrap behind the time-series intervals in step 5
(`time_series={"bootstrap_samples": 0}` skips it). The result holds tables, nothing more:

```python
cs = result.summary.query("method == 'spearman'")
print(cs[["horizon", "mean", "ci95_lower", "ci95_upper", "ic_ir", "hac_p_value", "n_periods"]])
```

Expect a mean rank IC near 0.04 at one bar, with a 95% interval that excludes zero. Each row is
one horizon:

- `mean` is the average, over timestamps, of the Spearman correlation between scores and forward
  returns across the 50 assets.
- `ci95_lower` and `ci95_upper` come from a Newey–West standard error. Labels at longer
  horizons overlap, so adjacent ICs are dependent and a plain standard error would be too
  small; see [methodology](../explanation/methodology.md).
- `ic_ir` is mean divided by standard deviation, **not** annualised.
- `n_periods` counts timestamps with a valid IC; the last 21 rows have no 21-bar label.

## 3. Look at the IC through time

```python
ic = result.ic()
print(ic.tail(3).round(3))
print(result.periods["status"].value_counts())
```

`result.ic()` returns one column per horizon and one row per timestamp, the layout alphalens users
know. A cell is `NaN` when the IC is undefined, and `periods["status"]` says why. Here the only
skipped timestamps are those without a label at the end of the sample.

## 4. Compare with a factor that has no skill

The most useful sanity check of any evaluation tool is to feed it noise:

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(0)
noise = pd.DataFrame(rng.normal(size=factor.shape), index=factor.index, columns=factor.columns)
null = evaluate(noise, prices, horizons=[1, 5, 21], mode="cross_sectional")
print(null.summary.query("method == 'spearman'")[["horizon", "mean", "ci95_lower", "ci95_upper"]])
```

The means sit near zero and every interval straddles it. `mode="cross_sectional"` skips the
time-series view, which this step does not need.

## 5. The time-series view

The first evaluation also asked a second question: does each asset's own score predict its own
return over time?

```python
ts = result.time_series
print(
    ts.summary.query("method == 'spearman'")[
        ["horizon", "n_assets", "mean", "ci95_lower", "ci95_upper"]
    ]
)
print(
    ts.assets.query("method == 'spearman' and horizon == 5")[
        ["asset", "ic", "ci95_lower", "ci95_upper"]
    ].head()
)
```

Each asset gets its own full-period IC and a block-bootstrap interval. The universe summary
averages the assets with equal weight.

With daily bars, the monthly and rolling views are mostly "unavailable" under the default
eligibility rules, which are tuned for intraday bars (100 pairs per window). That is by design, and
[choose an evaluation mode](../how-to/choose-evaluation-mode.md) shows the settings for daily data.

## 6. Write the tearsheet

```python
path = result.tearsheet("tearsheet.html", title="Demo factor", subtitle="synthetic, IC 0.04")
print(path)
```

Open `tearsheet.html` in a browser. It is one self-contained file: charts, tables and Plotly's
JavaScript. [Read a tearsheet](../how-to/read-a-tearsheet.md) walks through it.

## Where next

- Use your own data: [prepare factor and prices](../how-to/prepare-inputs.md).
- Keep the numbers: [save and reload results](../how-to/save-and-reload.md).
- Understand every statistic: [evaluation methodology](../explanation/methodology.md).
