# Scope and alternatives

alphatonic evaluates predictive association between scores and future returns. It does not build
factors or simulate portfolios, costs or P&L. An information coefficient measures association;
it does not establish that a trading strategy is profitable.

See [evaluation methodology](methodology.md) for the statistical assumptions.

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

