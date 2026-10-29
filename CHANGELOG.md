# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

### Added

- Compare alphatonic's signal evaluation with Alphalens, Alphalens Reloaded, Qlib and Spectre in
  the README.

### Changed

- The tearsheet follows the system's light or dark setting, as the list of trials already did;
  before, it was always light. Both pages print in light colours whatever the screen uses.
- The tearsheet's charts are drawn by Observable Plot and d3, which the package carries, instead of
  Plotly. A tearsheet is about a quarter of the size (1.5 MB instead of 6.3 MB for the demo
  evaluation). Charts show exact values in tooltips; they have no zoom, pan or image-export toolbar.
  Their colours come from the page's stylesheet, so they follow its light and dark theme, and a
  fourth sample status no longer repeats the colour of the first. The tearsheet needs a browser from
  2023 or later (Chrome 111, Firefox 113, Safari 16.2).
- The rolling IC chart of the time-series analysis picks its asset from a menu above the chart,
  styled like the menus of the list of trials, instead of one inside the chart.
- A printed tearsheet uses the type size its print stylesheet asks for. Before, the page was printed
  at about two thirds of it, so it now takes more pages.
- Condense the README, which is also the documentation home page, into one short "Main concepts"
  section. The home page now links to the documentation instead of listing the guides, and the
  README's links are web URLs that also work on PyPI.

### Removed

- `alphatonic[report]` no longer installs plotly; it installs jinja2 alone.

## [0.1.1] - 2026-10-29

### Added

- alphatonic is on [PyPI](https://pypi.org/project/alphatonic/): install it with
  `python -m pip install "alphatonic[report]"`.

## [0.1.0] - 2026-10-29

First public version.
