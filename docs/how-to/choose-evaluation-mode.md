# Choose an evaluation mode

`mode` selects which relationship to measure. Both modes read the same factor and forward
returns; [methodology](../explanation/methodology.md) defines the correlations and eligibility checks.

| Question | `mode` | Data requirement |
| --- | --- | --- |
| Do scores rank assets at the same timestamp? | `cross_sectional` | At least `min_assets` finite pairs per timestamp, varying scores and returns. |
| Do scores predict an asset's returns over time? | `time_series` | Enough history, coverage and variation within at least one asset. |
| Do both hold? | `both` (default) | Either mode can validate a horizon; inspect each separately. |

Cross-sectional IC is the standard measure for stock selection and long/short portfolios: it
cannot be earned by predicting the market's direction, because every timestamp is compared only
with itself. Time-series IC is the natural measure for timing a single instrument, or a few that
share a common driver, and it is the only one available with fewer than three assets.

## Evaluate a single asset

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=1, n_bars=1500, ic=0.05, seed=3)
result = evaluate(factor, prices, horizons=[1], mode="time_series")
print(result.time_series.summary.query("method == 'spearman'")[["horizon", "n_assets", "mean"]])
```

The cross-sectional tables still exist in `time_series` mode, with every status `disabled`.
In `both` mode a single asset gives cross-sectional status `insufficient_assets` and a valid
time-series result.

## Evaluate a small universe

For three or more overlapping assets use `both` and set the minimum cross-section to what you
can defend:

```python
result = evaluate(factor, prices, mode="both", min_assets=3)
```

`min_assets` cannot be lower than 3. Timestamps with fewer valid pairs are skipped, and their
number appears as `skipped_periods`; they are never counted as zero. With very few assets, rank
correlations take only a handful of discrete values, so read the interval, not the point
estimate.

## Make the time-series view fit your bar size

The time-series view recomputes IC inside windows: the full period, each UTC calendar month,
and trailing windows. A window is only used if it is long enough to say something. The
defaults require 100 finite pairs, 80% coverage, and a length of at least 20 horizons. They suit
intraday bars; with daily bars a calendar month has about 21 rows, so monthly IC is unavailable
until you relax them:

```python
daily = {
    "min_pairs": 15,  # pairs a window needs
    "min_horizons": 3,  # window length in multiples of the horizon
    "min_months": 6,  # complete months before a monthly ICIR is computed
    "rolling_window": "90D",
    "rolling_step": "5D",
}
result = evaluate(factor, prices, horizons=[1, 5], time_series=daily)
```

Relaxed settings buy availability, not accuracy: a monthly IC from 15 observations is very
noisy. Longer horizons need longer windows; a 21-bar horizon never fits a 21-row month, so its
monthly view stays `short_window`, as intended.

| Bars | Suggested starting point |
| --- | --- |
| Minutes to hours | The defaults. |
| Daily | `min_pairs` 15–30, `min_horizons` 3, `rolling_window` 90D–252D. |
| Weekly or monthly | Rely on the full-period IC and its bootstrap interval; windows are too short. |

## Cost

Cross-sectional evaluation is vectorised: 3,000 assets by 2,500 daily bars at three horizons
takes seconds. The time-series block bootstrap redraws the data `bootstrap_samples` times and
recomputes every asset's correlation each time, so its cost grows with draws × assets × bars (for
500 assets and 2,500 bars about a third of a second per draw and horizon). Set
`time_series={"bootstrap_samples": 0}` while exploring and switch it on for the run you keep.
`mode="cross_sectional"` skips the time-series work altogether.
