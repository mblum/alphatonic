# Scope and alternatives

alphatonic evaluates predictive association between scores and future returns. It does not build
factors or simulate portfolios, costs or P&L. An information coefficient measures association;
it does not establish that a trading strategy is profitable.

This page defines the boundary between signal evaluation and the surrounding research and
trading tools.

## From association to an investment result

An IC evaluates a score against a chosen target. It does not specify capital allocation, risk
constraints or the trades needed to implement a position. [Boyd et al. (2017)][boyd] model these
as distinct components: forecasts inform decisions that also depend on holdings, risk, transaction
costs and holding costs. Alphatonic supplies diagnostics for the predictive component.

| Question | What alphatonic supplies | What remains outside the evaluation |
| --- | --- | --- |
| Do scores order subsequent targets? | Pearson and rank IC, bucket response | A position-sizing rule and economic value after costs |
| Is the association distinguishable from zero? | Dependence-aware tests and intervals | Validation of the assumptions for the research sample |
| Is the signal useful beyond known exposures? | Association for the supplied scores and targets | A specified benchmark or conditional model and its estimation |
| Does the selected signal generalise? | A trial record and chronological holdout boundary | Training provenance and protection against adaptive holdout reuse |

A high cross-sectional IC can reflect sector or other common exposures. It is not automatically
incremental forecasting skill relative to a benchmark. Similarly, the time-series cosine can
include average exposure to a rising asset. The [timing/static split](targets-and-scaling.md)
helps interpret that contribution, but is not a regression alpha or a causal decomposition.

## Work outside the evaluator

- **Factor construction.** Alphatonic evaluates supplied scores; it does not compute factors or
  train forecasting models.
- **Group analysis and neutralisation.** It does not break results down by sector or remove
  known exposures. Neutralise scores before evaluating if that is the research question.
- **Portfolio construction and P&L.** It does not compute weights, traded turnover, cumulative
  returns, alpha/beta, fees, slippage, financing or market impact. Close-to-close labels do not
  establish that a trade could execute at the observed price. A backtester must supply the
  portfolio and execution assumptions.
- **Research-process validation.** It cannot detect how scores were built or see searches run
  outside a study. [Research validity](research-validity.md) explains these limits and the
  protection a recorded trial history and holdout boundary can provide.

[Signal persistence](signal-persistence.md#why-score-changes-are-not-turnover) describes score
and bucket changes; it does not supply traded notional or a cost estimate. These scope boundaries
are not a roadmap commitment.

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

## References

- Boyd, S., Busseti, E., Diamond, S., Kahn, R. N., Koh, K., Nystrup, P. and Speth, J. (2017).
  [Multi-Period Trading via Convex Optimization][boyd]. *Foundations and Trends in Optimization*,
  3(1), 1–76. Portfolio accounting and decisions conditional on forecasts.
- Alphalens Reloaded. [Performance API](https://alphalens.ml4trading.io/api-reference.html).
  Definitions of IC, mean returns, spreads and turnover for comparison.
- Qlib. [`calc_ic` implementation](https://github.com/microsoft/qlib/blob/main/qlib/contrib/eva/alpha.py).
  Cross-sectional Pearson and rank-correlation evaluation.
- Spectre. [Project documentation](https://github.com/Heerozh/spectre).
  Factor analysis and backtesting interfaces.

[boyd]: https://web.stanford.edu/~boyd/papers/pdf/cvx_portfolio.pdf
