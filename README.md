# alphatonic

[![CI](https://github.com/mblum/alphatonic/actions/workflows/ci.yml/badge.svg)](https://github.com/mblum/alphatonic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mblum/alphatonic/blob/master/LICENSE)

alphatonic is a Python library for testing trading signals. Give alphatonic your scores 
and prices, and it measures how well the scores predict future returns. Inspect the 
results as pandas tables or open them as an interactive HTML report. Organise 
and browse results from a local study server. Start with the
[first-evaluation tutorial](https://mblum.github.io/alphatonic/tutorials/first-evaluation/),
or browse the [docs](https://mblum.github.io/alphatonic/).

With alphatonic you can:

- Measure cross-sectional and time-series information coefficients, including single-asset signals.
- Estimate uncertainty with Newey–West standard errors and a block bootstrap.
- Assess how costly a signal would be to trade, using rank-persistence and bucket-turnover
  statistics.
- Render an offline HTML tearsheet, and browse your trials with `alphatonic serve`.

alphatonic evaluates predictive association; it does not build factors or simulate portfolios,
costs or P&L. See [scope and alternatives](https://mblum.github.io/alphatonic/explanation/scope/).

## Try it

Python 3.11 or newer. Install from [PyPI](https://pypi.org/project/alphatonic/):

```sh
python -m pip install "alphatonic[report]"
```

`alphatonic[report]` adds jinja2 for the tearsheet; evaluation itself depends only on NumPy,
pandas and pydantic.

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, ic=0.04, seed=7)  # or your own tables
result = evaluate(factor, prices, horizons=[1, 5])

result.summary.query("method == 'spearman'")[["horizon", "mean", "ci95_lower", "ci95_upper"]]
result.tearsheet("tearsheet.html")
```

Open `tearsheet.html` in your browser.

## Development

```sh
uv sync --all-extras --locked
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run pyright
```

See [Contributing](https://mblum.github.io/alphatonic/contributing/development/)
for setup, tests and the release process.

## License

[MIT License](https://github.com/mblum/alphatonic/blob/master/LICENSE). Copyright 2026 Manuel Blum.
