# alphatonic

[![CI](https://github.com/mblum/alphatonic/actions/workflows/ci.yml/badge.svg)](https://github.com/mblum/alphatonic/actions/workflows/ci.yml)
[![License: Apache 2.0](https://img.shields.io/badge/license-Apache%202.0-blue.svg)](LICENSE)

Evaluate predictive signals (alpha factors) with information coefficients you can trust, and see
the result in an interactive tearsheet that opens offline. A successor to
[alphalens](https://github.com/quantopian/alphalens): the same inputs, a more careful treatment of
inference and missing data, and a time-series view for markets with few assets.

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, ic=0.04, seed=7)  # or your own tables
result = evaluate(factor, prices, horizons=[1, 5])

result.summary.query("method == 'spearman'")[["horizon", "mean", "ci95_lower", "ci95_upper"]]
result.tearsheet("tearsheet.html")
```

## Why

- **Cross-sectional and time-series IC.** Does the factor rank assets at each timestamp? Does
  an asset's own score predict its own return, per asset, per calendar month, over rolling windows?
- **Uncertainty that respects dependence.** Overlapping forward returns make adjacent ICs
  dependent. The mean IC has a Newey–West standard error with at least `horizon − 1` lags, and
  time-series IC has circular block-bootstrap intervals.
- **No silent zeros.** A statistic that cannot be computed is `NaN` with a status such as
  `constant_signal`, `insufficient_assets` or `low_coverage`.
- **Exact labels.** A forward return needs an unbroken path of prices, so a gap never stretches a
  horizon. Horizons count rows of your price table: trading days, 24/7 hours, rebalance dates.
- **Plain tables.** The result is a few tidy DataFrames that you can save, reload and re-render.
  The tearsheet is one HTML file.

## Install

Python 3.11 or newer. A release on PyPI is planned; install from the repository for now:

```sh
pip install "alphatonic[report] @ git+https://github.com/mblum/alphatonic"
```

`alphatonic[report]` adds plotly and jinja2 for the tearsheet; evaluation itself depends only on
NumPy, pandas and pydantic.

## Inputs

- `prices`: a `DataFrame`, one row per bar, one column per asset, positive prices, `NaN` for
  missing.
- `factor`: scores of the same shape, or an alphalens-style `Series` indexed by
  `(timestamp, asset)`. Larger means a higher expected return.

See [prepare factor and prices](docs/how-to/prepare-inputs.md) for alignment rules, timing, and a
look-ahead check.

## Documentation

| Need | Guide |
| --- | --- |
| First run | [Your first evaluation](docs/tutorials/first-evaluation.md) |
| Your own data | [Prepare factor and prices](docs/how-to/prepare-inputs.md) |
| Which mode? Few assets? Daily bars? | [Choose an evaluation mode](docs/how-to/choose-evaluation-mode.md) |
| Coming from alphalens | [Migrate from alphalens](docs/how-to/migrate-from-alphalens.md) |
| A statistic is missing | [Troubleshooting](docs/how-to/troubleshooting.md) |
| Tables and metric names | [Results and metrics](docs/reference/results.md) |
| What the numbers mean | [Evaluation methodology](docs/explanation/methodology.md) |
| What it does not do | [Design decisions](docs/explanation/design.md) |

Preview the site with `uv run --group docs zensical serve`.

## What it does not do

alphatonic measures predictive association. It does not simulate portfolios, turnover, costs or
P&L, build factors, or neutralise by group, and it cannot detect look-ahead in your factor or
correct for the number of signals you tried. See [design decisions](docs/explanation/design.md).

## Development

```sh
uv sync --all-extras --locked
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and [development](docs/contributing/development.md).

## License

[Apache License 2.0](LICENSE). Copyright 2026 Manuel Blum.
