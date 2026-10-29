# alphatonic

[![CI](https://github.com/mblum/alphatonic/actions/workflows/ci.yml/badge.svg)](https://github.com/mblum/alphatonic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mblum/alphatonic/blob/master/LICENSE)

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

## Install

Python 3.11 or newer. Install from [PyPI](https://pypi.org/project/alphatonic/):

```sh
python -m pip install "alphatonic[report]"
```

`alphatonic[report]` adds jinja2 for the tearsheet; evaluation itself depends only on NumPy,
pandas and pydantic.

## Main concepts

Give alphatonic scores and prices as pandas tables, with one row per bar and one column per asset;
scores can also be a Series indexed by timestamp and asset. Higher scores mean higher expected
returns. Horizons count price rows, and missing prices are never filled to create returns.

An **information coefficient (IC)** measures how scores relate to future returns. Cross-sectional
IC compares assets at each bar; time-series IC measures each asset over time and also works for a
single asset. Signal persistence tracks changes in scores, ranks and bucket membership. Confidence
intervals account for temporal dependence using Newey–West standard errors and a block bootstrap.
Unavailable statistics are `NaN` with a reason.

Results are pandas tables that you can save, reload and turn into an offline HTML report. A `Study`
keeps every completed trial and separates in-sample return labels from a holdout period.

alphatonic evaluates predictive association; it does not build factors or simulate portfolios,
costs or P&L. See the [documentation](https://mblum.github.io/alphatonic/) for tutorials, input
requirements, methodology and the API reference.

## Development

```sh
uv sync --all-extras --locked
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
```

See [Contributing](https://mblum.github.io/alphatonic/contributing/development/)
for setup, tests and the release process.

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

[MIT License](https://github.com/mblum/alphatonic/blob/master/LICENSE). Copyright 2026 Manuel Blum.
