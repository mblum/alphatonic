# alphatonic

[![CI](https://github.com/mblum/alphatonic/actions/workflows/ci.yml/badge.svg)](https://github.com/mblum/alphatonic/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](https://github.com/mblum/alphatonic/blob/master/LICENSE)

alphatonic is a Python library for testing trading signals. Give it scores and prices to measure how
well the scores predict future returns. Inspect the results as pandas tables or open an interactive
HTML report offline.

**[Documentation](https://mblum.github.io/alphatonic/) ·
[First evaluation](https://mblum.github.io/alphatonic/tutorials/first-evaluation/) ·
[API reference](https://mblum.github.io/alphatonic/reference/api/)**

<!-- Screenshot slot: add a readable tearsheet crop using synthetic data, descriptive alt text
and a caption. Link it to the documentation guide to reading a tearsheet. -->

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

- Measure cross-sectional and time-series information coefficients, including single-asset signals.
- Estimate uncertainty with Newey–West standard errors and a block bootstrap.
- Save and reload results, and keep every completed trial in a `Study`.

alphatonic evaluates predictive association; it does not build factors or simulate portfolios,
costs or P&L. See [scope and alternatives](https://mblum.github.io/alphatonic/explanation/scope/).

[Contributing](https://mblum.github.io/alphatonic/contributing/development/) ·
[MIT License](https://github.com/mblum/alphatonic/blob/master/LICENSE)
