# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

### Added

- Compare alphatonic's signal evaluation with Alphalens, Alphalens Reloaded, Qlib and Spectre in
  the README.

### Changed

- The tearsheet follows the system's light or dark setting, as the list of trials already did. Its
  charts are redrawn with a dark palette on a dark system, and again if the setting changes while
  the page is open. Both pages print in light colours whatever the screen uses.
- The rolling IC chart of the time-series analysis picks its asset from a menu above the chart,
  styled like the menus of the list of trials, instead of one inside the chart.
- Condense the README, which is also the documentation home page, into one short "Main concepts"
  section. The home page now links to the documentation instead of listing the guides, and the
  README's links are web URLs that also work on PyPI.

## [0.1.1] - 2026-10-29

### Added

- alphatonic is on [PyPI](https://pypi.org/project/alphatonic/): install it with
  `python -m pip install "alphatonic[report]"`.

## [0.1.0] - 2026-10-29

First public version.
