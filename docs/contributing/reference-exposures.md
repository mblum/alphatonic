# Reference exposures for future cost analysis

This is a design proposal, not an available feature or a release commitment. Current [persistence
diagnostics](../explanation/signal-persistence.md) measure score changes only.

A future cost analysis must be explicitly requested and record its position rule. The intended
initial reference rules are:

- **Cross-section:** subtract the mean cross-sectional rank, divide by the sum of absolute centred
  ranks. Gross exposure is 1, net exposure is 0 (50% long and 50% short). Constant ranks are
  unavailable. Eligibility and ranks use only information available at the signal timestamp.
- **Time series:** `w[i,t] = allocation[i] * score[i,t] * target_vol / estimated_vol[i,t]`.
  Allocation, score units, target volatility, volatility floor and exposure cap must be explicit.
  Both volatility quantities must use the same time unit. Zero score means zero exposure.
  This is an asset risk-budget rule, not a guaranteed portfolio volatility target.

Do not silently rescale scores by their full-sample magnitude for trading. Any fitted score
normalisation must be trained before the evaluation period or updated causally. The diagnostic
normalisation above is descriptive, not an instruction to size positions.

The execution contract must also specify delay, rebalance interval and phase, initial positions,
terminal liquidation, asset type, and missing-score/price handling. A missing price cannot imply a
free liquidation. Future returns must never determine position eligibility. Start with
non-overlapping one-bar accounting; a five-bar predictive label is not five independent P&L bars.
For slower rebalancing, hold the chosen position according to the accounting convention between
scheduled decisions. Any overlapping holding sleeves must be aggregated before measuring trades.

Report `sum(abs(w_target[t] − w_target[t−1]))` as **target-exposure change**, a proxy. Actual traded
notional compares targets with drifted pre-trade holdings; cash securities and futures need their
respective holdings/contract accounting. Volatility scaling can require trading even when scores are
constant. The first implementation should support only explicitly documented asset accounting,
rather than implicitly treating every price series as cash equity.

Use full buys-plus-sells traded notional divided by pre-trade NAV as the primary turnover unit,
excluding the financing cash leg. Label the alternative half-notional convention explicitly. For
one-way cost `c` in bps of traded notional, cost drag in bps of NAV is `c * turnover`. Selling 10%
and buying 10% of NAV at 5 bps costs 1 bp of NAV. Distinguish borrowing and funding from trading
costs. Linear cost scenarios are assumptions; capacity requires portfolio size, liquidity data and
calibrated impact. Costs cannot be subtracted from IC.

