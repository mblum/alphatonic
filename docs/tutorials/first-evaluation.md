# Your first evaluation

In this tutorial you evaluate a factor on a simulated market, read the results, and write a
tearsheet. It takes about five minutes and needs no data. You need Python 3.11+ and:

```sh
python -m pip install "alphatonic"
```

## 1. Get a factor and prices

For this example, we use two tables of the same shape: a **factor** (a score per asset and
timestamp, larger meaning a higher expected return) and **prices** (one row per bar, one column per
asset). `alphatonic.demo` simulates both, with a factor that really does predict the next-bar
return:

```python
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=50, n_bars=750, ic=0.04, seed=7)
print(factor.iloc[:3, :3])
print(prices.shape, prices.index[0].date(), prices.index[-1].date())
```

The rows are 750 business days, the columns are 50 assets. The factor's population correlation with
the next day's return is set to 0.04. The measured IC will differ because the sample is finite and
Spearman uses ranks. With your own data you would pass your own tables; see [prepare factor and
prices](../how-to/prepare-inputs.md).

## 2. Evaluate

```python
from alphatonic import evaluate

result = evaluate(factor, prices, horizons=[1, 5, 21])
print(result)
```

`horizons` are in bars. Here the label of a score is the return over the next 1, 5 or 21 rows of
`prices`. The call also computes the time-series intervals used in step 5. The result contains
pandas tables. Start with the cross-sectional summary:

```python
cs = result.summary.query("method == 'spearman'")
print(cs[["horizon", "mean", "ci95_lower", "ci95_upper", "ic_ir", "hac_p_value", "n_periods"]])
```

Look for a positive mean rank IC at one bar and check whether its interval includes zero. Each row
is one horizon:

- `mean` is the average, over timestamps, of the Spearman correlation between scores and forward
  returns across the 50 assets.
- `ci95_lower` and `ci95_upper` come from a Newey–West standard error. Labels at longer
  horizons overlap, so adjacent ICs are dependent and a plain standard error would be too
  small when dependence is positive; see [methodology](../explanation/methodology.md).
- `ic_ir` is mean divided by standard deviation, **not** annualised.
- `n_periods` counts timestamps with a valid IC; the last 21 rows have no 21-bar label.

## 3. Look at the IC through time

```python
ic = result.ic()
print(ic.tail(3).round(3))
print(result.periods["status"].value_counts())
```

`result.ic()` returns one column per horizon and one row per timestamp. A cell is `NaN` when the IC
is undefined, and `periods["status"]` says why. Here the only skipped timestamps are those without a
label at the end of the sample.

## 4. Compare with a factor that has no skill

Now replace the signal with random scores and compare the results:

```python
import numpy as np
import pandas as pd

rng = np.random.default_rng(0)
noise = pd.DataFrame(rng.normal(size=factor.shape), index=factor.index, columns=factor.columns)
null = evaluate(noise, prices, horizons=[1, 5, 21], time_series={"bootstrap_samples": 0})
print(null.summary.query("method == 'spearman'")[["horizon", "mean", "ci95_lower", "ci95_upper"]])
```

The means should be near zero. Check the intervals too: noise can produce an interval that excludes
zero by chance, so this is a sanity check rather than a guarantee. `bootstrap_samples=0` skips the
time-series bootstrap for this comparison; both analyses still produce point estimates.

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

Each asset gets its own full-period IC and a block-bootstrap interval. The universe summary averages
the assets with equal weight.

The default settings need 100 pairs per window. A month of daily bars has too few, so this example
has no monthly or 30-day rolling IC. The full-period results can still be valid. The guide to
[configuring an evaluation](../how-to/configure-evaluation.md) shows the settings for daily data.

## 6. Write the tearsheet

```python
path = result.tearsheet("tearsheet.html", title="Demo factor", subtitle="synthetic, IC 0.04")
print(path)
```

Open `tearsheet.html` in a browser. It is one self-contained file: charts, tables and the
JavaScript that draws the charts. [Read a tearsheet](../how-to/read-a-tearsheet.md) walks through it.

## Where next

- Use your own data: [prepare factor and prices](../how-to/prepare-inputs.md).
- Keep the numbers: [save and reload results](../how-to/save-and-reload.md).
- Understand every statistic: [evaluation methodology](../explanation/methodology.md).
