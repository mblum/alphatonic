# Contributing

Bug reports with a minimal, runnable example are welcome. Use
`alphatonic.demo.synthetic_market` to share an example without market data. For usage questions,
check the [documentation](https://mblum.github.io/alphatonic/) or open an issue.

Statistical changes need a source or the calibration evidence described in
[TESTING.md], plus an update to `docs/explanation/methodology.md`. Add a changelog
entry for changes users would notice. Work on a branch and open a pull request.

[TESTING.md] is the guide to the test suite: its layout, how expected values are
derived, statistical validation, the checks a pull request must pass and the commands that run
them.

By contributing, you agree that your contribution is licensed under the MIT License.

## Set up local development

Local development uses Python 3.13 (`.python-version`); the library supports Python 3.11–3.14. Use
[uv](https://docs.astral.sh/uv/). Run commands from the repository root:

```sh
uv sync --all-extras --locked      # create .venv with the dev tools
uv run ruff check .
uv run ruff format --check .
uv run pyright                     # type-check src/ using Python 3.11 compatibility
```

Pyright checks `src/` in standard mode using the settings in `pyproject.toml`. The dev group
includes pandas type stubs. Select the project's `.venv` interpreter in your editor so Pylance uses
the same dependencies; it also reads the shared Pyright settings.

To run the tests, follow "Local test execution" in [TESTING.md].

## Where changes belong

| Change | Module |
| --- | --- |
| Options and their validation | `config.py` |
| Input checks, alignment, the evaluation window | `inputs.py` |
| Forward-return labels | `returns.py` |
| Correlations, HAC, score buckets | `stats.py` |
| Cross-sectional IC | `cross_section.py` |
| Time-series windows, bootstrap, monthly statistics | `time_series.py` |
| Signal persistence | `signal_persistence.py` |
| `evaluate`, `Evaluation`, metrics | `evaluation.py` |
| JSON values of results (`to_dict`) | `export.py` |
| Saving and loading | `persistence.py` |
| Studies: trials, the holdout, the board | `study.py` |
| The tearsheet | `report/__init__.py`, `report/templates/` |
| The tearsheet's charts | `report/*figures.py`, `report/static/alphatonic.js` |
| Styles shared by both pages | `report/page.py`, `report/static/` |
| The list of trials and its server | `report/board.py`, `server.py` |
| The `alphatonic` command | `cli.py` |
| Demo data | `demo.py` |
| Documentation examples | `docs/` |

The tests that belong to each module are assigned in [TESTING.md].

Preserve the explicit handling of gaps, ties, constants and unavailable statistics: a statistic that
cannot be computed is `NaN` with a status, never zero.

## The pages' stylesheet and charts

The tearsheet and the list of trials share one stylesheet, written into each page: [Pico
CSS](https://picocss.com) followed by `report/static/alphatonic.css`. Pico styles the elements
themselves, so templates use semantic HTML (`article`, `details`, `nav`, `table`) and add a class
only where Pico has nothing to say, such as a dense numeric table. Put new rules in
`alphatonic.css`; never edit the vendored file. The accent colour, royal blue (`#4169e1`), is set
there by overriding Pico's `--pico-primary` variables, with a lighter tint for dark mode.

The charts' colours are variables in the same file, each with a dark value: `--at-c1` to `--at-c8`
for series (taken in order, never cycled), `--at-context` and `--at-zero` for the lines that give
context, and `--at-low`, `--at-mid` and `--at-high` for the scale of the heatmaps. Python never names
a colour: a chart specification names a slot. Check a new colour for contrast with the card colour
of both themes (white and `#181c25`) and for separation from its neighbours under colour-vision
deficiency, as the existing ones were.

The charts are drawn by [Observable Plot](https://observablehq.com/plot/) and [d3](https://d3js.org),
vendored in `report/static/` with their licences, and by `report/static/alphatonic.js`.
`report/figures.py` and `report/ts_figures.py` compute everything a chart shows and write it as a
specification, which is plain data of one of five kinds (`lines`, `rolling`, `heatmap`, `bars`,
`intervals`); the script only draws. [TESTING.md] describes how the specifications and
the drawn pages are tested. After you change the script, also look at it yourself: open a tearsheet
in light and dark mode, hover each kind of chart, open the closed panels and the second tab, narrow
the window, and print once with a dark system: paper is meant to come out light.

`report/static/pico.classless.min.css` is Pico 2.1.1 from the npm package `@picocss/pico`, with its
licence beside it as `pico.LICENSE.md`. `plot.umd.min.js` is Observable Plot 0.6.17 and `d3.min.js`
is d3 7.9.0 (Plot's build needs d3 as the global `d3`), each from the file `dist/` of its npm
package, with the licence beside it. To update one, download the package tarball from the npm
registry, check it against the registry's `integrity` hash, copy the same file and the licence,
change the version in `report/page.py`, and look at both pages in a
browser, in light and dark mode.

## Supported versions

The library supports Python 3.11 to 3.14 and the lower bounds of the dependencies declared in
`pyproject.toml`. "Quality gates" and "Minimum and newest dependencies" in
[TESTING.md] say how both ends are tested. When you raise a lower bound, say why in the
pull request.

## Documentation

The site is built with [Zensical](https://zensical.org/) and the API pages are rendered by
mkdocstrings from docstrings (Google style):

```sh
uv run --group docs zensical serve            # preview
uv run --group docs zensical build --strict   # what CI runs
```

Python code blocks in the root Markdown files and `docs/` must actually run; the documentation tests
in [TESTING.md] execute them. The structure follows
[Diátaxis](https://diataxis.fr/): tutorials, how-to guides, reference, explanation. Keep reference
pages factual, and put reasons in the explanation pages. Tutorials should lead a new user through
one working example. How-to guides should solve a specific task. Use short, direct sentences and
British spelling. Check descriptions against the code when editing; a runnable example alone does
not prove that the surrounding explanation is correct.

### Root files

Edit `README.md` for the GitHub and PyPI introduction and `docs/index.md` for the documentation
home page. These are independent pages. The changelog (`CHANGELOG.md`) and contributor guidance
(this file) live only on GitHub and are not part of the site.

Use absolute web URLs in the root Markdown files so their links also work on PyPI and GitHub, and
make links to the site and to files on `master` name an existing page or file. After changing
links, build the site with `--strict` and check the rendered destinations.

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
   request into `master`. Commit anything that needs fixing to this branch.
   CI runs on every push to a `release-*` branch, so it tests the last commit exactly as it will
   be tagged. It also runs on the pull request, merged into `master`, which shows what the merge
   will do; GitHub skips that run while the pull request has a merge conflict.
2. When CI on the branch is green, tag its last commit. Do not push the tag yet:

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

[TESTING.md]: https://github.com/mblum/alphatonic/blob/master/TESTING.md
