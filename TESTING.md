# Testing alphatonic

The production path is `evaluate()` → input alignment → return labels and optional volatility
scaling → cross-sectional IC, time-series IC and signal persistence. Results also pass through
versioned file storage, JSON export, `Study`, HTML rendering, a local HTTP server and a CLI.
Spend test effort in proportion to what a wrong answer costs along that path: the numbers first,
then the stored records, then the interfaces.

## 1. What the tests must guarantee

| Guarantee | Evidence |
| --- | --- |
| Correct numbers | Hand-calculated examples and independent scalar oracles for correlations, ranks, buckets, summaries and uncertainty. |
| Correct time boundaries | Exact bar-based horizons and delays; half-open evaluation windows; no label ending outside a window; volatility using only information available at the score timestamp. |
| Honest missingness | An undefined estimate is `NaN` with a status, never zero. A genuine zero stays distinguishable. |
| Dependence-aware uncertainty | Formula checks and calibration experiments for Newey–West, equal-weighted cosine (EWC) and the paired circular block bootstrap. |
| Reproducible results | Seeded local generators; the same options give the same numbers. |
| Durable research records | Readable historical formats, faithful exports and reloads, preserved trial counts, enforced holdout boundaries, visible unreadable records. |
| Working interfaces | Public imports, packaged report resources, the CLI, the HTTP server and the documented examples. |

These guarantees are bounded. Calibration applies to the data-generating mechanisms and sample
sizes tested; it does not establish validity under arbitrary non-stationarity or informative
missingness. The library cannot know whether a caller's factor used future information.

Add a failing regression test with every fix, and an executable example with every new public
behaviour.

## 2. Layout and ownership

Tests live outside `src/` and import the installed package (`--import-mode=importlib`). Use the
smallest level that can show a guarantee. Exhaustive cases belong to the subsystem's own tests;
higher levels check only the joining contract.

```text
tests/
  conftest.py          # shared fixtures, Hypothesis profiles, network guard
  support/             # panels.py (synthetic data), oracles.py (scalar references),
                       # strategies.py, assertions.py
  data/                # hand-authored files in each readable format; see MANIFEST.md
  unit/                # one function or rule (config, inputs, returns, stats, export,
                       # progress, report figures and board values)
  component/           # one subsystem through its normal interface
  integration/         # subsystems together, or a real OS boundary (HTTP, subprocess, docs,
                       # packaging)
  acceptance/          # researcher-facing requirements through the public API
  statistical/         # calibration experiments
benchmarks/            # timing and size measurements; run explicitly
```

Name tests `test_<behaviour>_<condition>_<outcome>` and give parametrized cases descriptive IDs.
Import helpers from `tests.support`; tests must not import other test modules.

| Production source | Primary tests |
| --- | --- |
| `config.py` | `unit/test_config.py` |
| `inputs.py` | `unit/test_inputs.py` |
| `returns.py` | `unit/test_returns.py` |
| `stats.py` | `unit/test_stats.py`, `statistical/` |
| `cross_section.py` | `component/test_cross_section.py` |
| `time_series.py` | `component/test_time_series.py` |
| `signal_persistence.py` | `component/test_signal_persistence.py` |
| `evaluation.py` | `component/test_evaluation.py`, `integration/test_evaluation_io.py`, `acceptance/` |
| `persistence.py` | `component/test_persistence.py` (reads the files in `tests/data/`) |
| `export.py` | `unit/test_export.py` |
| `study.py` | `component/test_study.py`, `integration/test_study_workflow.py`, `acceptance/` |
| `report/figures.py`, `report/ts_figures.py` | `unit/report/` |
| `report/` pages and templates | `component/test_report.py` |
| `report/board.py` | `unit/report/test_board_values.py` |
| `server.py` | `component/test_server.py` (routing, no socket), `integration/test_http_server.py` (real HTTP) |
| `cli.py`, `__main__.py` | `integration/test_cli.py` |
| `__init__.py`, package metadata | `integration/test_imports.py`, `integration/test_distribution.py` |
| `progress.py` | `unit/test_progress.py` |
| `demo.py` | Exercised by the documentation tests |
| Documentation examples | `integration/test_documentation.py` |

The browser charts are drawn by `alphatonic.js` and are not tested in a browser. The chart
specifications that feed them are tested in `unit/report/`; after changing the script, look at the
pages yourself (see `CONTRIBUTING.md`).

### What the tests must cover

- **Labels and windows.** Compute `P[t + delay + h] / P[t + delay] - 1` independently. A missing
  price anywhere from `t` through `t + delay + h` makes the label missing. The last `delay + h`
  rows have no label. Nothing ending on or after an exclusive end contributes.
- **Primitives.** Compare Pearson, Spearman (average ranks over the surviving pairs) and cosine
  with scalar definitions, including ties, constants, genuine zeros and fewer than three pairs.
  Check chunk boundaries (`BLOCK_ROWS - 1`, `BLOCK_ROWS`, `BLOCK_ROWS + 1`), bucket membership
  from average paired ranks, the Bartlett-weighted HAC sum (which preserves the positions of
  missing periods), EWC degrees of freedom and the Student t p-values.
- **Statuses.** Every exclusion reason and the order in which they take precedence: partial
  window, short window, insufficient pairs, low coverage, then method-specific degeneracy. A
  constant non-zero position has a valid cosine even when Pearson and Spearman are undefined.
- **Bootstrap.** Paired circular blocks from a known seed; all assets and methods share time
  indices; draws that lose any eligible asset are rejected.
- **Stored contracts.** Evaluation directories (formats 1–5), trial records (format 1) and JSON
  exports (format 1) are separate version contracts. Historical files in `tests/data/` are never
  regenerated by the current writer.
- **Studies.** Holdout boundaries, family trial counts and `min(1, p * family_trial_count)`
  adjustment, repeated variants as separate records, `.partial` directories ignored, and
  unreadable records reported rather than hidden.
- **Presentation.** Chart specifications agree with the stored tables; missing values are
  explicit gaps; text is escaped in HTML and in embedded JSON; a reloaded evaluation renders
  without recomputing inference.
- **Server and CLI.** Traversal is rejected; JSON and HTML sort handling differs on purpose
  (400 and fallback); fresh-interpreter runs of `alphatonic` and `python -m alphatonic`;
  importing `alphatonic`, `server` and `cli` does not load the report subsystem.

## 3. Method

### Independent oracles

Write the expected value before calling the code under test. Slow scalar definitions live in
`tests/support/oracles.py` and must not call production ranks, labels, correlations or summaries.
A round trip, or a comparison of two production functions, does not prove the mathematics.

Assert keys, row order, shape, timezone, counts, statuses and missing-value masks exactly. For
floating-point estimates choose `rtol` and `atol` from the operation (`1e-12` suits small
well-conditioned correlations) and justify looser ones. Check tail probabilities with relative or
log-space tolerances so that zero cannot replace a small p-value. Do not widen a tolerance to make
a failing test pass. `assert_allclose(strict=True)` needs NumPy 2 and cannot be used.

### Fixtures and properties

Use small function-scoped factories with explicit control over shape, calendar, ties, gaps and
universe changes. Build prices separately from scores, and do not take expected labels from
`forward_returns()`. Write only under `tmp_path`, and close servers, threads and sockets in
`finally`.

Hypothesis (a test-only dependency) checks invariants such as correlations in `[-1, 1]`,
invariance to positive affine transforms and asset permutation, and bootstrap multiplicities
equal to explicit row repetition. Generate valid inputs directly rather than filtering with
`assume()`. Profile `ci` is bounded and deterministic; `extended` is larger. Turn a minimised
failure into an explicit example.

### Statistical validation

Separate "the formula is implemented correctly" from "the method behaves well". A change to
labels, ranks, inference, eligibility or statistical defaults needs both: scalar-oracle tests and
a calibration experiment in `tests/statistical/` (or a published source for the formula).

For each experiment, state the data-generating mechanism, the estimand, the method and options,
and the performance measure. Cover null signals, persistent signals and returns, overlapping
horizons, heteroskedasticity, common cross-asset shocks, exogenous gaps and known alternatives
(bias, width, power). Report how often inference is unavailable; a method cannot pass by
returning no tests.

Choose the number of replications `R` from the Monte Carlo error first: for a rejection rate `p`
the standard error is `sqrt(p * (1 - p) / R)`, about 0.0049 at `p = 0.05` and `R = 2000`.
Bootstrap draws inside one replication are not replications. Set the acceptable excess rejection
rate and coverage error in advance and test against binomial bounds, not against exactly 5%.
Use `np.random.default_rng` streams seeded per scenario and replication. Never search for a
passing seed. The compact panel runs by default; the expanded one is marked `slow`.

### Mocking and isolation

Use real NumPy, pandas, pydantic, Jinja2 and temporary files. Patch only narrow boundaries (a
write or replace call, the clock, a UUID, a render in a routing test) and never the statistic,
serializer or renderer a test claims to check. External network access is blocked by
`tests/conftest.py`; loopback is allowed for server tests, which use port 0. Subprocess tests
use one BLAS thread. Unexpected warnings fail the tests (`filterwarnings = ["error"]`); assert
intentional ones. Don't use blanket suppression, retries, `skip` or `xfail` to turn a required
contract green. Tests must pass in any order and under `-n auto`.

The documentation tests only show that the examples run, so they cap the bootstrap at 100 draws
(`FAST_BOOTSTRAP` in `tests/integration/test_documentation.py`); the statistical tests establish
that the intervals are right.

## 4. Quality gates

CI (`.github/workflows/ci.yml`) runs on every pull request:

| Job | What it checks |
| --- | --- |
| `quality` | `ruff check .`, `ruff format --check .`, `pyright`. |
| `test` | `pytest --hypothesis-profile=ci` on Python 3.11–3.14, each with pandas 3 and pandas 2, resolved independently of the dev lock. |
| `minimum` | The same on Python 3.11 at NumPy 1.26.0, pandas 2.2.2, pydantic 2.6.0 and Jinja2 3.1.0. |
| `platform` | Imports, persistence, CLI and HTTP tests on Windows and macOS. |
| `docs-and-build` | `zensical build --strict`, `uv build`, `twine check`. |

On a schedule and on `release-*` branches, `expanded` also runs the packaging test, the full
calibration (`--extended`), the larger property search and the benchmarks.

A change is ready to merge when those jobs pass and a reviewer can trace the changed behaviour to
meaningful assertions. Intentional contract or statistical changes need an explanation and updated
documentation; format changes need a version decision and a test that reads the older format.
Never regenerate expected values from the implementation under test.

## 5. Local test execution

```sh
uv sync --locked --no-default-groups --group test --group quality

uv run --no-sync pytest                          # the default run: no `slow` tests
uv run --no-sync pytest tests/unit/test_returns.py -q
uv run --no-sync pytest tests/unit/test_stats.py -k resampled -vv
uv run --no-sync pytest -n auto --durations=20   # parallel; inspect the slowest tests

uv run --no-sync pytest -m property --hypothesis-profile=extended
uv run --no-sync pytest tests/statistical --extended --timeout=600

# Documentation, packaging and the distribution test (needs an offline wheelhouse first).
uv run --no-sync python -m pip download --dest .test-wheelhouse hatchling numpy pandas pydantic jinja2
uv run --no-sync pytest tests/integration/test_distribution.py --extended
uv sync --locked --no-default-groups --group test --group quality --group docs
uv run --no-sync zensical build --clean --strict
uv build --no-sources && uv run --no-sync twine check dist/*

uv run --no-sync pytest benchmarks -m benchmark --timeout=600
```

Coverage is a diagnostic, not a gate. To see which branches a change leaves unexecuted:

```sh
uv run --no-sync coverage run -m pytest && uv run --no-sync coverage combine
uv run --no-sync coverage report --show-missing
```

For a failure, rerun its node ID with `-vv --tb=long` in one process before adding workers.
Replay a Hypothesis failure from its reported seed.

### Minimum and newest dependencies

Check the declared floors and the newest versions in isolated resolver environments rather than
the dev lock (the `minimum` and `test` jobs do this). To reproduce the floor run locally:

```sh
uv run --isolated --no-project --python 3.11 --with-editable . \
  --with pytest --with hypothesis --with pytest-timeout --with scipy \
  --with 'numpy==1.26.0' --with 'pandas==2.2.2' --with 'pydantic==2.6.0' --with 'jinja2==3.1.0' \
  python -m pytest --hypothesis-profile=ci
```

Use the same command with `--python 3.14` and no pins for the newest versions, and add
`--with 'pandas>=3'` or `--with 'pandas<3'` to pick a pandas generation. Don't ask for NumPy 1.26
on a Python version it cannot run on.
