# Report design

The tearsheet and study board put estimates, uncertainty and sample coverage together. This page
explains their choice and arrangement of information.

## Summary metric selection

The tearsheet shows every configured horizon so readers can compare them without a horizon being
selected for its performance.

The overview uses rank IC and the difference between the highest and lowest score buckets. Detailed
panels show Pearson, cosine, variation across assets and changes over time. A missing statistic
stays missing; sample and inference statuses explain why.

The [CFA Institute's active management
framework](https://www.cfainstitute.org/insights/professional-learning/refresher-readings/2026/analysis-active-portfolio-management)
uses IC to describe predictive skill.
[Alphalens](https://alphalens.ml4trading.io/api-reference.html#alphalens.performance.compute_mean_returns_spread)
reports mean IC and differences between quantile mean returns. Together these motivate the summary's
ordering and return-magnitude measures. The exact compact selection is a report design choice,
not a universal KPI standard.

Temporal stability remains a detailed diagnostic; it could join the overview once its aggregation
across assets and time is clearly defined. Portfolio performance measures fall outside the
[scope of the evaluator](../index.md#what-alphatonic-does).

The report omits p-values. A study board shows them: the cross-sectional, time-series and cosine
groups each give a p-value beside its adjustment for the recorded trial count. The underlying
result tables retain the inference statistics.

## Comparing trials

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
for merit. The [study-adjustment explanation](research-validity.md#what-the-study-adjustment-means)
defines which displayed quantities are adjusted.

## Interface design

Essential results stay visible. Optional diagnostics use one level of expandable panels, and horizon
tabs keep long time-series sections manageable. Both pages, the tearsheet and the list of trials,
follow the system's light or dark setting, and the charts take their colours from the same
stylesheet variables, so they change with the page. On paper they are always light. The
[software architecture](design.md#dependencies-and-offline-delivery) explains offline delivery.

The report follows the [GOV.UK accordion
guidance](https://design-system.service.gov.uk/components/accordion/) by keeping essential results
visible and avoiding nested disclosures. Semantic headings and table markup follow W3C guidance on
[headings](https://www.w3.org/WAI/tutorials/page-structure/headings/) and [table
captions](https://www.w3.org/WAI/tutorials/tables/caption-summary/). Narrow-screen layouts contain
horizontal scrolling to data regions, following the [W3C reflow
guidance](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html). Horizon tabs follow the
[WAI-ARIA tabs pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tabs/).

## Presenting uncertainty { #reading-uncertainty-without-changing-its-meaning }

The report pairs estimates with uncertainty and coverage, following the [ASA statement's][asa]
emphasis on context. It does not label a signal as profitable because an interval excludes zero.
This presentation is a design choice; it does not imply that the ASA endorses this report layout.
The [inference page](inference.md#what-an-interval-describes) explains what an interval means.

## References

- American Statistical Association (2016). [Statement on Statistical Significance and
  P-Values: six principles][asa]. Effect size, uncertainty, context and reporting.
- Alphalens Reloaded. [Performance API](https://alphalens.ml4trading.io/api-reference.html).
  Related IC and quantile-return summaries; alphatonic's exact metric selection is its own.

[asa]: https://www.amstat.org/asa/files/pdfs/p-valuestatement.pdf
