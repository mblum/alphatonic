# Development

Use Python 3.11+ and [uv](https://docs.astral.sh/uv/). Run commands from the repository root:

```sh
uv sync --all-extras --locked      # create .venv with the dev tools and the report extra
uv run pytest                      # about 40 seconds
uv run ruff check .
uv run ruff format --check .
```

The tests use synthetic data and temporary directories only. They run with every warning turned
into an error (`filterwarnings = ["error"]`), so a deprecation in pandas, NumPy or plotly fails
the suite instead of reaching users.

## Where changes belong

| Change | Module | Tests |
| --- | --- | --- |
| Options and their validation | `config.py` | `test_config.py` |
| Input checks, alignment, the evaluation window | `inputs.py` | `test_inputs.py`, `test_calendar.py` |
| Forward-return labels | `returns.py` | `test_returns.py` |
| Correlations, HAC, score buckets | `stats.py` | `test_stats.py` |
| Cross-sectional IC | `cross_section.py` | `test_cross_section.py` |
| Time-series windows, bootstrap, monthly statistics | `time_series.py` | `test_time_series.py` |
| `evaluate`, `Evaluation`, metrics | `evaluation.py` | `test_evaluation.py` |
| Saving and loading | `persistence.py` | `test_persistence.py` |
| Tearsheet | `report/` | `test_report.py` |
| Demo data | `demo.py` | `test_demo.py` |
| Documentation examples | `docs/` | `test_docs.py` |

Preserve the explicit handling of gaps, ties, constants and unavailable statistics: a statistic
that cannot be computed is `NaN` with a status, never zero.

## The reference implementation

`tests/reference.py` holds the original, straightforward formulation of the cross-sectional and
time-series evaluation: one timestamp or window at a time, with pandas. The optimised code in
`src/` must produce the same tables, and `tests/test_reference_equivalence.py` asserts it on
randomised data with gaps, ties, delays, constants and varied bucket counts. When you change
statistical behaviour on purpose, change the reference in the same commit and say so in the
pull request. When you optimise, leave the reference alone.

`tests/test_inference.py` runs fixed-seed simulations that pin the calibration of the
inference: a factor without skill must not be declared significant much more often than 5% of
the time.

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

Python code blocks in `README.md` and `docs/` are executed by `tests/test_docs.py`, in order,
within one namespace per page and in a temporary directory. Put `<!-- notest -->` on the line
above a block that must not run (for example one that needs another library). The structure
follows [Diátaxis](https://diataxis.fr/): tutorials, how-to guides, reference, explanation.
Keep reference pages factual, and put reasons in the explanation pages.

## Releasing

1. Update `CHANGELOG.md` and the version in `pyproject.toml`.
2. Make sure CI is green on the default branch.
3. Tag `vX.Y.Z` and build the distributions with `uv build`; check them with `uvx twine check dist/*`.
4. Upload to PyPI (preferably with [trusted publishing](https://docs.pypi.org/trusted-publishers/)).
