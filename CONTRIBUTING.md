# Contributing

Bug reports with a minimal, runnable example are welcome. Use
`alphatonic.demo.synthetic_market` to share an example without market data. For usage questions,
check the [documentation](README.md) or open an issue.

Statistical changes need a source or a fixed-seed simulation in `tests/test_inference.py`, plus an
update to [the methodology](docs/explanation/methodology.md). Add a changelog entry for changes
users would notice. Work on a branch and open a pull request.

By contributing, you agree that your contribution is licensed under the MIT License.

## Set up local development

Local development uses Python 3.13 (`.python-version`); the library supports Python 3.11–3.14. Use
[uv](https://docs.astral.sh/uv/). Run commands from the repository root:

```sh
uv sync --all-extras --locked      # create .venv with the dev tools and the report extra
uv run pytest                      # in parallel, under 40 seconds
uv run ruff check .
uv run ruff format --check .
uv run pyright                     # type-check src/ using Python 3.11 compatibility
```

Pyright checks `src/` in standard mode using the settings in `pyproject.toml`. The dev group
includes pandas type stubs. Select the project's `.venv` interpreter in your editor so Pylance uses
the same dependencies; it also reads the shared Pyright settings.

The tests use synthetic data and temporary directories only. They run with every warning turned into
an error (`filterwarnings = ["error"]`), so a deprecation in pandas, NumPy or plotly fails the suite
instead of reaching users.

The suite runs on all cores with [pytest-xdist](https://pytest-xdist.readthedocs.io/) and must
finish in under 40 seconds. Add `-n 0` to run it in one process, for example with `--pdb`, and
`--durations=10` to see the slowest tests. Keep new tests fast: use small synthetic panels,
`time_series={"bootstrap_samples": 0}` when the bootstrap is not under test, and a coarse
`rolling_step` when the rolling windows are not.

## Where changes belong

| Change | Module | Tests |
| --- | --- | --- |
| Options and their validation | `config.py` | `test_config.py` |
| Input checks, alignment, the evaluation window | `inputs.py` | `test_inputs.py`, `test_calendar.py` |
| Forward-return labels | `returns.py` | `test_returns.py` |
| Correlations, HAC, score buckets | `stats.py` | `test_stats.py` |
| Cross-sectional IC | `cross_section.py` | `test_cross_section.py` |
| Time-series windows, bootstrap, monthly statistics | `time_series.py` | `test_time_series.py` |
| Signal persistence | `signal_persistence.py` | `test_signal_persistence.py` |
| `evaluate`, `Evaluation`, metrics | `evaluation.py` | `test_evaluation.py` |
| JSON values of results (`to_dict`) | `export.py` | `test_export.py` |
| Saving and loading | `persistence.py` | `test_persistence.py` |
| Studies: trials, the holdout, the board | `study.py` | `test_study.py` |
| The tearsheet | `report/__init__.py`, `report/*figures.py`, `report/templates/` | `test_report.py` |
| Styles shared by both pages | `report/page.py`, `report/static/` | `test_report.py` |
| The list of trials and its server | `report/board.py`, `server.py` | `test_server.py` |
| The `alphatonic` command | `cli.py` | `test_cli.py` |
| Demo data | `demo.py` | `test_demo.py` |
| Documentation examples | `docs/` | `test_docs.py` |

Preserve the explicit handling of gaps, ties, constants and unavailable statistics: a statistic that
cannot be computed is `NaN` with a status, never zero.

## The pages' stylesheet

The tearsheet and the list of trials share one stylesheet, written into each page: [Pico
CSS](https://picocss.com) followed by `report/static/alphatonic.css`. Pico styles the elements
themselves, so templates use semantic HTML (`article`, `details`, `nav`, `table`) and add a class
only where Pico has nothing to say, such as a dense numeric table. Put new rules in
`alphatonic.css`; never edit the vendored file. The accent colour, royal blue (`#4169e1`), is set
there by overriding Pico's `--pico-primary` variables, with a lighter tint for dark mode. The
charts' colours are in `report/figures.py`.

`report/static/pico.classless.min.css` is Pico 2.1.1 from the npm package `@picocss/pico`, with its
licence beside it as `pico.LICENSE.md`. To update it, download the package tarball from the npm
registry, check it against the registry's `integrity` hash, copy the same file and the licence,
change the version in `report/page.py` and `tests/test_report.py`, and look at both pages in a
browser. Check the study board in light and dark mode; the tearsheet uses a light theme.

## The reference implementation

`tests/reference.py` holds the original, straightforward formulation of the cross-sectional and
time-series evaluation: one timestamp or window at a time, with pandas. The optimised code in `src/`
must produce the same tables, and `tests/test_reference_equivalence.py` asserts it on randomised
data with gaps, ties, delays, constants and varied bucket counts. When you change statistical
behaviour on purpose, change the reference in the same commit and say so in the pull request. When
you optimise, leave the reference alone.

`tests/test_inference.py` runs fixed-seed simulations that pin the calibration of the inference: a
factor without skill must not be declared significant much more often than 5% of the time.

## Supported versions

CI runs the suite on Python 3.11 to 3.14, on the newest dependencies, and on the **lowest**
supported versions (`uv run --resolution lowest-direct`). When you raise a lower bound in
`pyproject.toml` say why in the pull request. Run the lowest-bound check locally with:

```sh
uv run --isolated --resolution lowest-direct --python 3.11 pytest
```

## Documentation

The site is built with [Zensical](https://zensical.org/) and the API pages are rendered by
mkdocstrings from docstrings (Google style):

```sh
uv run --group docs zensical serve            # preview
uv run --group docs zensical build --strict   # what CI runs
```

Python code blocks in the root Markdown files and `docs/` are executed by `tests/test_docs.py`, in order, within
one namespace per page and in a temporary directory. Put `<!-- notest -->` on the line above a block
that must not run (for example one that needs another library). The structure follows
[Diátaxis](https://diataxis.fr/): tutorials, how-to guides, reference, explanation. Keep reference
pages factual, and put reasons in the explanation pages. Tutorials should lead a new user through
one working example. How-to guides should solve a specific task. Use short, direct sentences and
British spelling. Check descriptions against the code when editing; a runnable example alone does
not prove that the surrounding explanation is correct.

### Shared pages

Edit `README.md` for the site home page, `CHANGELOG.md` for the changelog, and this file for
contributor guidance. The matching pages under `docs/` include these files at build time using
Zensical's built-in Jinja support. `docs/_includes/` contains symlinks to the three root files;
it is excluded from site navigation and output. The page filters adapt repository-relative links for the
site. Use inline Markdown links rather than reference-style links so these filters can adjust them.

The example tests expand the same includes before running code blocks. After changing links,
build the site with `--strict` and check the rendered destinations. Shared files are watched
when running `zensical serve`.

## Releasing

A release is a tag `X.Y.Z`, without a `v` prefix and equal to the version in `pyproject.toml`,
on the last commit of a release branch that is merged into `master`. What you release is what the
release branch holds: work that lands on `master` while you prepare it waits for the next release.

Pushing the tag runs `.github/workflows/release.yml`, which builds the documentation from the tag
and publishes it to GitHub Pages at <https://mblum.github.io/alphatonic/>, and builds the
distributions from the tag and uploads them to [PyPI](https://pypi.org/project/alphatonic/). The
workflow stops before it publishes anything if the tagged commit is not in the history of
`master`, the tag does not match the version, `CHANGELOG.md` has no section for it, or the
documentation does not build. Tags of any other form, such as `v1.0.0` or `1.0.0rc1`, do not start
it.

1. Branch `release-X.Y.Z` from an up-to-date `master`. Set the version with `uv version X.Y.Z`
   (or `uv version --bump minor`), which updates `pyproject.toml` and `uv.lock`. In
   `CHANGELOG.md`, rename `[Unreleased]` to `[X.Y.Z] - YYYY-MM-DD` and add an empty
   `[Unreleased]` above it. Commit this as "Release X.Y.Z", push the branch and open a pull
   request into `master` so that CI runs. Commit anything that needs fixing to this branch.
   CI tests the pull request merged into `master`, so if `master` has moved it also tests what
   landed there.
2. When CI is green, tag the last commit of the branch. Do not push the tag yet:

    ```sh
    git switch release-X.Y.Z
    git tag -a X.Y.Z -m "alphatonic X.Y.Z"
    ```

3. Merge the branch into `master` with a merge commit. A squash or a rebase merge would leave the
   tagged commit outside `master`. If `master` has moved and the merge conflicts, resolve the
   conflicts in the merge, not by merging `master` into the release branch, which would put
   unreleased work into the tagged commit:
   - In `CHANGELOG.md`, keep what `master` added under the new `[Unreleased]`, above `[X.Y.Z]`.
     Git can merge this file cleanly and still put those lines in the wrong section, so check it.
   - For `uv.lock`, run `uv lock` instead of editing it by hand.

   With a conflict, merge locally: `git switch master && git pull --ff-only`, then
   `git merge --no-ff release-X.Y.Z`. Push the result, or, if `master` is protected, merge on a
   branch off `master` and merge that pull request with a merge commit.
4. Once CI on `master` is green, push the tag:

    ```sh
    git push origin X.Y.Z
    ```

5. Check that the Release workflow succeeds, then delete the release branch. If the check or the
   documentation build fails, nothing has been published: delete the tag
   (`git push --delete origin X.Y.Z`, then `git tag -d X.Y.Z`), fix the cause on the release
   branch, which you keep until the release has succeeded, then tag its new last commit, merge it
   into `master` again and push the tag. If the deployment or the upload fails, fix the settings
   below and re-run the failed jobs. PyPI never accepts a version twice, even after it is deleted,
   so once the upload has succeeded a fix needs a new version.

GitHub Pages needs two settings, made once by a repository admin. Under **Settings → Pages**, set
the source to **GitHub Actions**. Under **Settings → Environments → github-pages**, add a
deployment tag rule `[0-9]*.[0-9]*.[0-9]*`: by default the environment accepts deployments only
from `master`, and it rejects the tag.

The upload uses [trusted publishing](https://docs.pypi.org/trusted-publishers/), so the
repository keeps no PyPI token. On PyPI, add a GitHub publisher with owner `mblum`, repository
`alphatonic`, workflow `release.yml` and environment `pypi`. Before the first release the project
does not exist yet, so add it as a pending publisher at
<https://pypi.org/manage/account/publishing/>; later, a project owner manages it under the
project's **Publishing** settings. In GitHub, under **Settings → Environments**, create the
environment `pypi` and give it the same deployment tag rule, so that only release tags can upload.
