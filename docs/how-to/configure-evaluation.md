# Configure an evaluation

Choose settings for your bar size, asset count and return target. Every evaluation runs both
analyses on the same input scores, with separate targets and eligibility rules;
[methodology](../explanation/methodology.md) defines the correlations and eligibility checks.

| Question | Analysis | Data requirement |
| --- | --- | --- |
| Do scores rank assets at the same timestamp? | Cross-sectional IC | At least `min_assets` finite pairs per timestamp, varying scores and returns. |
| Do scores predict an asset's returns over time? | Time-series IC | Enough history, coverage and variation within at least one asset. |

Use cross-sectional IC to assess asset rankings. Use time-series IC to assess each asset over time.
With fewer than three assets, only the time-series analysis can produce IC.

## Evaluate a single asset

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=1, n_bars=1500, ic=0.05, seed=3)
result = evaluate(factor, prices, horizons=[1])
print(result.time_series.summary.query("method == 'spearman'")[["horizon", "n_assets", "mean"]])
```

A single asset gives cross-sectional status `insufficient_assets` and can still produce a valid
time-series result. The tearsheet briefly explains the unavailable cross-sectional analysis and
keeps its sample diagnostics.

## Evaluate a small universe

The default cross-sectional minimum is five pairs. For a smaller universe, lower `min_assets` only
if you are prepared to interpret correlations from such small samples:

```python
small_factor, small_prices = synthetic_market(n_assets=3, n_bars=500, seed=3)
result = evaluate(small_factor, small_prices, min_assets=3)
```

`min_assets` cannot be lower than 3. Timestamps with fewer valid pairs are skipped, and their number
appears as `skipped_periods`; they are never counted as zero. With very few assets, rank
correlations take only a handful of discrete values, so read the interval, not the point estimate.

## Make the time-series view fit your bar size

The time-series view recomputes IC inside windows: the full period, each UTC calendar month, and
trailing windows. A window is only used if it is long enough to say something. The defaults require
100 finite pairs, 80% coverage, and a length of at least 20 horizons. They suit intraday bars; with
daily bars a calendar month has about 21 rows, so monthly IC is unavailable until you relax them.
`TimeSeriesOptions.for_bars` picks windows that fit the length of your bars:

```python
from alphatonic import TimeSeriesOptions

daily = TimeSeriesOptions.for_bars("1D")  # 15 pairs, 3 horizons, 90-day rolling windows
result = evaluate(factor, prices, horizons=[1, 5], time_series=daily)
```

Bars of 5 hours 45 minutes or shorter keep the defaults, because a 30-day window then holds enough
bars for 100 pairs at 80% coverage. Longer bars get `min_pairs` 15, `min_horizons` 3, and a 90-day
rolling window moved in 5-day steps. Keyword arguments replace any of these, for example a longer
calendar window for daily stock data:

```python
yearly = TimeSeriesOptions.for_bars("1D", rolling_window="365D", bootstrap_samples=0)
```

Lowering the requirements makes more windows eligible: a monthly IC from 15 observations is very
noisy. Longer horizons need longer windows; a 21-bar horizon never fits a 21-row month, so its
monthly view stays `short_window`, as intended.

| Bars | Suggested starting point |
| --- | --- |
| Minutes to a few hours | The defaults, which `for_bars` keeps. |
| 12-hour or daily | `for_bars`; raise `min_pairs` towards 30 and `rolling_window` towards 365D when the sample allows. |
| Weekly or monthly | Rely on the full-period IC and its bootstrap interval; windows are too short. |

The time-series target is vol-scaled by default, and its volatility estimate needs `vol_min_bars`
(20) one-bar returns. With daily bars that is about a month: supply prices from before `start` so
the first month keeps its pairs.

## Choose the target

Each analysis has its own target. The cross-section uses forward returns by default, which keeps the
rank IC comparable with published values. The time series uses forward returns divided by the
asset's estimated volatility over the horizon:

```python
scaled = evaluate(factor, prices, horizons=[1])  # vol-scaled by default
raw = evaluate(factor, prices, horizons=[1], time_series={"target": "return"})
```

`time_series.target` sets the time-series target and `target` the cross-sectional one, where
`target="vol_scaled"` gives a risk-adjusted IC. `vol_span` sets the span of the volatility estimate
(60 bars by default).

## Read the time-series cosine

Next to Spearman and Pearson, the time-series view reports the **cosine**, a correlation that does
not subtract means. It treats the score as a position and asks whether position times target is
positive on average, so a long-biased score earns the asset's drift. The cosine splits into a
**timing** part and a **static** part, the latter earned by the average position alone:

```python
cosine = scaled.time_series.assets.query("method == 'cosine'")
print(cosine[["asset", "ic", "ic_timing", "ic_static", "long_fraction"]])
```

A large static component means the average position explains much of the cosine. The [design
note](../explanation/targets-and-scaling.md) explains when each view applies.

## Cost

The time-series bootstrap is usually the most expensive step. Its cost grows with the number of
draws, assets, bars and horizons. The default is 1,000 draws. Use `time_series={"bootstrap_samples":
0}` for a quick comparison; this removes time-series confidence intervals but keeps point estimates,
windows, quantiles and sample diagnostics. Cross-sectional confidence intervals are unaffected.

Enable the bootstrap when you need its intervals. A nonzero `bootstrap_samples` must be at least
100. Increase `time_series.rolling_step` to compute fewer trailing windows.

Window settings such as `"30D"` and `"365D"` count calendar time, including weekends. Horizons,
delays and bootstrap block lengths count price rows. `for_bars` chooses a preset; it does not change
the grid or infer a trading calendar.

## Signal persistence

Set `persistence={"lags": [1, 5, 10], "min_pairs": 2}` to choose endpoint comparisons independently
of return horizons. Lags count rows of the price grid; `min_pairs` applies to each asset’s
descriptive statistics. See [measure signal persistence](measure-persistence.md).
