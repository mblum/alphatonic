# Migrate from alphalens

alphatonic takes the same two inputs as [alphalens](https://github.com/quantopian/alphalens)
(and its maintained fork, alphalens-reloaded): a factor and a table of prices. It is not a
drop-in replacement and does not copy its API. This page maps what you do today to what you do
here, lists what is different, and is honest about what alphatonic does not cover yet.

## The short version

=== "alphalens"

    <!-- notest -->
    ```python
    import alphalens

    factor_data = alphalens.utils.get_clean_factor_and_forward_returns(
        factor,  # Series indexed by (date, asset)
        pricing,  # DataFrame: dates x assets
        quantiles=5,
        periods=(1, 5, 10),
    )
    alphalens.tears.create_information_tear_sheet(factor_data)
    ```

=== "alphatonic"

    <!-- notest -->
    ```python
    import alphatonic

    result = alphatonic.evaluate(
        factor,  # the same Series, or a wide DataFrame
        pricing,  # the same DataFrame
        quantiles=5,
        horizons=(1, 5, 10),
    )
    result.tearsheet("tearsheet.html")
    ```

## Where each alphalens result lives

| alphalens | alphatonic |
| --- | --- |
| `factor_information_coefficient(factor_data)` | `result.ic()`: a timestamp × horizon table (Spearman by default, `"pearson"` available). |
| `mean_information_coefficient` | `result.summary` has the mean, standard deviation, ICIR and a 95% interval per horizon. |
| IC t-statistic and p-value in the summary table | `hac_z` and `hac_p_value` in `result.summary`, from a Newey–West standard error. |
| `mean_return_by_quantile` | `result.quantiles` (per timestamp) and, per asset, `result.time_series.quantiles`. |
| `create_information_tear_sheet` | `result.tearsheet(path)`, one HTML file. |
| `create_full_tear_sheet`, `create_returns_tear_sheet`, `create_turnover_tear_sheet`, `create_event_returns_tear_sheet` | Not provided. See below. |

Alphalens' quantile table is demeaned by the cross-sectional average return by default.
alphatonic's `quantiles` hold raw forward returns; demean them from the labels if you want that
view:

```python
import pandas as pd

from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=40, n_bars=500, ic=0.05, seed=1)
result = evaluate(factor, prices, horizons=[5], quantiles=5, mode="cross_sectional")

market = result.forward_returns[5].mean(axis=1)  # equal-weight average return per timestamp
buckets = result.quantiles.query("horizon == 5").copy()
buckets["excess"] = buckets["mean_return"] - buckets["timestamp"].map(market)
print(buckets.groupby("quantile")["excess"].mean().mul(1e4).round(1))  # basis points
```

## Differences you will notice

**Horizons count bars, not days.** `periods=(1, 5, 10)` and `horizons=(1, 5, 10)` mean rows of
the price table. On a table of trading days they are trading days. There is no frequency
inference, so a calendar with holidays needs no special handling.

**Timing is explicit.** The label of a score starts at the price of the same row; `delay`
adds bars between the two. If you adapted your prices for alphalens (for example, passing next-day
prices because the factor is known only after the close), remove that adjustment and use
`delay=1`, or leave the prices as they are and keep your convention. Check which one your
existing pipeline uses before comparing numbers.

**Uncertainty accounts for overlap.** Alphalens summarises IC with a plain t-test of its mean,
which assumes independent daily ICs. With 5- or 21-bar labels and persistent factors, adjacent ICs
are dependent, and that test is overconfident. alphatonic's interval uses at least
`horizon − 1` Newey–West lags. Expect wider intervals and larger p-values than you are used to.

**Missing data is visible.** Alphalens drops factor rows it cannot score and fails a run when
more than `max_loss` of the data goes. alphatonic keeps every timestamp, records a `status`
(`insufficient_assets`, `constant_signal`, ...) and counts skipped periods. A label also
needs an unbroken path of prices, so a gap removes every label that crosses it.

**Undefined is `NaN`.** A correlation that cannot be computed is never zero.

**No outlier filter or binning options.** There is no `filter_zscore`; buckets are formed by
rank with ties kept together, so there is no `bins` or `zero_aware`.

**Time-series IC is new.** Besides the cross-sectional IC, the default mode `both` also
correlates scores and returns over time inside each asset, with monthly, rolling and bootstrap
views. Use `mode="cross_sectional"` for the familiar view only.

## Not provided

Be aware of what you would lose by switching:

- Factor-weighted and long/short return series, cumulative returns, and alpha/beta.
- Quantile turnover and factor rank autocorrelation (alphatonic reports the one-bar
  autocorrelation of each asset's score in the time-series view).
- Group (sector) analysis, group-neutral IC and `binning_by_group`.
- Event studies.
- Jupyter-inline charts; the tearsheet is a standalone HTML page.

alphatonic measures predictive association. If you need portfolio-level performance, build the
portfolio in a backtester and keep alphatonic for the question "does this signal carry
information at all, and how sure are we?".
