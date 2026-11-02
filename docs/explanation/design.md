# Software architecture

Alphatonic separates numerical evaluation, saved results and presentation. This page explains
how its data model and execution choices support reproducible, inspectable results. The
[scope page](scope.md) defines the product boundary; [evaluation methodology](methodology.md)
defines the statistical samples.

## Tables as the boundary between computation and presentation

The result is a handful of tidy DataFrames. The tearsheet renders them without rerunning inference,
and saved tables can be rendered again with different display options. A front end of another
kind can read the same results from `to_dict()`.

An unavailable statistic is `NaN` with a reason. A correlation of a constant is undefined,
not zero, and an interval without enough data is absent. Sample and inference statuses explain
unavailable correlations and intervals. Summary ratios can also be `NaN`, for example when their
denominator is zero. Keeping values and statuses together lets both programmatic consumers and
the report distinguish missing results from genuine zeros.

## Durable trial records

A study never overwrites or deletes a trial, and counts all of them. Facts the library cannot
check, such as how a signal was computed, are recorded as the caller states them. This makes the
history inspectable. The [research-validity explanation](research-validity.md) covers what that
history can establish about selection and holdout use.

## Dependencies and offline delivery

Alphatonic needs NumPy, pandas and pydantic (for validated, immutable configuration), and Jinja2
for report pages. The list of a study's trials is served by the standard library's HTTP server,
so browsing it adds no runtime dependency. There is no progress-bar dependency; a hook lets you
plug in your own.

Both pages use Pico CSS, a classless stylesheet, and the tearsheet's charts use Observable Plot
and d3. These resources are vendored in the package and written into each page, so there is no
front-end build and a tearsheet opens offline. The [report-design page](report-design.md)
explains the presentation choices built on this delivery model.

## Performance and reproducibility

Cross-sectional work is vectorised over timestamps in blocks of 256 rows, which bounds temporary
arrays. Time-series work evaluates each window with array operations over all assets at once.
The block bootstrap is the expensive part: each draw recomputes every asset's rank correlation,
so its cost is draws × assets × bars. It is deterministic and single-threaded. The
[inference page](inference.md#block-length-and-available-draws) specifies its random seeding and
resampling rules.

A reference implementation of the original timestamp-by-timestamp formulation lives in the test
suite. The optimised code is checked against it on randomised data, including gaps, ties, delays
and constant scores.
