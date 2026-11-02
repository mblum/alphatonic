# alphatonic docs

alphatonic measures how well trading signals predict future returns. Give it signal scores and
prices in pandas DataFrames to produce information coefficients, uncertainty estimates and offline HTML reports.

## What alphatonic does

alphatonic evaluates predictive association between supplied scores and future returns. An
information coefficient (IC) does not establish that a trading strategy is profitable. The library
does not build factors, neutralise exposures, construct portfolios or simulate costs and P&L.
Close-to-close labels do not establish that a trade could execute at the observed price.

A high IC can reflect sector or other common exposures rather than skill beyond a benchmark.
Neutralise scores before evaluating if that is the research question. The
[timing and static split](explanation/targets-and-scaling.md#timing-and-average-exposure) helps
interpret average exposure, while [signal persistence](explanation/signal-persistence.md#why-score-changes-are-not-turnover)
describes score changes rather than traded turnover. A study records trials and a holdout boundary,
but cannot establish how scores were built or prevent adaptive holdout reuse; see
[trials and holdouts](explanation/research-validity.md).

## Getting started

Evaluate a signal on synthetic data, inspect its information coefficients and confidence intervals,
and create an offline HTML tearsheet. You need Python 3.11 or newer; no market data is required.
The tutorial includes installation.

[Start your first evaluation](tutorials/first-evaluation.md){ .md-button .md-button--primary }

## Where to go from there

Once your first tearsheet is open, these stops take you from the synthetic example to your own research.

| Next stop | Read |
| --- | --- |
| Bring your own factor and prices | [Prepare factor and prices](how-to/prepare-inputs.md) |
| Make sense of the charts and tables in the report | [Read a tearsheet](how-to/read-a-tearsheet.md) |
| Tune windows and sample requirements | [Configure an evaluation](how-to/configure-evaluation.md) |
| Find out why a statistic is `NaN` | [Troubleshooting](how-to/troubleshooting.md) |
| Learn what the numbers mean and how much to trust them | [Evaluation methodology](explanation/methodology.md) |

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

Before comparing IC values from different libraries, align the target, horizon, delay, paired
sample, tie handling, universe and aggregation weights. Matching a column name does not ensure
that two estimates answer the same question. In particular, a package's portfolio return spread
need not have the same weighting or normalisation as alphatonic's descriptive bucket difference.

## Get support

Check [troubleshooting](how-to/troubleshooting.md), or
[report an issue](https://github.com/mblum/alphatonic/issues).

## Project

See what changed in each release in the
[changelog](https://github.com/mblum/alphatonic/blob/master/CHANGELOG.md). To work on alphatonic
itself, read the [contributing guide](https://github.com/mblum/alphatonic/blob/master/CONTRIBUTING.md).
