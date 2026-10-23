# Results and metrics

`evaluate` returns an [`Evaluation`](api.md): tables you can inspect, save and render. This
page defines every column, status and metric name.

Missing statistics are `NaN` in tables, blank in CSV files and omitted from `metrics()`. They
are never zero. Each row of the correlation tables has a `method`: `spearman` (the primary view) or
`pearson`.

## Cross-sectional tables

### `periods`

One row per timestamp and horizon, horizons in the configured order.

| Column | Contents |
| --- | --- |
| `timestamp` | The bar (UTC). |
| `horizon` | Label length in bars. |
| `spearman`, `pearson` | The IC at that timestamp, or `NaN`. |
| `n_available` | Assets with a price at the timestamp. |
| `n_signal` | Assets with a finite score. |
| `n_pairs` | Assets with a finite score **and** a label. |
| `pair_coverage` | `n_pairs / n_available`; `NaN` if no asset is available. It does not measure coverage of a historical universe. |
| `status` | `valid`, `insufficient_assets`, `constant_signal`, `constant_returns` or `disabled`. |

### `summary`

One row per horizon (ascending) and method; every statistic that cannot be computed is
absent (`NaN`).

| Column | Contents |
| --- | --- |
| `total_periods`, `n_periods`, `skipped_periods` | Timestamps, those with a valid IC, and those without. |
| `mean_pair_coverage`, `mean_n_pairs` | Averages over all timestamps. |
| `mean`, `std`, `positive_fraction` | Over valid timestamps, with equal weights. |
| `ic_ir` | `mean / std`, not annualised. |
| `hac_lags` | Lags used: `max(horizon − 1, L)`, where `L` is the `hac_lags` option or, by default, `floor(4·(n/100)^(2/9))` for `n` valid periods. |
| `hac_se`, `hac_z`, `hac_p_value` | Newey–West standard error of the mean, z-statistic and two-sided normal p-value. |
| `ci95_lower`, `ci95_upper` | `mean ± 1.96·hac_se`. |

### `quantiles`

Per valid timestamp and horizon: `quantile` (1 is the lowest score bucket), `mean_return` of
the bucket (`NaN` if empty) and `n_pairs`. The buckets are retrospective.

## Time-series tables

`assets`, `monthly` and `rolling` share these window columns:

| Column | Contents |
| --- | --- |
| `asset`, `horizon`, `method` | The row's keys. |
| `window_start`, `window_end` | The half-open window `[start, end)`. |
| `complete` | Whether the window lies fully inside the evaluation period. |
| `n_expected` | Bars whose label ends inside the window. |
| `n_pairs` | Of those, bars with a finite score and label. |
| `boundary_excluded` | Bars in the window whose label ends outside it. |
| `pair_coverage` | `n_pairs / n_expected`. |
| `status` | `valid`, `partial_window`, `short_window`, `insufficient_pairs`, `low_coverage`, `constant_signal` or `constant_returns` (first applicable). |
| `first_pair`, `last_pair` | First and last bar with a pair. |
| `ic` | The IC if `status` is `valid`, else `NaN`. |

`assets` is the full-period view, with extra columns:

| Column | Contents |
| --- | --- |
| `valid_months`, `skipped_months` | Complete UTC calendar months with and without a valid IC. |
| `monthly_mean_ic`, `monthly_std_ic`, `monthly_ic_ir` | Over valid months; the ratio needs `min_months` and variation. |
| `monthly_ir_status` | `insufficient_months`, `constant_ic`, `preliminary` (below twelve months) or `available`. |
| `ci95_lower`, `ci95_upper` | Percentile interval from the circular block bootstrap. |
| `bootstrap_valid`, `bootstrap_status`, `bootstrap_block_bars` | Draws used, outcome, block length. |
| `signal_autocorr_lag1` | Correlation of the asset's score with its previous bar's. |

### `summary` (time series)

One row per horizon and method, weighting eligible assets equally:

| Column | Contents |
| --- | --- |
| `n_assets`, `total_assets` | Assets with a valid full-period IC, and all assets. |
| `mean`, `median`, `q25`, `q75`, `positive_fraction` | Over eligible assets. Quartiles describe dispersion, not uncertainty. |
| `mean_pair_coverage` | Over all assets. |
| `universe_valid_months`, `universe_skipped_months`, `universe_monthly_mean_ic`, `universe_monthly_std_ic`, `universe_monthly_ic_ir`, `universe_monthly_ir_status` | Average the eligible assets' IC within each month first, then summarise across months. The asset set can change between months. |
| `ci95_lower`, `ci95_upper`, `bootstrap_*` | Interval for the mean asset IC, using one block resampling shared by all assets, and its status: `disabled`, `too_few_blocks`, `no_eligible_assets`, `insufficient_draws` or `valid`. |

### `quantiles` (time series)

Per eligible asset: `asset`, `horizon`, `quantile`, `mean_return`, `n_pairs`.

## Metrics

`result.metrics()` flattens the summaries to finite numbers named

```text
<mode>.h<horizon>.<method>.<statistic>
```

with mode `cs` or `ts`, horizon in bars, and method `spearman` or `pearson`. For example
`cs.h5.spearman.mean` is the mean cross-sectional rank IC at five bars, and `ts.h5.spearman.mean`
is the mean eligible asset time-series rank IC. They describe different samples. The statistics are
the columns of the two `summary` tables, so `cs.h5.spearman.hac_p_value` and
`ts.h5.pearson.n_assets` exist. String-valued columns (such as `bootstrap_status`) are omitted. In
`time_series` mode there are no `cs.` metrics.

## Files written by `save`

| Path | Contents |
| --- | --- |
| `evaluation.json` | `format_version`, `alphatonic_version`, the configuration, the window (`start`, `end`) and `bar_seconds` (null for irregular grids). |
| `ic_by_timestamp.csv`, `ic_summary.csv`, `cs_quantiles.csv` | `periods`, `summary`, `quantiles`. |
| `ic_monthly.csv` | The mean and count of `spearman` and `pearson` IC per horizon and UTC month. |
| `ts_assets.csv`, `ts_monthly.csv`, `ts_rolling.csv`, `ts_summary.csv`, `ts_quantiles.csv` | The time-series tables; absent in `cross_sectional` mode. |
