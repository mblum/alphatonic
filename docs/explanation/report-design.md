# Report design

The tearsheet puts estimates, uncertainty and sample coverage together. It shows every configured
horizon so readers can compare them without a horizon being selected for its performance.

The overview uses rank IC and the difference between the highest and lowest score buckets. Detailed
panels show Pearson, cosine, variation across assets and changes over time. A missing statistic
stays missing; sample and inference statuses explain why.

The report omits p-values. A study board shows them: the cross-sectional, time-series and cosine
groups each give a p-value beside its adjustment for the recorded trial count. The underlying
result tables retain the inference statistics.

The list of trials is read like a leaderboard and borrows from public ones, such as
[Arena's agent leaderboard](https://arena.ai/leaderboard/agent/code) and
[BenchLM](https://benchlm.ai): a row of summary tiles above the table, a rank in the first column,
the horizon as a segmented control, and one graphic in each row that carries the headline number.
Here the graphic is the rank IC with its 95% interval on a single axis, the same for every row. A
large but imprecise estimate then looks different from a small, precise one, and an interval that
crosses zero is seen before any number is read.

Two choices go against what a leaderboard usually does. The tile for the highest rank IC always
shows its adjusted p-value, because the best of many trials is picked by being the best. And rows
are ranked only when the list is sorted by a statistic, so the newest-first order is never mistaken
for merit. The interval is the trial's own and is not adjusted for the trials of its family; `p ×
trials` is.

Essential results stay visible. Optional diagnostics use one level of expandable panels, and horizon
tabs keep long time-series sections manageable. Both pages, the tearsheet and the list of trials,
follow the system's light or dark setting, and the charts take their colours from the same
stylesheet variables, so they change with the page. On paper they are always light. Styles and chart code are embedded so the
report works offline.

## Interface design references

The report follows the [GOV.UK accordion
guidance](https://design-system.service.gov.uk/components/accordion/) by keeping essential results
visible and avoiding nested disclosures. Semantic headings and table markup follow W3C guidance on
[headings](https://www.w3.org/WAI/tutorials/page-structure/headings/) and [table
captions](https://www.w3.org/WAI/tutorials/tables/caption-summary/). Narrow-screen layouts contain
horizontal scrolling to data regions, following the [W3C reflow
guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). Horizon tabs follow the
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/).


## Summary metric selection

The [CFA Institute's active management
framework](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/analysis-active-portfolio-management)
uses IC to describe predictive skill.
[Alphalens](https://alphalens.ml4trading.io/api-reference.html#alphalens.performance.compute_mean_returns_spread)
reports mean IC and differences between quantile mean returns. Together these motivate the summary's
ordering and return-magnitude measures. The page leads with dependence-aware IC confidence intervals
and reports sample support alongside them, following the [ASA's emphasis on contextual
interpretation](https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf). The exact compact
selection is a report design choice, not a universal KPI standard.

Temporal stability remains a detailed diagnostic; it could join the overview once its aggregation
across assets and time is clearly defined. A Sharpe ratio, CAGR, or drawdown would require a
specified portfolio and trading simulation, which this predictive-association study does not
provide.
