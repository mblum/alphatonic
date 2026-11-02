# Trials, selection and the holdout

A confidence interval describes uncertainty for a specified analysis. Choosing that analysis
because it performed best introduces another source of error. Alphatonic's `Study` records trials
and enforces a chronological boundary, but the researcher still determines which hypotheses,
data and comparisons belong to the investigation.

## Selection changes the question

Suppose many signals have no predictive association. Their estimated ICs will nevertheless differ
because the sample is finite. Choosing the largest observed IC favours both skill, if present,
and favourable estimation error. Optimising an evaluation criterion can therefore overfit it, as
[Cawley and Talbot (2010)][cawley] demonstrate for model selection. Their experiments concern
machine learning rather than financial IC, but the distinction between model fitting and
selection on a noisy criterion applies here too.

In factor research, [Harvey, Liu and Zhu (2016)][hlz] study how extensive testing changes
significance thresholds. Their findings motivate recording the search that produced a signal.
Their numerical thresholds are specific to their analysis; alphatonic does not impose a universal
t-statistic cutoff of 3.

## What the study adjustment means

A study counts every saved evaluation with the same family name, across parameter variants and
both in-sample and holdout evaluations. Repeating a variant creates another trial. The board
adjusts each displayed p-value $p$ using

$$
p_{\mathrm{adjusted}}=\min(1,mp),
$$

where $m$ is the recorded family trial count. This is the single-step Bonferroni rule described
by [Harvey, Liu and Zhu (2016, §3.4.1)][hlz]. For a fixed family of $m$ hypotheses with valid
individual p-values, the union bound gives

$$
\Pr(\text{at least one false rejection})
\leq \sum_{j\in\mathcal H_0}\Pr(p_j\leq\alpha/m)
\leq |\mathcal H_0|\,\alpha/m\leq\alpha,
$$

where $\mathcal H_0$ is the set of true nulls and $\alpha$ is the chosen family-wise error level.
No independence between tests is required. For example, a p-value of 0.003 becomes 0.06 after
20 trials. Correlated variants can make the rule conservative, but do not justify ignoring trials.

The adjustment does not estimate the probability that a signal is false. It also does not repair
miscalibrated input p-values, optimistic effect estimates or selection of the family after seeing
the results. Confidence intervals and ICs remain the individual trial's estimates; the study does
not construct simultaneous or selection-adjusted intervals.

### What the count leaves out

The board applies the trial count separately to the cross-sectional rank, time-series rank and
time-series cosine p-values. It does not expand the count for choosing among these metrics,
horizons, asset subsets or date ranges. If a fixed search compares all three metrics over $H$
horizons in $m$ trials, there are up to $3Hm$ tests to include in a corresponding Bonferroni
family. The board's `p × trials` covers only the $m$ multiplier.

Variants run outside the study are invisible. So are abandoned ideas that influenced the final
design without becoming saved evaluations. A family name groups records; it does not discover
which signals test the same research question. Grouping only unsuccessful trials separately would
understate the search behind the selected result.

An adaptive search creates a further problem: each new hypothesis can depend on earlier results
from the same data. Multiplying by the number of recorded trials does not, by itself, establish
the individual p-values' validity under that selection process. A complete trial log makes the
process inspectable; it is not an adaptive-inference procedure.

## What the chronological boundary protects

For a holdout boundary $b$, an in-sample evaluation uses scores before $b$ and only labels whose
endpoints are also before $b$. A score just before the boundary cannot borrow a future holdout
price for its return. Holdout scores start at or after $b$. Past prices may warm up the holdout's
volatility estimate because those prices were already available at the score timestamp.

These rules constrain evaluation inputs, not their provenance. A model trained on the full
history, a full-sample scaling transform or revised data unavailable at the original timestamp
can already contain future information when passed to `evaluate()`. For fitted signals, training
labels must also finish before the relevant validation boundary. A chronological split of score
timestamps alone is insufficient when those training labels extend beyond the split.

The caller controls the training procedure and data snapshots. Alphatonic neither retrains models
inside each window nor implements cross-validation, purging or embargo schedules. Its
[input guide](../how-to/prepare-inputs.md) covers data preparation; the
[study guide](../how-to/run-a-study.md) covers the enforced boundary.

## Why repeated holdout use matters

A holdout evaluates a choice made without its outcomes. Once a holdout result changes the signal,
target, horizon or eligibility rules, that sample has informed the next choice. Recording the
next evaluation as another holdout use makes this visible, but does not restore independence
from the selection process.

[Dwork et al. (2015)][dwork] study this failure under adaptive data reuse and develop procedures
that restrict how information is released from a holdout. Alphatonic does not implement those
procedures. An ordinary study exposes results directly; it is not a reusable-holdout algorithm.
For a final confirmatory assessment, reserve data that have not guided the specification and
record the decision rule before inspecting them.

## Missingness and the research population

The complete pairs in an evaluation need not represent the intended universe. If missing returns
concentrate around suspensions or distress, the measured association describes a selected sample.
A universe that excludes delisted assets can similarly favour survivors. Pair coverage measures
availability against the supplied price grid, not against a historical universe.

Keeping gaps on the grid preserves lag meaning; it does not correct selection caused by those
gaps. Neither a dependence-aware standard error nor a trial-count adjustment repairs this
population mismatch. Record the universe and data availability rules alongside the evaluation.

## Interpret evidence in context

The [ASA statement (2016)][asa] distinguishes a p-value from both an effect size and the
probability that a hypothesis is true. In alphatonic, a small p-value can accompany an IC too
small to matter economically. A large p-value can accompany a wide interval that leaves useful
effects unresolved. Neither threshold crossing establishes a profitable strategy.

Read the IC, its interval, sample coverage and temporal diagnostics together. Record the target,
universe, horizon, selection history and holdout uses alongside them. An association that survives
those checks still needs portfolio construction and execution assumptions to assess economic
value; [scope and alternatives](scope.md) explains that boundary.

## References

- Cawley, G. C. and Talbot, N. L. C. (2010). [On Over-fitting in Model Selection and Subsequent
  Selection Bias in Performance Evaluation][cawley]. *Journal of Machine Learning Research*,
  11, 2079–2107. Selection can overfit a noisy performance criterion.
- Harvey, C. R., Liu, Y. and Zhu, H. (2016). [… and the Cross-Section of Expected Returns][hlz].
  *The Review of Financial Studies*, 29(1), 5–68. Multiple-testing families, Bonferroni and the
  consequences of unobserved tests in factor research.
- Dwork, C., Feldman, V., Hardt, M., Pitassi, T., Reingold, O. and Roth, A. (2015).
  [Generalization in Adaptive Data Analysis and Holdout Reuse][dwork]. arXiv:1506.02629.
  Adaptive reuse and protected holdout mechanisms; these are not implemented by `Study`.
- American Statistical Association (2016). [Statement on Statistical Significance and
  P-Values: six principles][asa]. Interpretation of p-values, effect size and full reporting.

[cawley]: https://jmlr.org/papers/v11/cawley10a.html
[hlz]: https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF
[dwork]: https://arxiv.org/abs/1506.02629
[asa]: https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf
