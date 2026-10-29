# alphatonic

[![CI](https://github.com/mblum/alphatonic/actions/workflows/ci.yml/badge.svg)](https://github.com/mblum/alphatonic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)

alphatonic is a Python library for testing trading signals. Give it scores and prices to measure how
well the scores predict future returns. Inspect the results as pandas tables or open an interactive
HTML report offline.

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, ic=0.04, seed=7)  # or your own tables
result = evaluate(factor, prices, horizons=[1, 5])

result.summary.query("method == 'spearman'")[["horizon", "mean", "ci95_lower", "ci95_upper"]]
result.tearsheet("tearsheet.html")
```

## What it measures

An **information coefficient (IC)** measures the association between a score and a future return. A
positive IC means higher scores tend to precede higher returns.

- **Cross-sectional IC:** do higher-scored assets outperform lower-scored assets at each bar?
- **Time-series IC:** does each asset earn higher returns after higher scores? This also works
  with a single asset. By default, returns are divided by volatility estimated from past prices.
- **Signal persistence:** how much do scores, ranks and bucket membership change over time?

Both IC analyses run on every evaluation. Confidence intervals account for temporal dependence using
Newey–West standard errors and a block bootstrap. If a statistic cannot be computed, it is `NaN`
with a reason, such as `constant_signal` or `insufficient_assets`.

Horizons count rows of your price table. A return needs an unbroken path of prices; missing prices
are never filled. Results can be saved, reloaded and used to rebuild reports.

For repeated experiments, a `Study` saves each completed trial, counts variants of the same idea and
keeps in-sample return labels out of a holdout period. Browse its results with `alphatonic serve`.

## Install

Python 3.11 or newer. Install from [PyPI](https://pypi.org/project/alphatonic/):

```sh
python -m pip install "alphatonic[report]"
```

`alphatonic[report]` adds plotly and jinja2 for the tearsheet; evaluation itself depends only on
NumPy, pandas and pydantic.

## Inputs

- `prices`: a `DataFrame`, one row per bar, one column per asset, positive prices, `NaN` for
  missing.
- `factor`: a `DataFrame` of scores, or a long-format `Series` indexed by
  `(timestamp, asset)`. Scores may cover a subset of the price rows and assets. Higher scores
  mean higher expected returns.

See [prepare factor and prices](docs/how-to/prepare-inputs.md) for alignment rules, timing, and a
look-ahead check.

## Documentation

| Need | Guide |
| --- | --- |
| First run | [Your first evaluation](docs/tutorials/first-evaluation.md) |
| Your own data | [Prepare factor and prices](docs/how-to/prepare-inputs.md) |
| Choose windows and sample requirements | [Configure an evaluation](docs/how-to/configure-evaluation.md) |
| Read the report | [Read a tearsheet](docs/how-to/read-a-tearsheet.md) |
| Save results | [Save and reload results](docs/how-to/save-and-reload.md) |
| A statistic is missing | [Troubleshooting](docs/how-to/troubleshooting.md) |
| Many variants, one holdout | [Keep every trial in a study](docs/how-to/run-a-study.md) |
| Tables and metric names | [Results and metrics](docs/reference/results.md) |
| What the numbers mean | [Evaluation methodology](docs/explanation/methodology.md) |
| What it does not do | [Design decisions](docs/explanation/design.md) |

See the [changelog](CHANGELOG.md) for release notes.

Preview the site with `uv run --group docs zensical serve`.

## What it does not do

alphatonic measures predictive association and signal persistence. It does not simulate portfolios,
traded turnover, costs or P&L. It does not build factors or neutralise them by group. It cannot
check whether your factor uses future information, and a `Study` counts only the trials it saves.
See [design decisions](docs/explanation/design.md).

## Development

```sh
uv sync --all-extras --locked
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
```

See [Contributing](CONTRIBUTING.md) for setup, tests and the release process.

## Other libraries

You might also consider these open-source alternatives. Each can evaluate signals without running
a trading backtest:

- [Alphalens](https://github.com/quantopian/alphalens) analyses factor values and prices with
  cross-sectional rank IC, quantile returns, turnover and group analysis, and produces factor
  tearsheets.
- [Alphalens Reloaded](https://github.com/stefan-jansen/alphalens-reloaded) is a maintained
  Alphalens fork with the same style of factor analysis and tearsheets.
- [Qlib](https://github.com/microsoft/qlib) is a broader research platform for data, models,
  experiment recording and backtesting. Its `calc_ic` function evaluates predictions against
  labels using cross-sectional Pearson and rank IC.
- [Spectre](https://github.com/Heerozh/spectre) combines a GPU-capable factor engine with factor
  analysis over multiple periods and backtesting. Its analysis output can also be used with
  Alphalens.

## License

[MIT License](LICENSE). Copyright 2026 Manuel Blum.
