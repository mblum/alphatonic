# Design decisions

Alphatonic keeps predictive association, sampling uncertainty and research selection visible as
separate questions. Its data and storage rules support that separation; they do not remove the
need for a specified research design.

## Principles

**An unavailable statistic is `NaN` with a reason.** A correlation of a constant is undefined,
not zero, and an interval without enough data is absent. Sample and inference statuses explain
unavailable correlations and intervals. Summary ratios can also be `NaN`, for example when their
denominator is zero.

**Bars, not clock time.** The rows of the price table define the calendar. This keeps the core free
of market-specific assumptions: a business-day table, a 24/7 hourly grid, and irregular rebalance
dates all follow the same rule, and only the calendar-month and rolling-window views use timestamps.
The cost is that a missing *row* looks like a shorter gap than a missing *price*; the [input
guide](../how-to/prepare-inputs.md#calendars) shows how to put missing 24/7 bars on the grid.

**Exact labels over maximal data.** A label needs an unbroken path of prices. This discards more
data than skipping or filling gaps would, and it guarantees that "the 24-bar return" always spans 24
bars.

**Uncertainty that accounts for dependence.** Cross-sectional IC uses a HAC standard
error, and time-series IC a block bootstrap and a t-test with an equal-weighted cosine standard
error, because both outputs depend on time ordering. These intervals can be wider, and these
p-values larger, than a naive t-test gives when observations are positively dependent.
[Newey and West (1987)][nw] and [Lazarus et al. (2018)][har] provide the variance-estimation
basis. The [inference explanation](inference.md) distinguishes their results from alphatonic's
choices about correlations, gaps and horizons.

**Separate timing from average exposure.** Cross-sectional correlations centre each timestamp,
so adding the same return to every asset does not change them. Time-series positions carry net
exposure, so the time-series view also reports an uncentred cosine, split into the part earned by
timing and the part earned by the average position, against volatility-scaled targets by default.
[Targets, scaling and the cosine IC](targets-and-scaling.md) gives the evidence.

**Tables first.** The result is a handful of tidy DataFrames. The tearsheet is a rendering of them;
it does not rerun inference. Saved tables can be rendered again with different display options.

**Every trial is kept.** A study never overwrites or deletes a trial, and counts all of them.
Selection among many results changes the interpretation of a small p-value, as
[Harvey, Liu and Zhu (2016)][hlz] explain for factor research. Keeping trials makes the search
inspectable; counting them alone does not validate an adaptive search. Facts the library cannot
check, such as how a signal was computed, are recorded as the caller states them. See
[trials, selection and the holdout](research-validity.md).

**Small dependency footprint.** Alphatonic needs NumPy, pandas and pydantic (for validated, immutable
configuration), and Jinja2 for the report pages. The list of a study's trials
is served by the standard library's HTTP server, so browsing it adds nothing beyond that. Both
pages are styled by Pico CSS, a classless stylesheet, and the tearsheet's charts are drawn by
Observable Plot and d3. All are vendored in the package and written into each page, so there is no
front-end build and a tearsheet still opens offline. A front end of another
kind can read the same results from `to_dict()`. There is no progress-bar dependency; a hook lets
you plug in your own.

## What alphatonic does not do

- **Portfolio construction and P&L.** No weights, traded turnover, cumulative returns, alpha/beta or
  costs. Use a backtester for those and alphatonic to decide whether a signal is worth backtesting.
- **Factor construction.** It evaluates scores; it does not compute them.
- **Group (sector) analysis and neutralisation.** Neutralise the factor before evaluating.
- **Look-ahead detection.** It cannot see how your factor was built. The input guide includes a
  truncation test you can run.
- **Multiple-testing control beyond the study.** A study counts the evaluations it runs and
  reports p-values times that count, but alternatives tried outside it, or abandoned before
  evaluation, are invisible to it.

These are boundaries, not a roadmap commitment: some, such as cost analysis and group analysis, are
natural extensions if there is demand.

[Signal persistence](signal-persistence.md) is available independently of return labels. It measures
score and bucket changes, not traded notional. Cost analysis is not an available feature.

## Performance model

Cross-sectional work is vectorised over timestamps in blocks of 256 rows, which bounds temporary
arrays. Time-series work evaluates each
window with array operations over all assets at once. The block bootstrap is the expensive part:
each draw recomputes every asset's rank correlation, so its cost is draws × assets × bars. It is
deterministic and single-threaded. A reference implementation of the original,
timestamp-by-timestamp formulation lives in the test suite and the optimised code is checked against
it on randomised data, including gaps, ties, delays and constant scores.

## References

- Newey, W. K. and West, K. D. (1987). [A Simple, Positive Semi-Definite, Heteroskedasticity and
  Autocorrelation Consistent Covariance Matrix][nw]. *Econometrica*, 55(3), 703–708.
- Lazarus, E., Lewis, D. J., Stock, J. H. and Watson, M. W. (2018).
  [HAR Inference: Recommendations for Practice][har]. *Journal of Business & Economic Statistics*,
  36(4), 541–559. Dependence-aware tests and the consequences of smoothing choices.
- Harvey, C. R., Liu, Y. and Zhu, H. (2016). [… and the Cross-Section of Expected Returns][hlz].
  *The Review of Financial Studies*, 29(1), 5–68. Multiple testing in factor research.

[nw]: https://doi.org/10.2307/1913610
[har]: https://www.princeton.edu/~mwatson/papers/LLSW_har_JBES_Final_071418.pdf
[hlz]: https://people.duke.edu/~charvey/Research/Published_Papers/P118_and_the_cross.PDF
