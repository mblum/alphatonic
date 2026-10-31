# Changelog

All notable changes are listed here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project aims to follow
[Semantic Versioning](https://semver.org/) once it reaches 1.0.

## [Unreleased]

### Added

- Report pages link to the project on GitHub, its documentation and its licence in the footer.

- The list of trials that `alphatonic serve` shows is easier to read at a glance. Four tiles lead
  it: the lowest `p × trials`, the highest rank IC with its `p × trials`, the family with the most
  trials, and the looks at the holdout. Each row draws the cross-sectional rank IC as a dot with its
  95% interval on one axis shared by every row. Sorted by a statistic, the rows are numbered from
  its best value, and equal values share a rank.
- `Study.to_dict()` and `/study.json` give each trial the 95% interval of its cross-sectional rank
  IC as `cs_ci_lower` and `cs_ci_upper`, null where the trial has no inference at the horizon.

- The list of trials draws the time-series rank IC and the time-series cosine IC as a dot with its
  95% bootstrap interval, each on an axis of its own, as it does for the cross-sectional rank IC.
  The time-series columns are no longer set in a lighter colour.
- Checkboxes above the list of trials show or hide the column groups, and the `show` query parameter
  does the same in a link (`/?show=ts`, `/?show=cs,testing`). The sorted column stays visible, and
  hiding the multiple-testing columns is noted on the page.
- `Study.to_dict()` and `/study.json` give each trial the 95% bootstrap intervals of its
  time-series rank IC and cosine IC as `ts_ci_lower`, `ts_ci_upper`, `ts_cosine_ci_lower` and
  `ts_cosine_ci_upper`, null where the bootstrap was off.

### Changed

- The selected section in the tearsheet header now matches the height and rounded corners of the download button.
- The tearsheet no longer ends with a "Methods and interpretation" section, and the list of trials
  no longer has an "About these columns" panel. Their links now lead to the matching pages of the
  documentation.
- On the list of trials the horizon is chosen with buttons instead of a menu, and the time-series
  and data columns are set in a lighter colour so that the rank IC and `p × trials` stand out.
- The name in the header bar is larger and leads back to the list of trials on the pages that
  `alphatonic serve` shows.
- The header bar, the page header, the main part and the footer of the tearsheet and the list of
  trials now share one width, one side margin and one set of vertical spacings, so their edges
  line up at every window width and the bar keeps the same height on every page.

## [0.2.0] - 2026-10-31

### Added

- `Study.render_tearsheet(id)` returns the tearsheet of a finished trial as HTML, drawn from its
  saved tables: the same page `Study.evaluate(report=True)` writes, with the study's name, the
  trial's context and its place in its family's count.
- The tearsheet served by `alphatonic serve` has a Download button that saves the page to disk,
  and a tearsheet that was not stored opens at once with a spinner and a message while the server
  draws it, then replaces itself with the tearsheet.

### Changed

- Jinja2 is now a core dependency, so `pip install alphatonic` is enough to write a tearsheet or
  run `alphatonic serve`. The `report` extra still exists and is empty, so
  `pip install "alphatonic[report]"` keeps working. The upper bound `<4` on Jinja2 is gone.
- `Evaluation.save` writes each table as gzip-compressed CSV (`ic_summary.csv.gz`, and so on), as
  format 4 of the saved evaluation. A saved evaluation is about seven times smaller: 22 MB instead
  of 158 MB for 20 assets of hourly bars over five years. Directories of formats 1 to 3, which hold
  plain `.csv` files, still load, and saving over one replaces its plain files. `pandas.read_csv`
  reads the new files as they are, but an older alphatonic cannot load a format 4 directory.
- `Study.evaluate` no longer stores a tearsheet unless you pass `report=True`, which was the
  default. A tearsheet can be as large as the trial's compressed tables. `alphatonic serve` and
  `Study.render_tearsheet` draw it from the tables when it is asked for, which takes a few seconds;
  the server keeps the last few pages. Stored tearsheets are still served as they are, and
  `Study.evaluate` no longer needs `alphatonic[report]` unless you ask for a report. A tearsheet the
  server draws shows the study's name only if you pass `--name`. In
  `Study.to_dict` and `/study.json`, `files.tearsheet` is now set for a trial that has tables, not
  only for one with a stored page.
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
- Improve the documentation. Formulas are typeset as math instead of code blocks. The documentation
  compares alphatonic's signal evaluation with Alphalens, Alphalens Reloaded, Qlib and Spectre. The
  README, which is also the documentation home page, is a shorter introduction with one "Main
  concepts" section and prominent links to the tutorials, task guides, reference and explanations;
  its links are web URLs that also work on PyPI. The example under `evaluate` in the API reference
  is a code block you can paste; before, it ran together as nested quotations.

### Removed

- `alphatonic[report]` no longer installs plotly; it installs jinja2 alone.

## [0.1.1] - 2026-10-29

### Added

- alphatonic is on [PyPI](https://pypi.org/project/alphatonic/): install it with
  `python -m pip install "alphatonic[report]"`.

## [0.1.0] - 2026-10-29

First public version.
