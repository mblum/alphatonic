# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

## [0.1.0]

First public version.

### Added

- `evaluate(factor, prices, ...)` with cross-sectional IC (Spearman and Pearson) per timestamp
  and horizon, a Newey–West standard error of the mean, ICIR, and score-bucket mean returns.
- Time-series IC per asset: full-period, per UTC calendar month and rolling, with circular
  block-bootstrap intervals and a monthly ICIR.
- Exact-horizon forward-return labels that require an unbroken path of prices, with an optional
  delay between observation and label.
- Input handling for wide DataFrames and alphalens-style `(timestamp, asset)` Series; horizons
  count rows of the price table, so trading calendars and 24/7 grids both work.
- A status for every statistic that cannot be computed; undefined values are `NaN`, never zero.
- `Evaluation.save` / `load`, `Evaluation.metrics()` and `Evaluation.ic()`.
- An offline interactive HTML tearsheet (`pip install "alphatonic[report]"`).
- `alphatonic.demo.synthetic_market` and an optional progress hook.

### Notes

- Correlations smaller than 1e-12 in magnitude are reported as exactly zero, so floating-point
  noise cannot decide whether a period counts as a positive IC.
