# alphatonic

Evaluate predictive signals (alpha factors) with information coefficients you can trust.
Give alphatonic your scores and prices; it measures how well the scores rank assets at each
timestamp (**cross-sectional IC**) and how well they predict each asset's own returns over
time (**time-series IC**), with dependence-aware uncertainty, an explicit reason for every
statistic it cannot compute, and an interactive tearsheet that opens offline.

It is a successor to [alphalens](https://github.com/quantopian/alphalens): the same inputs
(a factor and prices), a more careful treatment of inference and missing data, and a
time-series view for markets with few assets. See
[migrate from alphalens](how-to/migrate-from-alphalens.md) for what carries over and what
does not.

```python
from alphatonic import evaluate
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=500, ic=0.04, seed=7)  # or your own tables
result = evaluate(factor, prices, horizons=[1, 5])

result.summary.query("method == 'spearman'")[["horizon", "mean", "ci95_lower", "ci95_upper"]]
result.tearsheet("tearsheet.html")  # needs: pip install "alphatonic[report]"
```

## What you get

- **Exact labels.** A forward return exists only if every price from the observation to the
  end of the horizon exists, so gaps never stretch a horizon. Horizons count rows of your
  price table, so trading calendars, 24/7 grids and rebalance dates all work.
- **Honest uncertainty.** The mean cross-sectional IC carries a Newey–West standard error with
  at least `horizon − 1` lags, because overlapping labels make adjacent ICs dependent. Time-series
  IC carries circular block-bootstrap intervals.
- **Nothing is silently zero.** An IC that cannot be computed is `NaN` with a `status` such as
  `constant_signal` or `insufficient_assets`. Summaries keep missing periods in their time
  positions.
- **Two views of "predictive".** Cross-sectional IC asks whether scores pick winners among
  assets. Time-series IC asks whether an asset's own score predicts its own return, per asset,
  per calendar month and over rolling windows.
- **A reproducible artifact.** Results are tables you can save, reload and re-render. The
  tearsheet is one HTML file with no network access needed.

## Start here

| I want to… | Read |
| --- | --- |
| Run my first evaluation | [Your first evaluation](tutorials/first-evaluation.md) |
| Feed in my own data correctly | [Prepare factor and prices](how-to/prepare-inputs.md) |
| Evaluate one asset or a small universe | [Choose an evaluation mode](how-to/choose-evaluation-mode.md) |
| Interpret the report | [Read a tearsheet](how-to/read-a-tearsheet.md) |
| Keep results and rebuild reports | [Save and reload results](how-to/save-and-reload.md) |
| Rank many factors or parameter values | [Compare factors and parameters](how-to/compare-factors.md) |
| Move from alphalens | [Migrate from alphalens](how-to/migrate-from-alphalens.md) |
| Find out why a statistic is missing | [Troubleshooting](how-to/troubleshooting.md) |
| Look up a function or a table column | [API](reference/api.md) · [Results and metrics](reference/results.md) |
| Understand the statistics | [Evaluation methodology](explanation/methodology.md) |
| Know what it deliberately does not do | [Design decisions](explanation/design.md) |

## Scope

alphatonic measures **predictive association** between scores and forward returns. It does not
simulate portfolios, execution, costs or P&L, and it does not build factors. Returns are simple
close-to-close returns and exclude fees, slippage and financing. Statistical tools cannot repair
look-ahead in your factor, a biased universe, or selection among many tried signals; the
[methodology](explanation/methodology.md) lists what the uncertainty estimates do and do not cover.

## Install

alphatonic needs Python 3.11 or newer.

```sh
pip install "alphatonic[report] @ git+https://github.com/mblum/alphatonic"
```

The `report` extra adds plotly and jinja2 for the tearsheet; evaluation itself needs only
NumPy, pandas and pydantic. A release on PyPI is planned; until then install from the
repository as above.
