# Testing alphatonic

This testing strategy was built from the production code and published testing guidance,
reviewed on 1 November 2026. The replacement suite follows the levels and layout below. The
inventory describes the evidence to maintain and extend; coverage alone does not establish
that every adversarial case or statistical regime has been validated.

The production path is `evaluate()` → input alignment → return labels and optional volatility
scaling → cross-sectional IC, time-series IC and signal persistence. Results also pass through
versioned file storage, JSON export, `Study`, HTML rendering, a local HTTP server and a CLI.
Test effort should follow the consequences of a failure along those paths.

## 1. Testing objectives

The suite should provide evidence for these guarantees:

| Guarantee | Required evidence |
| --- | --- |
| Correct numbers | Hand-calculated examples, independent numerical oracles and generated comparisons for correlations, ranks, buckets, summaries and uncertainty. |
| Correct time boundaries | Exact bar-based horizons and delays; half-open evaluation windows; no labels ending outside a window; volatility using information available at the score timestamp. |
| Honest missingness | Undefined estimates remain missing, with the appropriate status or documented omission. Counts, coverage and inference availability explain what contributed. A genuine zero remains distinguishable from an undefined value. |
| Dependence-aware uncertainty | Formula checks and calibration experiments for cross-sectional Newey–West inference, time-series equal-weighted cosine inference and paired circular block bootstrap. |
| Reproducible results | Explicit local random generators; repeatable results with the same options; independence from test order, parallel workers and unrelated random draws. |
| Durable research records | Readable historical formats, faithful exports and reloads, preserved trial counts, enforced holdout boundaries and visible unreadable records. |
| Faithful presentation | JSON, tables and charts agree about estimates, units, intervals and missingness. A saved tearsheet works offline without recomputing inference. |
| Reliable interfaces | Public imports, installed package resources, both CLI entry points and documented workflows work in supported environments. Invalid input fails clearly. |

These are bounded guarantees. Calibration applies to the data-generating mechanisms and sample
sizes tested; it does not establish validity under arbitrary non-stationarity or missingness.
The library cannot establish that a caller's factor was constructed without future information,
or that a predictive association will make a profitable strategy. Tests must distinguish those
claims from the library's own alignment and inference responsibilities.

Use a failing regression test for each defect and executable examples for each new public
behaviour. This follows [NumPy's testing guidance](https://numpy.org/doc/stable/reference/testing.html),
which calls for normal, erroneous and unexpected input cases as well as regression coverage.

## 2. Test levels

Use the smallest level that can demonstrate a guarantee. A large number of numerical and
validation tests should support a small number of complete user journeys. The following
definitions make component and integration tests distinct for this library.

| Level | Boundary and real dependencies | Examples |
| --- | --- | --- |
| Unit | One function or validation rule; real NumPy and pandas where used. | Pairwise ranking, a delayed return with an interior gap, a HAC sum, a configuration bound, strict JSON conversion. |
| Component | One coherent subsystem through its normal interface, including its internal helpers. | All cross-sectional tables; all TS windows and inference; persistence diagnostics; evaluation save/load; a study board; report specifications; `respond()` routing without a socket. |
| Integration | Cooperation between subsystems or a real operating-system boundary. | `evaluate()` with both target types; study → saved tables → reload → report; actual HTTP GET/HEAD; CLI subprocess; installed wheel resources. |
| End-to-end | A complete process or browser journey using the installed package. | Create trials through Python, run `alphatonic serve`, sort the board, open a lazily rendered tearsheet and download it; open a standalone report with networking disabled. |
| Acceptance | A researcher-facing requirement expressed through public interfaces and independently specified expected outcomes. | A constant factor has unavailable centred IC; a holdout boundary cannot be crossed; every completed variant contributes to its family's trial count. |

Acceptance is a purpose rather than a reason to launch a browser. Keep numerical acceptance
tests at the public Python API unless a requirement is specifically about the UI. Statistical
calibration, property tests, compatibility checks and performance checks cut across these levels;
they are separately selectable workloads, not additional definitions of “unit test”.

Minimum acceptance scenarios:

1. **Known association:** hand-built prices and scores give the specified positive, negative
   or zero IC, with exact pair counts. Include separate CS and TS examples.
2. **Unavailable association:** missing data, insufficient pairs and constant scores produce
   the intended missing estimates and reasons. A constant non-zero position can have a valid
   cosine even when Pearson and Spearman are undefined.
3. **Bounded evaluation:** changing prices after an explicit evaluation end cannot affect its
   numerical tables; no return ending on or after that end contributes.
4. **Research history:** repeated evaluations with identical parameters create distinct trials;
   family counts and holdout uses include every completed trial across both samples.
5. **Durable result:** saving and loading preserves stored statistics and permits JSON export
   and report rendering without the original market data.
6. **Usable report:** missing values remain gaps or unavailable labels in an offline report;
   the board retains multiple-testing context when estimates are displayed.

## 3. Test organization and source-derived inventory

### Proposed layout and naming

Keep tests outside `src/` and import the installed package. Use pytest's `importlib` import mode
so collection does not silently alter the import path; this layout also supports testing wheels.
See [pytest's integration guidance](https://docs.pytest.org/en/stable/explanation/goodpractices.html).

```text
tests/
  __init__.py
  conftest.py                    # small shared fixture interfaces
  support/
    __init__.py
    panels.py                   # independent synthetic-data builders
    oracles.py                  # deliberately simple mathematical implementations
    strategies.py               # Hypothesis input strategies
    assertions.py               # schema, missingness and numerical comparisons
  data/
    evaluations/                # immutable examples of readable file formats
    studies/                    # versioned trial-record examples
    exports/                    # small JSON contract examples
    MANIFEST.md                 # origin, writer version and expected semantics
  unit/
    test_config.py
    test_inputs.py
    test_returns.py
    test_stats.py
    test_export.py
    test_progress.py
    test_demo.py
    report/
      test_figures.py
      test_ts_figures.py
      test_board_values.py
  component/
    test_cross_section.py
    test_time_series.py
    test_signal_persistence.py
    test_evaluation.py
    test_persistence.py
    test_study.py
    test_report.py
    test_server.py
  integration/
    test_evaluation_io.py
    test_study_workflow.py
    test_http_server.py
    test_cli.py
    test_imports.py
    test_distribution.py
    test_documentation.py
  e2e/
    test_offline_tearsheet.py
    test_study_browser.py
  acceptance/
    test_research_contracts.py
  statistical/
    test_calibration.py
benchmarks/
  test_evaluation_performance.py
  test_report_performance.py
```

Name tests `test_<behaviour>_<condition>_<outcome>`, for example
`test_forward_returns_interior_gap_has_no_label`. Parametrized cases need descriptive IDs such
as `delay-2-gap-before-entry`, not only numeric positions. Import shared helpers explicitly
from `tests.support`; tests must not import other test modules.

The mapping below assigns ownership. A subsystem's exhaustive cases belong to its unit or
component tests; integration tests assert the joining contract instead of repeating every case.

| Production source | Primary test ownership | Additional boundary checks |
| --- | --- | --- |
| `config.py` | `unit/test_config.py` | Configuration through `evaluate()` and persisted options. |
| `inputs.py` | `unit/test_inputs.py` | Alignment through `component/test_evaluation.py`. |
| `returns.py` | `unit/test_returns.py` | Delays, target selection and history through evaluation. |
| `stats.py` | `unit/test_stats.py` | CS/TS component tests; calibration experiments. |
| `cross_section.py` | `component/test_cross_section.py` | Public evaluation and acceptance examples. |
| `time_series.py` | `component/test_time_series.py` | Target routing, statistical calibration and saved tables. |
| `signal_persistence.py` | `component/test_signal_persistence.py` | Evaluation, saved tables, metrics and reports. |
| `evaluation.py` | `component/test_evaluation.py` | `integration/test_evaluation_io.py`; acceptance. |
| `persistence.py` | `component/test_persistence.py` | Historical files and cross-version round trips. |
| `export.py` | `unit/test_export.py` | Evaluation/study JSON and HTTP JSON responses. |
| `study.py` | `component/test_study.py` | `integration/test_study_workflow.py`; acceptance. |
| `report/figures.py`, `report/ts_figures.py` | `unit/report/` | Report JSON specifications and browser charts. |
| `report/__init__.py`, `report/page.py`, templates and owned static assets | `component/test_report.py` | Distribution resources, offline and served browser journeys. |
| `report/board.py`, board template | `unit/report/test_board_values.py`; report component tests | Query parameters, HTTP responses and browser navigation. |
| `server.py` | `component/test_server.py` | Real HTTP in `integration/test_http_server.py`. |
| `cli.py`, `__main__.py` | `integration/test_cli.py` | Installed console script and server process lifecycle. |
| `__init__.py`, `py.typed`, package metadata | `integration/test_imports.py`; distribution tests | Fresh-interpreter imports and consumer installation. |
| `progress.py`, `demo.py` | Matching unit files | Progress callbacks during evaluation; tutorial smoke checks. |

### Priority 0: numerical and temporal correctness

These cases are necessary before relying on evaluation results.

**Configuration and inputs (`config.py`, `inputs.py`).**

- Exercise each declared bound, literal, uniqueness rule and frozen/extra-field rule, including
  nested options. Check exact boundaries: positive horizons/lags; duplicate values; minimum asset
  and pair counts; coverage; non-negative delay and seed; bootstrap counts of 0, 1, 99 and 100.
  Check boolean rejection for `PositiveInt` fields and document which coercions are accepted.
- Validate positive fixed durations, invalid/non-fixed durations, `NaT`, UTC conversion and
  `start < end`. Check `TimeSeriesOptions.for_bars()` just below, at and above its preset
  threshold, and that explicit overrides win.
- Compare a wide factor with equivalent long Series in either index-level order. Cover unsorted
  factor rows, unsorted price rejection, duplicate timestamps/assets/pairs, invalid index types,
  `NaT`, multi-level columns, non-numeric values and accepted numeric conversion.
- Verify naive timestamps mean UTC; equivalent aware timestamps give the same grid, including
  daylight-saving transitions and differing datetime resolutions.
- Check price rejection for infinities, zero and negative values; score infinities become
  missing. Exercise empty/no-finite-score inputs, too few price rows, no matching assets and
  windows with no bars. Assert the intended exception rather than accepting an arbitrary crash.
- Check partial asset overlap, its explicit warning, and price-column ordering after alignment.
  Assets with prices but no scores remain visible as unavailable assets.
- Check explicit/default window bounds, regular/irregular grid detection, pre-start history,
  finite scores off the price grid, and all-missing off-grid rows. No implicit filling or row
  compression is allowed. Inputs must remain unchanged after success and failure.

**Labels and ex-ante volatility (`returns.py`, `evaluation._targets`).**

- For row `t`, independently calculate `P[t + delay + h] / P[t + delay] - 1`. Use horizons 1
  and greater than 1, delays 0 and greater than 0, horizons longer than the panel and an
  irregular timestamp grid. The final `delay + h` rows have no labels.
- Put a missing price at every position from `t` through `t + delay + h`, including before
  delayed entry. Every affected label must be missing, even when both ratio endpoints exist.
  Price absence for one asset must not affect another.
- Verify label-end timestamps and exact exclusion when a label ends at the exclusive end of
  an evaluation, calendar month or rolling window.
- Compute a small exponentially weighted volatility example independently, with its actual
  weighting and sample correction. Test warm-up, constant prices, gaps and non-finite ratios.
  Pre-start prices may warm volatility; post-score prices may not affect that score's estimate.
- Verify scaling by `volatility * sqrt(h)`, missing/zero volatility and overflow masking. Test
  all four combinations of CS and TS targets (`return`/`vol_scaled`), checking that raw stored
  forward returns remain raw and volatility is absent when neither analysis needs it.

**Numerical primitives (`stats.py`).**

- Compare Pearson, Spearman and cosine with independent scalar definitions on complete and
  pairwise-missing samples. Spearman must rank only the surviving pairs, with average ranks
  for ties. Include positive/negative perfection, genuine zero, fewer than three pairs,
  constants such as repeated `0.1`, zero vectors and large finite magnitudes.
- Check `average_ranks`, row/column orientation, singleton dimensions and chunk boundaries at
  `BLOCK_ROWS - 1`, `BLOCK_ROWS` and `BLOCK_ROWS + 1`. Compare contiguous and strided arrays.
  Assert output shapes and missingness independently of approximate value comparisons.
- Verify the cosine's static term from population moments, and that timing plus static equals
  cosine. Centred correlations require variation; cosine requires non-zero norms instead.
- Compare `ResampledCorrelations` with explicitly repeated rows for integer multiplicities,
  including zeros, duplicate draws, resampled ties and draws that become constant. Re-rank
  each Spearman resample; ranking once before resampling is not an equivalent oracle.
- Check `standardized_products`: products sum to `count * correlation` for eligible columns;
  missing rows contribute zero while retaining their original positions. Exercise degenerate
  columns separately from that identity.
- Calculate bucket membership from average paired ranks and `ceil(Q * rank / n)`. Check tied
  scores, more buckets than pairs, empty buckets, constant scores and missing targets. Occupied
  bucket counts conserve pairs; unoccupied means are missing, not zero.
- Check `summarize_ic` by a direct Bartlett-weighted covariance sum, preserving the positions
  of missing periods and using the valid-observation denominator and finite-sample correction.
  Cover zero/one/two valid observations, constant IC, zero standard error, `n <= lags + 1`,
  explicit/default lags and the cross-sectional floor `h - 1`. Missing inference keys at the
  primitive level must become missing table values or documented metric omissions downstream.
- Compare FFT-based EWC long-run variance with direct cosine projections. Verify `ewc_dof`
  at integer-floor boundaries and its horizon cap, including zero degrees of freedom. The
  [Lazarus et al. paper](https://stock.scholars.harvard.edu/publications/har-inference-recommendations-practice)
  motivates EWC inference; alphatonic's additional horizon cap needs its own tests.
- Compare custom Student t p-values with `2 * scipy.stats.t.sf(abs(t), dof)` across degrees of
  freedom, values near zero, moderate/extreme tails, both signs, infinity and `NaN`. Include
  analytic values at one degree of freedom and high-precision tail fixtures, so an external
  implementation is not the sole oracle. Use survival probabilities to avoid cancellation,
  as supported by [SciPy's t-distribution API](https://docs.scipy.org/doc/scipy/reference/generated/scipy.stats.t.html).
  Finite p-values must stay within `[0, 1]` and be symmetric and monotone in `abs(t)`.

For complete, equally spaced IC samples, an additional comparison against an intercept-only
regression's HAC covariance is useful. Explicitly match Bartlett weights, lags and correction;
[statsmodels' HAC interface](https://www.statsmodels.org/stable/generated/statsmodels.stats.sandwich_covariance.cov_hac.html)
assumes consecutive, equally spaced observations. Dropping missing timestamps and calling that
routine would not independently validate alphatonic's gap-preserving convention.

**Cross-sectional results (`cross_section.py`).**

- Assert every timestamp/horizon row, both methods, counts and coverage against a simple
  one-timestamp oracle. Distinguish available prices, present signals and finite target pairs;
  cover a zero denominator. Verify status precedence when multiple exclusion reasons apply.
- Check summary means, sample standard deviations, positive fractions, non-annualised ICIR,
  period counts and HAC values. Genuine zero IC does not count as positive.
- Check quantile tables for every valid timestamp, all configured buckets and correct counts.
  Retain empty bins; verify invalid rows cannot enter bucket summaries.

**Time-series results (`time_series.py`).**

- Independently enumerate full-period, UTC calendar-month and trailing-window membership.
  Include leap February, partial first/last months, irregular bars, non-aligned endpoints and
  duration strings that must act as fixed durations rather than anchored pandas offsets.
- Assert `n_expected`, `boundary_excluded`, `n_pairs`, coverage, first/last pairs and long
  fraction. Test just below, at and above minimum duration, pair and coverage thresholds.
- Check ordered reasons: partial window, short window, insufficient pairs, low coverage, then
  method-specific degeneracy. Include constant non-zero scores and all-zero scores/returns.
- Recompute each window's correlation, monthly ICIR and status, equal-asset summaries,
  quantiles and lag-one signal autocorrelation independently. Monthly summaries use the
  eligible assets of that month; do not assume the full-period asset set is reused there.
  Show with unequal pair counts that equal-asset means differ from pooled correlations.
- Reconstruct paired circular bootstrap draws from a known seed. All assets/methods must
  share time indices; circular wraparound and final truncation must be correct. Test the
  block-length floor, seed/horizon streams, five-block eligibility, disabled sampling,
  no eligible assets and minimum valid-draw thresholds. Aggregate draws must keep the original
  eligible asset set and reject draws missing any member of that set.
- Independently form time-indexed standardised-product contributions and direct EWC standard
  errors for asset and aggregate t-tests. Include common cross-asset shocks, differing missing
  masks, zero variance and insufficient degrees of freedom. An aggregate must include
  cross-asset covariance rather than averaging individual standard errors.

**Signal persistence (`signal_persistence.py`).**

- Compare exactly `lag` original grid rows apart. Missing interior bars do not invalidate
  finite endpoints, unlike a forward-return path. Check lag boundaries and lags beyond the
  panel length; persistence must not depend on return horizons or future labels.
- Mask scores by endpoint price availability; rank each endpoint in its own universe before
  correlating ranks on common assets. Include universe changes that distinguish this from
  re-ranking only common assets. Check coverage and rank-status precedence.
- Enumerate bucket entries/exits, universe entries/exits and current/previous sizes. Entry
  fraction divides entries by current size. Check ties, empty buckets, ineligible endpoints,
  boundaries and conservation of membership counts.
- Calculate per-asset normalised change, sign flips and zero transitions directly. Cover
  all-zero scores, tiny/large magnitudes, positive rescaling and minimum pairs. Undefined
  normalised change may coexist with defined transition fractions; check both status fields.
- Verify equal-timestamp CS summaries and equal-asset TS summaries and their contributing
  counts, including all-unavailable groups.

### Priority 0: research integrity and stored contracts

**Evaluation and exports (`evaluation.py`, `export.py`).**

- Compare `config=` with equivalent keyword options; supplying both fails. Check configuration,
  UTC window, bar spacing and all three analyses on the result.
- Check `ic()` method validation and configured horizon order; monthly IC means/counts;
  `metrics()` namespaces, numeric types and omission of undefined values. Missing values are
  omitted from flat metrics, but represented by `null` in exported tables.
- Require strict JSON (`allow_nan=False`) for both document types. Assert format/version,
  table names, column order, equal column lengths, UTC timestamps, duration units, booleans,
  NumPy scalars, nullable pandas types and recursive containers; unsupported types fail.
- Include sub-second/sub-microsecond timestamps to expose precision decisions in the
  vectorised datetime exporter. Specify the intended precision before pinning an expectation;
  do not silently bless truncation because it is what the current implementation does.

**Saved evaluations (`persistence.py`).**

- Track the three independent version contracts separately: evaluation directories currently
  write format 5, trial records write format 1, and evaluation/study JSON exports use export
  format 1. An exported JSON document is not a reloadable evaluation directory.
- Round-trip every stored table, options and metadata, including empty tables, `NaN`, `NaT`,
  statuses, booleans, UTC times and difficult floating-point values. Assert schema as well as
  values, allowing only explicitly documented dtype normalisation across pandas versions.
  Raw labels and volatility are intentionally absent after reload.
- Preserve small independently reviewed files for each readable evaluation format, currently
  1–5. Cover uncompressed/compressed tables, legacy `mode`, format-1 return targets, optional
  absent TS/persistence tables, and old TS tables without t-test columns. Historical fixtures
  must not be regenerated with the current writer during the test.
- Test unknown versions, invalid JSON, missing required tables and incomplete optional table
  groups. Test loading without metadata using explicit configuration and the documented
  window/bar inference fallbacks. Verify compressed-file preference when both forms exist.
- Test repeated saves, removal of superseded plain CSV files, removal of stale persistence
  tables and deterministic compression metadata. Probe replacing results with absent optional
  analyses, so stale files cannot silently reappear on reload.
- Inject failures at table and metadata writes and specify the resulting recovery contract.
  General evaluation saves currently write multiple files directly; do not claim transactional
  directory replacement. A desired stronger guarantee requires a production change.

**Studies (`study.py`).**

- Exercise in-sample/holdout defaults, exact-boundary windows, explicit crossings, missing
  holdout configuration, empty windows and clamping to the actual end of prices. No admitted
  forward label may cross the holdout boundary. Check context-column collisions.
- Assert record contents: family defaults, parameters, versions, assets, evaluated window,
  raw-input fingerprint and metrics. Fingerprints must be stable for identical inputs and
  sensitive to changed values, index and labels; distinguish recorded-input provenance from
  equivalence of cleaned evaluation inputs.
- Repeated variants create separate records. Test slug sanitisation, malformed/traversal
  identifiers, unknown trials, ordering, horizon selection, stable sorting, missing-last
  ordering and invalid sorts. Exercise empty studies and heterogeneous/legacy trial records.
- Check family counts across signals, parameters and samples; holdout-use counts; and each
  adjusted p-value as `min(1, p * family_trial_count)`. Missing p-values stay missing. Sorting,
  signal filters and hidden columns must not reduce the family count used for correction.
- Exercise the record commit point: failure before `record.json` exists leaves no counted
  trial; `.partial` and abandoned directories are ignored. Inject save, optional report and
  rename failures. Completed earlier trials must remain unchanged. Explicitly report unreadable
  records instead of silently presenting a study as wholly intact.
- Test read compatibility for study-record format 1, allowed extra fields and rejected future
  versions. Read a study from a fresh `Study` instance and process, not only the writer object.
- Force an ID collision and define refusal/retry behaviour before claiming append-only safety
  for it. The current save path is not an exclusive directory reservation; a UUID suffix alone
  is not evidence that overwriting is impossible. Do not assume multi-process transaction or
  exactly-once recording guarantees that the code does not implement.

### Priority 1: interfaces, presentation and installation

- **Chart specifications:** check all five supported kinds, rectangular arrays, matching
  lengths, stable categories/status colours, UTC epoch milliseconds, explicit `null` gaps,
  quantile counts and equal-unit aggregation. Check basis points versus volatility units,
  chart-only rounding, rolling means masked at current missing observations and intervals
  taken from their actual inference source.
- **HTML:** parse generated pages and embedded JSON; compare displayed data to stored tables.
  Test absent legacy analyses, all-unavailable results, no-period rejection, custom text and
  the persistence detail-row limit. Escape asset names, titles, notes, context and strings
  containing quotes, markup and `</script>`. Assert escaping in JSON as well as HTML contexts.
  Render after reload; a narrowly scoped fail-fast replacement of evaluation/inference entry
  points can prove that rendering does not rerun them.
- **Board:** check empty/filter-empty/unreadable states, ties and ranks, missing intervals,
  default/invalid horizon and sort handling, shared plot scales, significance annotation,
  context columns and regular/business-day/irregular bar labels. Links and column-group toggles
  must preserve the selected horizon, order and filter; the sorted column remains visible.
- **Routing and cache:** exercise `/`, `/study.json`, finished-trial records and tearsheets,
  download flags, lazy drawing, cache hits/eviction and isolation between studies. Reject
  traversal (including URL-encoded paths), arbitrary files and incomplete/unknown trials.
  Distinguish JSON's invalid-sort 400 from the HTML board's fallback behaviour. Reset global
  cache state per test. Concurrent requests must return valid pages without assuming the code
  guarantees only one rendering operation per cache miss.
- **Real HTTP:** use GET and HEAD to verify bodies, content types, byte lengths, attachment
  names and 404/400/500 responses. Verify that newly completed trials appear without a restart.
  Shut down and close every server even after failure.
- **CLI:** execute `alphatonic` and `python -m alphatonic` in fresh subprocesses. Check help,
  required/invalid arguments, unknown sorting, empty studies, limits, horizon/direction,
  unavailable-value formatting, unreadable-record notices, exit codes and serve host/port/name.
  A small argument-dispatch test may replace `serve`; a separate smoke test must start the
  actual server and terminate it cleanly.
- **Package/API:** test all names in `__all__`, installed version metadata and `py.typed`.
  In fresh interpreters check that importing `alphatonic`, `server` and `cli` does not eagerly
  import the reporting subsystem/Jinja2. This is an import-cost contract; Jinja2 is a declared
  runtime dependency. Build both distributions, install a wheel built from the sdist, and
  render from outside the checkout to verify templates, CSS, JS and bundled licences.
- **Progress/demo/docs:** verify `track()` order, totals, advances and context cleanup on
  exceptions/early generator close; callbacks must not change numerical results. Test demo
  shapes, index, seed repeatability, parameter bounds and finite positive prices where present.
  Execute user-facing Python examples in isolated temporary working directories and build
  documentation strictly. The demo generator is useful for smoke tests, not the independent
  generator for statistical calibration.
- **Browser:** open a standalone tearsheet with network requests blocked; require visible
  charts and no console/page errors or chart-error fallbacks. Exercise tabs by mouse and
  keyboard, disclosures, anchors, asset selection, resize, light/dark and print state/restoration.
  On the served board exercise sorting, filtering, groups, lazy-render success/failure and
  downloads. Use semantic locators and condition-based assertions, following
  [Playwright's locator guidance](https://playwright.dev/python/docs/locators) and
  [retrying assertions](https://playwright.dev/python/docs/test-assertions).

### Priority 2: sustained robustness and scale

Maintain performance cases for dense and sparse panels, many horizons/assets, long rolling
histories, bootstrap draws, JSON conversion and HTML generation. Measure peak memory as well
as time, especially near chunk boundaries and on large report specifications. Run on controlled
hardware, record environment and compare repeated measurements with a reviewed baseline;
ordinary tests should not fail on small wall-clock fluctuations.

Use mutation testing selectively on masks, boundaries, denominators, weights and status
precedence. Examples of mutations the suite must catch are `end <=` replacing `end <`, dropping
missing rows before a HAC sum, independently bootstrapping each asset and replacing unavailable
IC with zero. This checks assertion quality beyond executed-line counts.

## 4. Testing methodology

### Independent oracles and numerical assertions

Construct small expectations before calling production code. Put slow scalar definitions in
`tests/support/oracles.py`; they must not call production ranks, labels, correlations or
summaries to construct expected answers. Differential comparisons with pandas/SciPy complement
these definitions; neither a round trip nor comparison between two production functions proves
mathematical correctness.

Assert keys, row identity/order, shape, timezone, counts, statuses and missing-value masks exactly.
For floating-point estimates, choose explicit `rtol` and `atol` from the operation's conditioning
and scale. Small well-conditioned correlations can start with `rtol=1e-12, atol=1e-12`; difficult
cases need a written error rationale. Tail probabilities need relative or log-space checks so
an absolute tolerance cannot make zero an acceptable replacement for a small non-zero p-value.
Compare tables with `pandas.testing.assert_frame_equal`, specifying exactness/tolerances.

[NumPy's `assert_allclose` documentation](https://numpy.org/doc/stable/reference/generated/numpy.testing.assert_allclose.html)
explains the tolerance formula and NaN matching. Check shape and dtype separately when needed;
its `strict=True` option was introduced in NumPy 2 and cannot be used in tests that must run on
the declared NumPy 1.26 floor. Do not widen tolerances merely to make a failing test pass.

### Fixtures and parametrization

Use small function-scoped factories with explicit controls for shape, calendar, ties, missing
prices/scores, changing universes and known relationships. Separate positive-price construction
from score construction; do not obtain every expected label from `forward_returns()` itself.
Fixtures must return independent mutable objects. Share only immutable expensive resources.

Write exclusively under `tmp_path`; allocate one directory per study/test. Use yield/finally
cleanup for processes, threads, sockets and browser contexts, including partial setup failures.
These choices follow [pytest's fixture lifecycle guidance](https://docs.pytest.org/en/stable/how-to/fixtures.html)
and [temporary-directory guidance](https://docs.pytest.org/en/stable/how-to/tmp_path.html).

Parametrize boundary values and meaningful interactions: method × ties/missingness, horizon ×
delay × gap location, target × warm-up, pandas generation × file format. Avoid the full Cartesian
product of unrelated options. Keep one explicit hand-calculated example for each core rule;
large randomized matrices are harder to diagnose and can miss a specific boundary.

### Property-based and metamorphic testing

Use Hypothesis as a required test-only dependency. Generate small valid panels directly rather
than rejecting most examples with `assume()`. Include invalid-input strategies separately.
Target these properties with their necessary preconditions:

| Property | Scope and qualification |
| --- | --- |
| Finite correlations lie in `[-1, 1]`; swapping arguments preserves them. | Eligible paired samples; test missingness separately. |
| Positive affine transforms preserve Pearson; strictly increasing transforms preserve Spearman. | Transforms must remain finite and preserve the intended ties. Cosine is not translation-invariant. |
| Positive rescaling preserves cosine and per-asset normalised signal change. | Non-degenerate norms/denominators; handle near-zero snapping explicitly. |
| Positive constant rescaling of each price column preserves returns and volatility-scaled labels. | Constant over time, finite positive transformed prices. |
| Asset permutation only permutes per-asset outputs and leaves aggregate statistics unchanged within tolerance. | Align both inputs; compare by semantic keys. |
| Wide/long inputs and equivalent timezone representations agree. | Same values and instants, with an unambiguous two-level long index. |
| Altering data outside an explicit end leaves evaluation tables unchanged. | Preserve input validity; compare numerical outputs, not fingerprints, timestamps of creation or generated HTML footers. |
| Appending future data cannot change earlier matured labels or earlier volatility estimates. | Restrict the comparison to those quantities; full-period ranks, summaries and intervals may change. |
| Bootstrap multiplicities equal explicit row repetition. | Identical paired rows and resample-specific ranks. |
| Bucket/member counts and overlap identities conserve their underlying pairs or universe. | Respect constant/ineligible endpoint status rules. |

Add a small state-machine model for study operations: evaluate, reopen, list, export and attempt
a refused window. Its invariant is that completed records and counts persist while refused or
unfinished work adds no completed trial. Hypothesis can generate sequences as described in its
[stateful testing documentation](https://hypothesis.readthedocs.io/en/latest/stateful.html).

Use a deterministic bounded Hypothesis profile for pull requests and a larger exploratory
profile for scheduled runs. Retain the failing example and dependency versions; promote a
minimised failure to an explicit regression example. Hypothesis documents both database replay
and explicit examples in [replaying failed tests](https://hypothesis.readthedocs.io/en/latest/tutorial/replaying-failures.html).
Do not suppress health checks or rely on a cached example database to supply essential coverage.

### Statistical validation

Separate “the formula was implemented correctly” from “the method has acceptable operating
characteristics”. Both are required. For each experiment record its aim, independent
data-generating mechanism, estimand, method/options and performance measure. This follows the
ADEMP approach of [Morris, White and Crowther (2019)](https://pmc.ncbi.nlm.nih.gov/articles/PMC6492164/).

The calibration inventory must cover:

- Null independent signals; persistent signals and returns; overlapping horizons and delays;
  heteroskedastic innovations; and common cross-asset shocks. Keep factor and future returns
  independent under the intended null, including their common-factor components.
- CS Newey–West rejection rates and interval coverage, TS EWC asset/aggregate rejection rates,
  and percentile-bootstrap coverage for asset and equal-asset IC, across all supported methods.
- Random and clustered exogenous gaps, ties and changing asset coverage, preserving the time
  grid. Informative missingness and strongly non-stationary processes are separate stress
  experiments, not cases where nominal calibration is automatically promised.
- Known alternatives to measure bias, interval width and power. Construct prices and factors
  independently of the production/demo code, and state when the true estimand is not the
  generator's slope (for example Spearman, cosine or a multi-bar return correlation).
- Small samples and near-degeneracy to measure how often inference is unavailable. Report the
  unavailable fraction and its denominator; a method cannot pass simply by returning no tests.

Choose repetitions from Monte Carlo precision before running the experiment. For a rejection
rate `p` from `R` independent replications, Monte Carlo SE is `sqrt(p * (1 - p) / R)`; at
`p=0.05`, `R=2000` gives about 0.0049. Bootstrap draws within one replication are not independent
Monte Carlo replications. Predeclare an acceptable excess rejection rate, coverage error and
unavailability rate per supported regime, then choose `R` large enough to resolve them. Use
binomial bounds, with multiplicity accounted for across gating scenarios, rather than requiring
exactly 5% rejection. A screening run with few replications cannot establish precise calibration.

Use independent seeded `np.random.default_rng` streams per scenario and replication, never
global random state or worker IDs. Freeze scenario definitions and thresholds independently of
the observed outcome. Keep a compact deterministic calibration panel as a merge gate and broader
experiments scheduled and required before statistical releases. Never search for a passing seed.

### Mocking and isolation

Use real NumPy, pandas, pydantic, Jinja2 and temporary files in their contract tests. Mock narrow
boundaries to inject failures or control nondeterminism: a write/replace operation, clock, UUID,
progress callback or expensive render during a routing-only test. Patch where a name is looked
up and restore it automatically; see [pytest's monkeypatch guidance](https://docs.pytest.org/en/stable/how-to/monkeypatch.html).
Do not mock the statistic, serializer or renderer whose correctness the test claims to establish.

Prohibit external network access during test execution; allow loopback only for explicit server
tests. Use ephemeral ports, bounded request/subprocess timeouts and readiness signals instead
of sleeps. Fresh interpreters isolate import state; fresh browser contexts isolate UI state.
Restore module caches, environment variables and working directories, and verify input frames
are unchanged. Subprocess tests use one BLAS thread to avoid thread-launch overhead for small
bootstrap matrices, particularly on the oldest supported NumPy. Tests must pass independently and with reordered/parallel execution.

## 5. External dependencies

The inspected production code has no database, remote market-data API client or message broker.
Do not add container services, credentials or live-data tests for dependencies the library does
not have. Its state is local files; its HTTP server is a local interface rather than an external
service integration.

| Dependency/boundary | Test strategy |
| --- | --- |
| NumPy, pandas, pydantic, Jinja2 | Real implementations; supported-version matrix; explicit behavioural contracts at alignment, numerical, validation and rendering boundaries. |
| Filesystem, JSON, CSV and gzip | Actual temporary files; historical fixtures; repeat writes; partial/corrupt/missing input; narrow I/O fault injection. |
| Standard-library HTTP server | Direct response tests plus real loopback HTTP; port 0 for automatic allocation; cleanup and concurrency/cache checks. |
| Browser, bundled d3/Observable Plot/Pico | Exercise alphatonic's specifications and rendering with real bundled assets; offline browser smoke tests; resources/licences checked in built packages. Do not retest vendor internals. |
| Package index/build tooling | Resolve dependencies and prepare a wheelhouse during job setup, then execute build/install tests offline. Use isolated wheel environments with runtime dependencies, build dependencies and test tools explicitly provisioned. |
| Database / third-party API / broker | Not applicable to the current code. If introduced, add an adapter contract and integration tests against a disposable real instance or local protocol stub as appropriate; keep a few separately credentialled live smoke checks only if a real remote contract needs them. |

Keep Hypothesis, SciPy reference calculations, coverage tooling and browser automation out of
runtime dependencies. A consumer-installation test must succeed without those test tools being
declared as package requirements. Keep minimum-runtime checks separate from reference-tool
environments if an oracle tool's requirements would otherwise raise the tested NumPy/pandas floor.

## 6. Quality gates

The following are proposed policies, not a description of current CI.

### Required checks and environments

| Gate | Pull request | Scheduled / release |
| --- | --- | --- |
| Deterministic correctness | All unit, component, integration and acceptance tests; bounded property tests and compact calibration panel. | Repeat with larger generated cases and changed ordering/seeds. |
| Runtime compatibility | Python 3.11–3.14 with newest compatible dependencies; a separate Python 3.11 environment at declared runtime floors. Exercise pandas 2 and 3 explicitly. | Resolve again without relying solely on a development lock; test new dependency releases and prereleases separately. |
| Operating systems | Linux numerical suite; Windows and macOS import, save/load, CLI and HTTP smoke tests. | Full non-browser suites on all three before release. |
| Browser | Chromium offline and served critical journeys. Missing browser installation is a failed required job. | Firefox/WebKit smoke tests, print, narrow viewport and reviewed visual comparisons. |
| Static analysis | Ruff lint/format and Pyright with Python 3.11 compatibility for package code. Check tests with suitable lint rules too. | Same checks on release artifacts/source. |
| Distribution and documentation | Wheel/sdist metadata and resources, installed-package smoke tests, executable examples and strict documentation build. | Clean consumer installation from the sdist-built wheel, including the oldest supported runtime. |
| Numerical calibration | Compact predeclared scenarios on every change. Expanded panel required when labels, ranks, inference, eligibility or statistical defaults change. | Full calibration and power/coverage report before a statistical release. |
| Performance | Avoid fragile per-test timing gates; flag large regressions for review. | Controlled time/peak-memory baselines and targeted mutation checks. |

The declared floors are NumPy 1.26, pandas 2.2.2, pydantic 2.6 and Jinja2 3.1. Pin those exact
minimum versions on Python 3.11 and resolve compatible transitive dependencies and test tools.
Testing only the newest patch in each old series does not test the declared minimum. Do not
demand NumPy 1.26 on a Python version it cannot support. Record actual resolved versions for
every matrix job.

### Coverage and merge requirements

Measure branch coverage of first-party Python under `src/alphatonic`; include reports, CLI and
server code. Exclude vendored JS/CSS from Python coverage, and assess owned browser behaviour
through explicit scenarios. Include worker/subprocess coverage when claiming those paths are
covered; a parent process's coverage report alone is insufficient.

The suite enforces a **95% combined statement-and-branch coverage floor**, with no
unreviewed reduction. This is a proposed project target, not an industry-mandated percentage.
Require explicit tests of every numerical exclusion/status reason, time-boundary decision,
format migration and holdout decision regardless of the total percentage. Aim for full branch
coverage of these decisions; inspect the separate line/branch metrics and missing branches.
[Coverage.py documents](https://coverage.readthedocs.io/en/latest/branch.html) why executing every
line can still miss a branch. Coverage measures reach, not whether the assertions would catch
an incorrect result.

A change is ready to merge when required jobs pass on its current revision, a reviewer can
trace changed behaviour to meaningful assertions, and all intentional contract/statistical
changes have an explanation and updated user documentation. Statistical changes also need an
independent formula review and the relevant calibration evidence. Format changes need a version
decision and historical-read tests. Never regenerate expected values from the implementation
under test without independent review.

Unexpected warnings fail tests; intentional user warnings are asserted explicitly. Do not use
blanket warning suppression, retries, skips, `xfail` or weakened tolerances to make a required
contract appear green. On failure retain seed/example, resolved versions, relevant generated
inputs, logs and browser traces. Review snapshot updates; normalise only irrelevant metadata
such as generation time, and do not replace numerical assertions with HTML/image snapshots.

The proposed developer feedback budget is under one minute for the default deterministic
selection on a documented reference machine, excluding environment setup. Measure durations
before setting a firm budget for calibration and browsers. Speed improvements must preserve
assertions and statistical precision; splitting workloads is preferable to reducing evidence.

## 7. Local test execution

### Tooling and setup

The commands below use the test layout and dependency groups in this repository. Use uv to
update the lockfile, and keep test tools in dependency groups, as described
in [uv's dependency guidance](https://docs.astral.sh/uv/concepts/dependencies/).

- `test`: pytest, Hypothesis, coverage.py, pytest-xdist, pytest-timeout, SciPy, build, Hatchling
  and pip (the last three build and install the distribution offline).
- `browser`: pytest-playwright, alongside the `test` group.
- `quality`: Ruff, Pyright and Twine.
- `docs`: Zensical and the documentation plugins required by the documentation configuration.

Choose and lock versions compatible with the relevant Python environments. The registered markers are
`property`, `statistical`, `slow`, `browser` and `benchmark`; browser tests and all benchmarks carry these markers. Only expanded inference experiments should carry `slow`, so the compact calibration
panel remains in the default run. Load Hypothesis profiles `ci` (bounded, deterministic) and
`extended` (larger, exploratory) in `conftest.py`.
Keep browser-only imports and fixtures under `tests/e2e/`. Plain `pytest` never collects that
directory, because a marker alone does not prevent optional imports. `tests/conftest.py` also
deselects `slow` tests unless `--extended` is given, so the default run is the essential quick
suite. Browser journeys need `--run-browser`; expanded experiments need `--extended`.

The pytest configuration is:

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
addopts = "--import-mode=importlib --strict-markers --strict-config"
filterwarnings = ["error"]
timeout = 60
markers = [
    "property: generated invariants and metamorphic relations",
    "statistical: simulation-based method validation",
    "slow: expanded experiments outside the default feedback budget",
    "browser: real browser journeys",
    "benchmark: controlled performance measurements",
]
```

### Daily development

Run from the repository root. The first command installs the ordinary test and quality
tools; browser binaries are a separate setup step.

```sh
uv sync --locked --no-default-groups --group test --group quality

# Provision archives before tests prohibit external network access. Repeat per Python/platform.
uv run --no-sync python -m pip download --dest .test-wheelhouse \
  hatchling numpy pandas pydantic jinja2

# Essential quick suite (the default): deterministic, includes compact calibration, no browser
# and no `slow` experiments.
uv run --no-sync pytest

# A numerical module, one named behaviour, or the joining contracts.
uv run --no-sync pytest tests/unit/test_returns.py -q
uv run --no-sync pytest tests/unit/test_stats.py -k resampled -vv
uv run --no-sync pytest tests/component/test_time_series.py tests/integration/test_evaluation_io.py

# Public research requirements and generated invariants.
uv run --no-sync pytest tests/acceptance
uv run --no-sync pytest -m property --hypothesis-profile=ci

# Parallel feedback once independence has been established; inspect slowest cases.
uv run --no-sync pytest -n auto --durations=20

# Static analysis.
uv run --no-sync ruff check src/alphatonic tests
uv run --no-sync ruff format --check src/alphatonic tests
uv run --no-sync pyright --pythonversion 3.11
```

For an actual failure use its pytest node ID with `-vv --tb=long`; reproduce in one process
before adding workers. Replay a generated failure using the reported Hypothesis seed/example
and recorded library versions. Do not treat a successful rerun as a repair.

### Coverage, inference, browser and packaging checks

```sh
# Run serially for this basic coverage command. Configure subprocess collection separately.
uv run --no-sync coverage run --branch --source=alphatonic -m pytest
uv run --no-sync coverage combine
uv run --no-sync coverage report --show-missing --fail-under=95
uv run --no-sync coverage html

# Full calibration and larger property searches; use the predeclared simulation sizes.
uv run --no-sync pytest tests/statistical --extended --timeout=600 --durations=20
uv run --no-sync pytest -m property --hypothesis-profile=extended

# Install browser tooling and binaries, then run offline and served journeys.
uv sync --locked --no-default-groups --group test --group browser --group quality
uv run --no-sync playwright install chromium
uv run --no-sync pytest --run-browser tests/e2e -m browser --browser chromium

# Documentation and distribution checks.
uv sync --locked --no-default-groups --group test --group quality --group docs
uv run --no-sync zensical build --clean --strict
uv run --no-sync pytest tests/integration/test_documentation.py
uv build --no-sources
uv run --no-sync twine check dist/*
uv run --no-sync pytest tests/integration/test_distribution.py

# Benchmarks are explicit and kept outside default test collection.
uv run --no-sync pytest benchmarks -m benchmark --timeout=600
```

The distribution test must create its own clean environment, build a wheel from the sdist,
install it non-editably and run smoke checks outside the source tree. Building archives and
checking metadata alone does not verify that the packaged report assets work.

### Minimum and newest dependencies

Use a fresh, isolated resolver environment for compatibility work, rather than assuming the
development lock represents both extremes. These proposed commands use uv's additional package
requirements, documented in its [CLI reference](https://docs.astral.sh/uv/reference/cli/):

```sh
# Runtime-floor environment: the resolver also chooses compatible test-tool versions.
uv run --isolated --no-project --python 3.11 --with-editable . \
  --with pytest --with hypothesis --with pytest-timeout \
  --with coverage --with scipy --with 'numpy==1.26.0' \
  --with 'pandas==2.2.2' --with 'pydantic==2.6.0' --with 'jinja2==3.1.0' \
  python -m pytest --hypothesis-profile=ci

# Newest compatible runtime dependencies; repeat for Python 3.11, 3.12, 3.13 and 3.14.
uv run --isolated --no-project --python 3.14 --with-editable . \
  --with pytest --with hypothesis --with pytest-timeout --with scipy \
  python -m pytest --hypothesis-profile=ci
```

Record resolved versions with failures. Add explicit pandas 2/3 constraints to separate matrix
runs rather than assuming “newest” tests both. Provision dependencies and browser binaries
before enforcing the no-external-network execution rule. In an environment without a browser
installation, run the non-browser selection locally; the required browser job must still pass
before merge.
