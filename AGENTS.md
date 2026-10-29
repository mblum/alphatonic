# AGENTS.md

Guidance for coding agents working in this repository. People should start with
[CONTRIBUTING.md](CONTRIBUTING.md). If this file and that guide disagree, the guide is right;
fix this file.

alphatonic is a Python library (with an `alphatonic` command) that evaluates predictive signals
(alpha factors). From scores and prices it computes cross-sectional and time-series information
coefficients (IC), with uncertainty that accounts for dependence (Newey–West, block bootstrap).
It can render an offline HTML tearsheet and keep the trials of a research question in a `Study`.
Users rely on its numbers, so getting the statistics right matters more than anything else.

## Commands

Use [uv](https://docs.astral.sh/uv/) and run from the repository root. Local development uses
Python 3.13 (`.python-version`), but the code must run on 3.11 to 3.14.

```sh
uv sync --all-extras --locked                  # set up .venv with the dev tools and the report extra
uv run pytest                                  # whole suite, in parallel, under 40 seconds
uv run pytest tests/test_stats.py -k hac -n 0  # one file or test, in one process
uv run ruff check .                            # lint (add --fix for safe fixes)
uv run ruff format .                           # format; CI runs `ruff format --check .`
uv run pyright                                 # type-check src/ as Python 3.11
uv run --group docs zensical build --strict    # build the docs site as CI does
uv run --isolated --resolution lowest-direct --python 3.11 pytest   # oldest supported dependencies
uv build && uvx twine check dist/*             # package and check the distributions
```

Before you call a change done, run `pytest`, `ruff check .`, `ruff format --check .` and
`pyright`. Also build the docs when you touch `docs/` or a public docstring, and run the
lowest-dependency suite when you use a pandas, NumPy or pydantic API you are not sure the oldest
supported version has. CI (`.github/workflows/ci.yml`) runs all of these.

## Layout

- `src/alphatonic/`: the package. `evaluate()` in `evaluation.py` is the entry point. It
  validates and aligns the inputs (`inputs.py`), computes forward-return labels (`returns.py`),
  then runs the cross-sectional (`cross_section.py`) and time-series (`time_series.py`)
  analyses, both built on `stats.py`. Options are pydantic models in `config.py`. Results are
  saved and loaded by `persistence.py`. `study.py` keeps trials, `report/` renders the
  tearsheet and the list of trials (Jinja2 templates; the charts are Observable Plot and d3,
  vendored in `report/static/`: `figures.py` and `ts_figures.py` compute what a chart shows and
  `alphatonic.js` only draws it), `server.py` serves that list, and `cli.py` is the `alphatonic`
  command.
- `tests/`: pytest, one `test_<module>.py` per module. `conftest.py` has synthetic-data
  helpers (`regular_panel`, `perfect_market`), and `reference.py` is the reference
  implementation (see below).
- `docs/`: the Zensical site, arranged by [Diátaxis](https://diataxis.fr/): `tutorials/`,
  `how-to/`, `reference/`, `explanation/`, and `contributing/`.
- The table "Where changes belong" in `CONTRIBUTING.md` maps each kind of
  change to its module and its tests.

## Rules that protect the results

- **No silent zeros.** A statistic that cannot be computed is `NaN` with a `status` (such as
  `constant_signal`, `insufficient_assets` or `low_coverage`), never `0`. Keep the explicit
  handling of gaps, ties, constant scores and missing data.
- **Bars, not clock time.** Horizons count rows of the price table. A forward return needs an
  unbroken run of prices, so never fill or skip gaps to get more labels.
- **The reference implementation is the specification.** `tests/reference.py` is the plain,
  one-timestamp-at-a-time version of the evaluation, and
  `tests/test_reference_equivalence.py` checks that `src/` gives the same tables. When you
  optimise, leave the reference alone. When you change statistical behaviour on purpose,
  change the reference in the same commit and say so in the pull request.
- **Statistical changes need evidence.** Cite a source or add a fixed-seed simulation to
  `tests/test_inference.py`, and update `docs/explanation/methodology.md`. The inference tests
  pin calibration: a factor without skill must not be declared significant much more often
  than 5% of the time.
- **Deterministic.** Draw random numbers only from a `np.random.default_rng` seeded from the
  options (see the bootstrap in `time_series.py`). Never use the global NumPy random state.
- **Saved formats stay readable.** Evaluation directories (`persistence.FORMAT_VERSION`) and
  study records (`study.FORMAT_VERSION`) are files users keep. If you change what is written,
  bump the version, keep reading the older formats, and test that they load.
- **Studies never overwrite or delete a trial.** Every evaluation is counted.

## Code conventions

- Ruff enforces formatting (100-character lines) and lint rules, including Google-style
  docstrings for everything public in `src/`. mkdocstrings renders those docstrings as the API
  reference, so write them for users: what the function returns, units, and when a value is
  `NaN`.
- Modules start with a docstring and `from __future__ import annotations`. Type every
  function in `src/`; pyright runs in standard mode.
- Write for Python 3.11: no `type` statements or PEP 695 generics. Supported dependencies go
  back to pandas 2.2.2, NumPy 1.26 and pydantic 2.6, and CI tests both pandas 2 and 3. Where
  they differ, branch on the version as `persistence.py` does.
- Options are pydantic models with `ConfigDict(extra="forbid", frozen=True)`. Validate in the
  model and give errors that say what is wrong and what is accepted.
- Keep `src/` vectorised. Loops over timestamps belong in the reference implementation, not in
  the library.
- Keep the dependencies small: evaluation needs only NumPy, pandas and pydantic. Jinja2
  belongs to the optional `report` extra, so import `alphatonic.report` lazily, inside
  the function that needs it (as `Evaluation.render_tearsheet` does). `alphatonic`,
  `alphatonic.server` and `alphatonic.cli` must import without them, and
  `tests/test_public_api.py` checks this.
  Ask before you add a runtime dependency or raise a lower bound, and give the reason in the
  pull request.
- The public API is `alphatonic.__all__`. A new public name needs a docstring, an entry in
  `__all__`, a place in `docs/reference/api.md`, and a changelog line.
- Change `uv.lock` only through uv (`uv lock`, `uv add`), never by hand. CI installs with
  `--locked`.

## Tests

- Use synthetic data from the helpers in `tests/conftest.py`
  (`from conftest import regular_panel`, since `tests/` is on the import path) and write files
  only to `tmp_path`. Tests use no network and no real market data.
- Every warning is an error (`filterwarnings = ["error"]`). If pandas or NumPy warns, fix the
  call; don't silence the warning.
- The suite runs in parallel (pytest-xdist, `-n auto` in `pyproject.toml`) and must finish in
  under 40 seconds. Check `--durations=10` after adding tests. Use small panels, and
  `time_series={"bootstrap_samples": 0}` and a coarse `rolling_step` when the bootstrap or the
  rolling windows are not what the test is about. Make slow code faster rather than cutting a
  test's repetitions or assertions. Tests must not depend on each other or on their order.
- Add a test with every fix and every feature, in the matching `test_<module>.py`. Never skip,
  `xfail` or loosen a test to make the suite pass.

## Documentation

- `tests/test_docs.py` runs every Python block in the root Markdown files and `docs/`, in order, in one
  namespace per page. Examples must actually run. Put `<!-- notest -->` on the line above a
  block that must not run.
- Follow Diátaxis: reference pages state facts, explanation pages give reasons, how-to guides
  solve one task. Update the page that matches what you changed.
- Write plain, concrete sentences. The prose uses British spelling (centre, neutralise,
  optimise).

## Changes, commits and pull requests

- Add a line to `CHANGELOG.md` under `[Unreleased]` (Keep a Changelog: Added, Changed, Fixed,
  Removed) for anything a user would notice. Say what changed for the user, not how the code
  changed.
- Commit messages are in the imperative and sentence case, without a type prefix, and say what
  the change does for users (for example "Add TimeSeriesOptions.for_bars for windows that fit
  the bar length").
- The default branch is `master`. Work on a branch and open a pull request.
- A release is a tag `X.Y.Z` (no `v`) on the last commit of a release branch that is merged into
  `master`; pushing it publishes the documentation and uploads the package to PyPI (see
  "Releasing" in `CONTRIBUTING.md`). Don't create or push a tag unless asked.
- Keep each change to what the task needs. Don't reformat or refactor unrelated code in the
  same change.

## Preparing a release

When asked to prepare a release, do step 1 of "Releasing" in `CONTRIBUTING.md` and stop at the
pull request. The release is the branch as it is when tagged, so the branch holds the version
bump and changelog and nothing else.

1. Take the version from the request. If there is none, read `[Unreleased]` in `CHANGELOG.md`,
   suggest one (new features or changed behaviour are a minor bump, fixes alone a patch) and ask.
   If `[Unreleased]` is empty, there is nothing to release: say so and stop.
2. Branch `release-X.Y.Z` from the latest `master` (`git fetch origin master`, then
   `git switch -c release-X.Y.Z origin/master`). If the task assigns a branch name, use that
   one; the steps are the same.
3. Run `uv version X.Y.Z`, which updates `pyproject.toml` and `uv.lock`. In `CHANGELOG.md`, rename
   `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` with today's date (`date +%F`) and add an empty
   `[Unreleased]` above it. Don't add features, fixes or edits to other files. If you find
   something that needs fixing before the release, say so, and commit the fix to the branch only
   if asked.
4. Run everything in "Commands" that CI runs: `pytest`, `ruff check .`, `ruff format --check .`,
   `pyright`, the docs build, and `uv build && uvx twine check dist/*`. If one fails, fix the
   cause only when it is in the release commit itself; otherwise report it.
5. Commit with the message "Release X.Y.Z", push the branch and open a pull request into
   `master`. In the description, list the changelog entries and the checks you ran, and say what
   remains: once CI is green, tag the last commit of the branch locally, merge the branch into
   `master` with a merge commit, and push the tag after CI on `master` is green.

Don't merge the pull request, create a tag or push a tag unless asked. If you are asked to finish
the release, follow steps 2 to 5 of "Releasing" in the order given: tag the branch, merge with a
merge commit (never squash or rebase, which would leave the tag outside `master`), then push the
tag. Never merge `master` into a release branch, because that puts unreleased work into the
release.
