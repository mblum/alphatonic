# Troubleshooting

Start with the error message: input problems are raised as `ValueError` or `TypeError` before
anything is computed and say what to change. Everything else is a table: when a statistic is
missing, look for the `status` next to it.

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
| `factor assets have no prices and are ignored` (warning) | Some asset labels differ between the tables, or those assets have no price history. |
| `the factor has no finite scores` | Every score is `NaN` for the priced assets, usually a label mismatch. |
| `the window is empty` / `prices have no rows in the window` | `start` and `end` exclude every bar. |
| `pass either a config or keyword options, not both` | Use `evaluate(f, p, EvaluationConfig(...))` or `evaluate(f, p, horizons=...)`. |

## Unavailable cross-sectional IC

`result.periods` has one row per timestamp and horizon. The first applicable reason is stored
as `status`:

| Status | Meaning and next check |
| --- | --- |
| `valid` | An IC was computed. |
| `insufficient_assets` | Fewer than `min_assets` finite score/return pairs. Inspect missing scores, warmup, the unlabelled last bars, gaps and universe size. |
| `constant_signal` | All scores among the valid pairs are equal (often a rounded or capped factor). |
| `constant_returns` | All returns are equal (often stale or filled prices). |
| `disabled` | The mode is `time_series`. |

The last `delay + horizon` bars have no label, and an interior price gap removes every label
whose path crosses it.

## Unavailable time-series IC

`result.time_series.assets`, `monthly` and `rolling` carry a `status` for each asset and window:

| Status | Meaning and next check |
| --- | --- |
| `valid` | The IC was computed. |
| `partial_window` | The UTC month or rolling window is not fully inside the evaluation period. |
| `short_window` | The window holds fewer than `min_horizons × horizon` bars. Lower `min_horizons` or use longer windows. |
| `insufficient_pairs` | Fewer than `min_pairs` finite pairs after boundary exclusions. The default of 100 is high for daily bars and for monthly windows; see [choose an evaluation mode](choose-evaluation-mode.md). |
| `low_coverage` | Fewer than `min_coverage` of the window's bars have a finite pair. |
| `constant_signal` / `constant_returns` | No variation in that asset's sample. |

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
- **Wider intervals than another tool** are expected; see
  [migrate from alphalens](migrate-from-alphalens.md).
- **A suspiciously high IC** usually means look-ahead. Run the truncation check in
  [prepare factor and prices](prepare-inputs.md#check-a-factor-for-look-ahead), and confirm
  `delay` matches when the score is really known.

## Speed

Cross-sectional evaluation takes seconds for thousands of assets. If an evaluation is slow, it
is the time-series view: reduce `time_series.bootstrap_samples` (or set it to `0`), widen
`rolling_step`, or use `mode="cross_sectional"`. See the cost note in
[choose an evaluation mode](choose-evaluation-mode.md#make-the-time-series-view-fit-your-bar-size).
