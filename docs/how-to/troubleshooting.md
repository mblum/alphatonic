# Troubleshooting

Start with the error message: input problems are raised as `ValueError` or `TypeError` before
anything is computed and say what to change. When a statistic is missing, inspect its sample status
and, for intervals, its inference status.

## Errors when you call `evaluate`

| Message | Meaning and action |
| --- | --- |
| `prices must be indexed by timestamps` | The index is not a `DatetimeIndex`. Convert it with `pd.to_datetime`. |
| `prices must be sorted by time` / `duplicate timestamps` | Call `sort_index()`; keep one row per bar. |
| `prices must be positive` | Returns are ratios. Mask zero or negative values with `NaN`. |
| `prices must be finite` | Replace infinities with `NaN`. |
| `a factor Series needs a two-level (timestamp, asset) MultiIndex` | Pass a wide DataFrame, or a Series with exactly one timestamp level and one asset level. |
| `the factor has scores at N timestamps that are not in prices` | The tables disagree on which bars exist. Reindex one to the other, or narrow `start` and `end`. |
| `no factor asset has prices` | The asset labels of the two tables do not match at all (for example integers against ticker strings). The message shows a few labels from each. |
| `factor assets have no prices and are ignored` (warning) | Some factor columns are absent from the price table. A matching column full of `NaN` is kept and yields missing pairs. |
| `the factor has no finite scores` | Every score is `NaN` for the priced assets, usually a label mismatch. |
| `the window is empty` / `prices have no rows in the window` | `start` and `end` exclude every bar. |
| `pass either a config or keyword options, not both` | Use `evaluate(f, p, EvaluationConfig(...))` or `evaluate(f, p, horizons=...)`. |

## Unavailable cross-sectional IC

`result.periods` has one row per timestamp and horizon. The first applicable reason is stored as
`status`:

| Status | Meaning and next check |
| --- | --- |
| `valid` | An IC was computed. |
| `insufficient_assets` | Fewer than `min_assets` finite score/return pairs. Inspect missing scores, warmup, the unlabelled last bars, gaps and universe size. |
| `constant_signal` | All scores among the valid pairs are equal (often a rounded or capped factor). |
| `constant_returns` | All returns are equal (often stale or filled prices). |

The last `delay + horizon` bars have no label, and an interior price gap removes every label whose
path crosses it.

## Unavailable time-series IC

`result.time_series.assets`, `monthly` and `rolling` carry a `status` for each asset and window:

| Status | Meaning and next check |
| --- | --- |
| `valid` | The IC was computed. |
| `partial_window` | The UTC month or rolling window is not fully inside the evaluation period. |
| `short_window` | The window holds fewer than `min_horizons × horizon` bars. Lower `min_horizons` or use longer windows. |
| `insufficient_pairs` | Fewer than `min_pairs` finite pairs after boundary exclusions. The default of 100 is high for daily bars and for monthly windows; see [configure an evaluation](configure-evaluation.md). |
| `low_coverage` | Fewer than `min_coverage` of the window's bars have a finite pair. |
| `constant_signal` / `constant_returns` | No variation in that asset's sample (Spearman and Pearson). The cosine accepts a constant score. |
| `zero_signal` / `zero_returns` | Every score, or every target, is zero (cosine). |

With the default vol-scaled time-series target, a bar has a target only once its asset has
`vol_min_bars` one-bar returns. If prices begin at the window's start, the first windows lose those
bars and can turn `low_coverage` or `insufficient_pairs`; pass prices from before `start` (they are
read only to estimate volatility), lower `vol_min_bars`, or set `time_series={"target": "return"}`.
A `vol_scaled` cross-sectional target loses the same bars, which shows as `insufficient_assets` at
the start.

## Missing ratios and intervals

- **ICIR** is undefined for a constant IC series. HAC inference also needs more observations
  than its lag count permits. A valid IC can exist without either.
- **Monthly TS ICIR** needs `min_months` complete valid months and variation across them. Its
  status is `insufficient_months`, `constant_ic`, `preliminary` (fewer than twelve) or
  `available`.
- **Bootstrap intervals** report `bootstrap_status`: `disabled` (`bootstrap_samples=0`),
  `too_few_blocks` (less than five blocks of history; shorten `block_bars` or lengthen the
  sample), `no_eligible_assets`, `insufficient_draws`, or `valid`.
- In `result.metrics()` missing statistics are omitted; in CSVs they are blank. They are never
  zeros.

## Surprising results

- **An IC of exactly 0.0** is real: tiny samples have discrete rank correlations, and
  values within 1e-12 of zero are reported as zero so rounding error cannot decide whether a period
  counts as positive.
- **Wider intervals than an independence-based estimate** can result from positive temporal dependence.
  The Newey–West standard error accounts for this; see
  [methodology](../explanation/methodology.md#summary-statistics-and-inference).
- **A suspiciously high IC** warrants a timing and data check. Run the truncation check in
  [prepare factor and prices](prepare-inputs.md#check-a-factor-for-look-ahead), and confirm
  `delay` matches when the score is really known.

## Speed

The time-series bootstrap is usually the largest cost. To reduce it, reduce
`time_series.bootstrap_samples` (or set it to `0`) or widen `time_series.rolling_step`. Both
analyses always run; disabling the bootstrap keeps their point estimates. See the cost note in
[configure an evaluation](configure-evaluation.md#cost).
