# Design decisions

Why alphatonic behaves the way it does, what it deliberately leaves out, and how it relates to
alphalens.

## Principles

**An unavailable statistic is `NaN` with a reason.** A correlation of a constant is undefined,
not zero, and an interval without enough data is absent. Every table that can be incomplete carries a
`status`, so "no signal" and "no information" cannot be confused.

**Bars, not clock time.** The rows of the price table define the calendar. This keeps the core free
of market-specific assumptions: a business-day table, a 24/7 hourly grid, and irregular rebalance
dates all follow the same rule, and only the calendar-month and rolling-window views use timestamps.
The cost is that a missing *row* looks like a shorter gap than a missing *price*; the
[input guide](../how-to/prepare-inputs.md#calendars) shows how to put missing 24/7 bars on the grid.

**Exact labels over maximal data.** A label needs an unbroken path of prices. This discards more
data than skipping or filling gaps would, and it guarantees that "the 24-bar return" always spans
24 bars.

**Honest uncertainty over convenient uncertainty.** Cross-sectional IC uses a HAC standard
error, and time-series IC a block bootstrap, because both outputs depend on time ordering. The
price is wider intervals than a naive t-test.

**Tables first.** The result is a handful of tidy DataFrames. The tearsheet is a rendering of them;
it recomputes nothing, so a saved result reproduces the same report.

**Small dependency footprint.** Evaluation needs NumPy, pandas and pydantic (for validated, immutable
configuration). Plotly and Jinja2 are an optional extra for the report. There is no progress-bar
dependency; a hook lets you plug in your own.

## What alphatonic does not do

- **Portfolio construction and P&L.** No weights, turnover, cumulative returns, alpha/beta or
  costs. Use a backtester for those and alphatonic to decide whether a signal is worth backtesting.
- **Factor construction.** It evaluates scores; it does not compute them.
- **Group (sector) analysis and neutralisation.** Neutralise the factor before evaluating.
- **Look-ahead detection.** It cannot see how your factor was built. The input guide includes a
  truncation test you can run.
- **Multiple-testing control.** It cannot know how many alternatives you tried.

These are boundaries, not a roadmap commitment: some, such as turnover and group analysis, are
natural extensions if there is demand.

## Relation to alphalens

alphalens popularised the factor-plus-prices workflow and its vocabulary (IC, quantiles,
tear sheets), and alphatonic keeps the inputs familiar. It differs on purpose:

| Topic | alphalens | alphatonic |
| --- | --- | --- |
| IC significance | t-test of mean IC. | Newey–West HAC with at least `horizon − 1` lags. |
| Time-series IC | Not provided. | Per asset, per month, rolling and bootstrapped. |
| Missing data | Drops rows; fails above `max_loss`. | Keeps every timestamp with a status. |
| Horizons | Periods, named in the inferred frequency of the dates. | Bars: rows of the price table. |
| Report | Matplotlib tear sheets for notebooks. | Standalone interactive HTML. |
| Portfolio-style analysis | Returns, turnover, events, groups. | Not provided. |

See [migrate from alphalens](../how-to/migrate-from-alphalens.md) for a practical mapping.

## Performance model

Cross-sectional work is vectorised over timestamps in blocks of 256 rows, which bounds temporary
arrays: thousands of assets over thousands of bars take seconds. Time-series work evaluates each
window with array operations over all assets at once. The block bootstrap is the expensive part:
each draw recomputes every asset's rank correlation, so its cost is draws × assets × bars.
It is deterministic and single-threaded. A reference implementation of the original,
timestamp-by-timestamp formulation lives in the test suite and the optimised code is checked
against it on randomised data, including gaps, ties, delays and constant scores.
