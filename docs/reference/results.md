# Results and metrics

`evaluate` returns an [`Evaluation`](api.md): tables you can inspect, save and render. This page
describes the result tables, status values, metric names and saved formats.

Missing statistics are `NaN` in tables, blank in CSV files and omitted from `metrics()`. They are
never replaced by zero. Summary and time-series tables have a `method` column: `spearman`,
`pearson`, or (time series only) `cosine`. The cross-sectional `periods` table stores `spearman` and
`pearson` as separate columns. Correlations are taken against each analysis's target: the forward
return, or the vol-scaled forward return (see [methodology](../explanation/methodology.md#targets)).

## In-memory labels

`result.forward_returns` maps each horizon to a DataFrame of raw forward returns on the evaluation
grid. These remain raw returns even when an analysis uses a volatility-scaled target.
`result.volatility` holds the one-bar volatility estimates when scaling is needed, otherwise `None`.
Neither is saved by `save()` or included in `to_dict()`.

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
| `status` | `valid`, `insufficient_assets`, `constant_signal`, `constant_returns`. |

### `summary`

One row per horizon (ascending) and method; every statistic that cannot be computed is absent
(`NaN`).

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

Per valid timestamp and horizon: `quantile` (1 is the lowest score bucket), `mean_return` of the
bucket (`NaN` if empty) and `n_pairs`. `mean_return` averages the cross-sectional target, so it is a
vol-scaled return when `target="vol_scaled"`. The buckets are retrospective.

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
| `long_fraction` | Share of the pairs with a positive score. |
| `status` | `valid`, `partial_window`, `short_window`, `insufficient_pairs`, `low_coverage`, then `constant_signal` or `constant_returns` for `spearman` and `pearson`, or `zero_signal` or `zero_returns` for `cosine` (first applicable). |
| `first_pair`, `last_pair` | First and last bar with a pair. |
| `ic` | The IC if `status` is `valid`, else `NaN`. |
| `ic_timing`, `ic_static` | For `cosine`: the parts of `ic` due to the covariance and to the means; they add up to `ic`. `NaN` for the other methods. |

`assets` is the full-period view, with extra columns:

| Column | Contents |
| --- | --- |
| `valid_months`, `skipped_months` | Complete UTC calendar months with and without a valid IC. |
| `monthly_mean_ic`, `monthly_std_ic`, `monthly_ic_ir` | Over valid months; the ratio needs `min_months` and variation. |
| `monthly_ir_status` | `insufficient_months`, `constant_ic`, `preliminary` (below twelve months) or `available`. |
| `ci95_lower`, `ci95_upper` | Percentile interval from the circular block bootstrap. |
| `bootstrap_valid`, `bootstrap_status`, `bootstrap_block_bars` | Draws used, outcome, block length. |
| `signal_autocorr_lag1` | Correlation of the asset's score with its previous bar's, by the row's method (uncentred for `cosine`). |

### `summary` (time series)

One row per horizon and method, weighting eligible assets equally:

| Column | Contents |
| --- | --- |
| `n_assets`, `total_assets` | Assets with a valid full-period IC, and all assets. |
| `mean`, `median`, `q25`, `q75`, `positive_fraction` | Over eligible assets. Quartiles describe dispersion, not uncertainty. |
| `mean_timing`, `mean_static` | For `cosine`: the mean of the assets' timing and static parts. `NaN` for the other methods. |
| `mean_pair_coverage` | Over all assets. |
| `universe_valid_months`, `universe_skipped_months`, `universe_monthly_mean_ic`, `universe_monthly_std_ic`, `universe_monthly_ic_ir`, `universe_monthly_ir_status` | Average the eligible assets' IC within each month first, then summarise across months. The asset set can change between months. |
| `ci95_lower`, `ci95_upper`, `bootstrap_*` | Interval for the mean asset IC, using one block resampling shared by all assets, and its status: `disabled`, `too_few_blocks`, `no_eligible_assets`, `insufficient_draws` or `valid`. |

### `quantiles` (time series)

Per asset with a valid Spearman IC: `asset`, `horizon`, `quantile`, `mean_return` (of the
time-series target), `n_pairs`.

## Metrics

`result.metrics()` flattens the summaries to finite numbers named

```text
<analysis>.h<horizon>.<method>.<statistic>
```

with analysis `cs` or `ts`, horizon in bars, and method `spearman`, `pearson` or (`ts` only)
`cosine`. For example `cs.h5.spearman.mean` is the mean cross-sectional rank IC at five bars, and
`ts.h5.spearman.mean` is the mean eligible asset time-series rank IC. They describe different
samples. The statistics are the columns of the two `summary` tables, so
`cs.h5.spearman.hac_p_value`, `ts.h5.pearson.n_assets` and `ts.h5.cosine.mean_static` exist.
String-valued columns (such as `bootstrap_status`) are omitted. Both analyses contribute their
available statistics.

Persistence metrics use a separate naming scheme; see [signal persistence](#signal-persistence).

## JSON documents

`result.to_dict()` and `study.to_dict()` return plain JSON values, for a page, a notebook widget or
another tool to read; the server sends the second as `/study.json`. Both pass `json.dumps(...,
allow_nan=False)`:

- a missing value is `null`, never `NaN` and never zero;
- timestamps are ISO 8601 strings in UTC, such as `2026-01-01T00:00:00+00:00`;
- durations are seconds;
- a table is an object of equally long columns, `{"column": [value, ...]}`, named and ordered as
  in the table above, so `pandas.DataFrame(table)` rebuilds it.

Each document starts with `format` and `format_version` (1). Fields may be added within a version;
renaming, removing or reinterpreting one increments it.

### `Evaluation.to_dict()`

| Field | Contents |
| --- | --- |
| `format` | `"alphatonic.evaluation"`. |
| `format_version`, `alphatonic_version` | The layout's version, and the version of alphatonic that wrote the document. |
| `config` | The configuration, as `EvaluationConfig.model_validate` reads it back. |
| `start`, `end`, `bar_seconds` | The window `[start, end)`, and the bar spacing (null for irregular grids). |
| `metrics` | `result.metrics()`. |
| `cross_section` | The tables `summary`, `periods` and `quantiles`. |
| `time_series` | The tables `assets`, `monthly`, `rolling`, `summary` and `quantiles`, or null. |
| `persistence` | The tables `periods`, `quantiles`, `assets` and `summary`, or null. |

Nothing is recomputed, so the document holds what the tearsheet draws. Forward returns and
volatilities are left out, as by `save`. The `rolling` table dominates its size, which grows with
assets, horizons and rolling windows: 30 assets, three horizons and 1,500 daily windows make about
120 MB of JSON.

### `Study.to_dict(horizon, sort=..., descending=...)`

| Field | Contents |
| --- | --- |
| `format` | `"alphatonic.study"`. |
| `format_version` | The layout's version. |
| `name`, `holdout_start` | The study's name and holdout boundary, or null. |
| `horizon`, `horizons` | The horizon of the statistics (default: the smallest), and the horizons of all trials. |
| `sort`, `descending` | The order of `trials`: a board column (default `created_at`) and its direction. |
| `context_keys` | The caller's context keys across all trials, in order of appearance. |
| `families` | Per family: `trials` and `holdout_uses`. |
| `trials` | One object per trial, in the board's order. |
| `unreadable` | Records that exist but cannot be read, relative to the study's directory. |

Each trial carries the record's `id`, `created_at`, `signal`, `family`, `summary`, `parameters`,
`note`, `sample`, `start`, `end`, `horizons`, `delay` and `bar_seconds`; the board's `assets` (a
count), `cs_ic`, `cs_z`, `cs_p`, `adjusted_p`, `ts_ic`, `ts_cosine`, `ts_timing`, `trials` and
`holdout_uses` at the document's horizon; its `context` as an object; and `files`, the paths of its
`record` and `tearsheet` relative to the study's directory. `tearsheet` is null if the trial has
neither a stored tearsheet nor tables to draw one from.

## Files written by `save`

| Path | Contents |
| --- | --- |
| `evaluation.json` | `format_version` (4, which gzips the tables; formats 1 to 3, which wrote plain CSV files, remain readable; format 1 is read with `return` targets, which it predates), `alphatonic_version`, the configuration, the window (`start`, `end`) and `bar_seconds` (null for irregular grids). |
| `ic_by_timestamp.csv.gz`, `ic_summary.csv.gz`, `cs_quantiles.csv.gz` | `periods`, `summary`, `quantiles`. |
| `persistence_periods.csv.gz`, `persistence_quantiles.csv.gz`, `persistence_assets.csv.gz`, `persistence_summary.csv.gz` | Signal persistence tables, written for new evaluations. |
| `ic_monthly.csv.gz` | The mean and count of `spearman` and `pearson` IC per horizon and UTC month. |
| `ts_assets.csv.gz`, `ts_monthly.csv.gz`, `ts_rolling.csv.gz`, `ts_summary.csv.gz`, `ts_quantiles.csv.gz` | The time-series tables, always written for new evaluations. |

Every table is gzip-compressed CSV. Formats 1 to 3 wrote the same tables as plain `.csv` files
(`ic_summary.csv`, and so on); they load as before.

## Files written by a study

Each trial of a `Study` is a directory named by its identifier, such as
`20260115-093012-momentum-3f9a2c`:

| Path | Contents |
| --- | --- |
| `record.json` | The trial's record, written last; a directory without one is an evaluation that did not finish. |
| `tables/` | The files written by `save`, reloadable with `Study.evaluation`. |
| `tearsheet.html` | The tearsheet, only if `Study.evaluate` was called with `report=True`. Otherwise `Study.render_tearsheet` and the server draw it from `tables/`. |

`record.json` holds these fields. Fields it does not know are ignored when it is read, and a record
without `family` is counted under its `signal`.

| Field | Contents |
| --- | --- |
| `format_version` | 1. |
| `id`, `created_at` | Identifier and creation time (UTC). |
| `signal`, `family`, `summary`, `parameters` | What was evaluated, the name its trials are counted under, a one-line description, the parameters. |
| `sample`, `holdout_start` | `in_sample` or `holdout`, and the study's holdout boundary at the time. |
| `start`, `end`, `horizons`, `delay` | The evaluated window `[start, end)` (UTC), horizons and delay in bars. |
| `assets`, `bar_seconds` | The assets of the price table, and the bar spacing (null if irregular). |
| `data_fingerprint` | SHA-256 fingerprint of the factor and price objects supplied to `Study.evaluate`, including rows outside the evaluation window. It does not store the data. |
| `versions` | alphatonic's version and any the caller added. |
| `context`, `note` | Facts and a note supplied by the caller. |
| `metrics` | The flat metrics above. |

`Study.board(horizon)` has one row per trial, indexed by `id`: `created_at`, `signal`, `family`,
`parameters`, `sample`, `start`, `end`, `assets` (a count), `bar`, `horizon`, then `cs_ic`, `cs_z`
and `cs_p` (mean cross-sectional Spearman IC, its Newey–West z-statistic and p-value), `adjusted_p`
(`cs_p` times `trials`, at most 1), `ts_ic`, `ts_cosine` and `ts_timing` (mean time-series Spearman
IC, cosine, and the cosine's timing part), `trials` and `holdout_uses` (per family), `note`, and one
column per context key.

## Signal persistence

`Evaluation.persistence` holds a `PersistenceEvaluation` with `periods`, `quantiles`, `assets` and
`summary` tables. It is `None` for older saved evaluations. These tables use no future-return labels
and have no horizon column. `persistence.lags` defaults to `(1, 5, 10)` price-grid bars;
`persistence.min_pairs` defaults to 2. Cross-sectional eligibility uses `min_assets`, and bucket
count uses `quantiles`. See [definitions and interpretation](../explanation/signal-persistence.md).

| Table | Keys | Values |
| --- | --- | --- |
| `periods` | `timestamp`, `lag` | `rank_autocorrelation`; current/prior/common eligible asset counts (`n_current`, `n_previous`, `n_common`); `pair_coverage = n_common / max(n_current, n_previous)`; eligible-universe `n_entries`, `n_exits`; `status`. |
| `quantiles` | `timestamp`, `lag`, `quantile` | `entry_fraction`; `n_current`, `n_previous`, `n_entries`, `n_exits`; `n_universe_entries`, `n_universe_exits` count bucket changes involving absent endpoint scores/prices; `status`. |
| `assets` | `asset`, `lag` | `normalized_change`, `change_status`; `sign_change_fraction`, `n_sign_changes`; `zero_transition_fraction`, `n_zero_transitions`; `n_pairs`, `n_expected = max(window_bars − lag, 0)`, `pair_coverage = n_pairs / n_expected`; `status` for transition metrics. |
| `summary` | `scope`, `lag`, `quantile`, `metric` | `mean`, `n_valid`, `n_total`, `status`. Scope is `cs`, `quantile` or `ts`; quantile 0 means not bucket-specific. CS/bucket candidates are all window timestamps (including boundary exclusions); TS candidates are all assets. |

Statuses: rank persistence uses `valid`, `boundary_excluded`, `insufficient_assets` or
`constant_signal`; bucket entry fraction uses `valid`, `boundary_excluded`, `ineligible_endpoint` or
`empty_quantile`. Asset transition metrics use `valid` or `insufficient_pairs`; `change_status`
additionally uses `zero_signal`. Summary status is `valid` if at least one statistic contributes,
otherwise `unavailable`. A zero denominator gives NaN. Counts remain descriptive even when a
comparison is unavailable; consult status before treating counts as transitions. Fractions are
decimals and no metric is annualised.

`metrics()` includes finite means and counts as
`persistence.<scope>.lag<lag>[.q<quantile>].<metric>.<mean|n_valid|n_total>`. Formats 3 and 4 save
four persistence tables (`persistence_*.csv.gz` in format 4); formats 1 and 2 remain readable
without them. The report renders stored tables without recomputing diagnostics.
