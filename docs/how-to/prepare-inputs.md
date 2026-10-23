# Prepare factor and prices

`evaluate(factor, prices, ...)` needs two tables. This page defines what each must contain, how
alphatonic aligns them, and the mistakes that matter.

## The two tables

**Prices** is a `DataFrame` with one row per bar and one column per asset. The index is a
`DatetimeIndex`, sorted and unique, and the columns are unique asset labels. Values are positive,
finite prices; `NaN` marks a missing price. Use adjusted prices (splits and dividends) if you
want total-return labels. Prices and asset labels may be anything hashable: tickers, integers,
`venue:symbol` strings.

**Factor** holds the scores, larger meaning a higher expected return. Pass either layout:

=== "Wide"

    ```python
    import pandas as pd

    index = pd.date_range("2024-01-01", periods=4, freq="B")
    factor = pd.DataFrame(
        {"AAPL": [0.5, 0.1, -0.2, 0.3], "MSFT": [-0.4, 0.2, 0.0, 0.6], "XOM": [0.1, -0.3, 0.4, 0.2]},
        index=index,
    )
    print(factor)
    ```

=== "Long (alphalens layout)"

    ```python
    import pandas as pd

    index = pd.date_range("2024-01-01", periods=4, freq="B")
    wide = pd.DataFrame(
        {"AAPL": [0.5, 0.1, -0.2, 0.3], "MSFT": [-0.4, 0.2, 0.0, 0.6], "XOM": [0.1, -0.3, 0.4, 0.2]},
        index=index,
    )
    factor = wide.stack()  # a Series indexed by (timestamp, asset)
    print(factor.head())
    ```

A long `Series` needs a two-level index where one level holds timestamps (either order). `NaN` and
infinite scores mean "no score for this asset at this time". An asset or a timestamp without
a score is fine; a factor never needs the same shape as prices.

## How the two are aligned

- **Rows of `prices` are the bars.** Horizons and delays count rows, not clock time. A
  5-bar horizon on a table of trading days is a 5-trading-day return.
- **Scores must sit on rows that exist in `prices`.** A score on a timestamp without a price row
  is an error that names the first offending timestamp. Rows of the factor that are entirely
  `NaN` are ignored.
- **Factor assets without prices are dropped** with a warning. Priced assets without a
  factor column simply have no scores.
- **Timestamps are UTC.** Naive timestamps are read as UTC and timezone-aware ones are converted.
  Calendar months, used by the monthly time-series view, are UTC calendar months.
- **Inputs are never modified.** Nothing is forward-filled or interpolated.

## Choose the evaluation window

By default the window starts at the first timestamp with a finite score and ends one bar after
the last price. To evaluate a sub-period, pass `start` and `end`:

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=400, seed=1)
result = evaluate(factor, prices, start="2020-06-01", end="2021-06-01", horizons=[5])
print(result.start, result.end)
```

`start` is inclusive and `end` is exclusive. Prices at or after `end` are **ignored**, so no
label can look past the window: the last `delay + horizon` bars before `end` simply have no
label. History before `start` is only needed to compute your factor, and alphatonic does not read
it. This is what makes a train/test split safe: evaluate the held-out period with `start` set to
its first row and your factor already computed with data from before it.

## Timing: when is the score known?

A score at row `t` must be computable from information available **at the price of row `t`**.
The label starts from that same price. If your data is only available after the bar (a daily
signal computed after the close and traded at the next close), say so with `delay`:

```python
result = evaluate(factor, prices, horizons=[5], delay=1)
```

With `delay=1` the label for row `t` is the return from row `t+1` to row `t+1+5`. Never shift the
factor to "fix" timing without knowing which convention you are in; evaluating a leaked factor
gives impressive and worthless numbers.

### Check a factor for look-ahead

Recompute your factor on truncated history and compare it with the full-history value at the
same row. If they differ, the factor uses the future:

```python
import numpy as np


def momentum(prices, window=20):
    return prices / prices.shift(window) - 1


def assert_causal(compute, prices, cuts=(150, 250, 350)):
    full = compute(prices)
    for cut in cuts:
        truncated = compute(prices.iloc[:cut])
        np.testing.assert_allclose(
            truncated.iloc[-1].to_numpy(), full.iloc[cut - 1].to_numpy(), equal_nan=True
        )


assert_causal(momentum, prices)
```

This catches centered windows, `shift(-k)`, and statistics computed over the whole sample. It
cannot catch information you loaded from elsewhere (for example restated fundamentals).

## Calendars

Because rows are bars, nothing special is needed for equities: a table of trading days has no
weekend rows and a 5-bar horizon spans one trading week. The tearsheet then labels horizons
as "5 bars" without a clock duration, because the spacing is irregular.

For markets that trade around the clock (crypto, FX), a missing **row** would silently shorten a
horizon. Put missing bars on the grid first so a gap becomes a `NaN` price instead:

```python
regular = prices.asfreq("h")  # inserts NaN rows for missing hours; use your bar size
```

A `NaN` price removes every label whose path crosses it, so a gap never turns a 24-bar label into
a longer return. Evaluate the regular grid and the tearsheet reports durations such as
"24 bars · 1d".

## Universe and survivorship

alphatonic evaluates the assets you give it. If your universe contains only assets that
survived to today, IC is biased upward and no statistic can tell. Include assets that were
delisted, with their prices up to the end of trading.

A price that turns `NaN` after delisting removes every label that would end after it, so the
delisting return itself is **not** counted: the worst outcomes drop out of the sample, which is a
bias of its own. If delistings matter for your strategy, end such an asset's price series with a
value that reflects what a holder received (a delisting or liquidation price), rather than
`NaN`.

## Checklist

- Prices are positive, sorted, unique in time, one column per asset.
- The factor uses information available at the price of its row, or `delay` says otherwise.
- Gaps are `NaN`, not forward-filled values and not missing rows (on 24/7 markets).
- The universe includes assets that disappeared.
- You decided the window and any holdout **before** looking at results.
