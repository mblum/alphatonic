# Keep every trial in a study

Use a `Study` to keep related experiments in one directory. It saves each completed trial, counts
variants of the same idea and reports cross-sectional p-values adjusted for that count. You can also
reserve a holdout period and track how often you evaluate it.

Evaluating needs no extra. Browsing the trials and drawing their tearsheets needs the `report`
extra. A study stores tables and records; it draws a tearsheet from the tables when you ask for one,
and stores it only if you pass `report=True` to `study.evaluate`.

## Run evaluations through a study

Create the study with the first timestamp of the holdout, then call `study.evaluate` where you would
call `evaluate`. It takes the same options, plus a name for the signal and what you want recorded
with it:

```python
from alphatonic import Study
from alphatonic.demo import synthetic_market

factor, prices = synthetic_market(n_assets=30, n_bars=600, ic=0.03, seed=4)
study = Study("smoothing-study", holdout_start=prices.index[450])

for window in (1, 5, 20):
    study.evaluate(
        factor.rolling(window).mean(),
        prices,
        signal="smoothed",
        parameters={"window": window},
        context={"Returns": "close to close"},
        note="how much smoothing helps",
        horizons=[5],
        time_series={"bootstrap_samples": 0},
    )
```

Each successful call saves a trial: its tables and a `record.json` written last. Failed or
interrupted calls without a record are not counted. An in-sample evaluation ends at
`holdout_start`, so no label reads a price from the holdout. When the prices end earlier, the window
ends with them and the record says so.

`context` holds facts the study cannot know, such as how returns were adjusted or which checks the
signal passed. They appear in the tearsheet and as columns of the board. `versions` records your own
code's version next to alphatonic's.

## Compare the trials

`board` returns one row per trial with its headline statistics at one horizon:

```python
board = study.board()
print(board[["parameters", "cs_ic", "cs_z", "cs_p", "adjusted_p", "trials"]].round(4))
```

`trials` counts the trials of the same family, across all parameters and both samples, and
`adjusted_p` is `cs_p` times that count, at most 1: Bonferroni's correction. Use the adjusted value
when comparing trials within a family. This correction covers the recorded trial count, not every
horizon, metric or unrecorded choice you may have inspected. A trial's family is its signal's name
unless you name one; give variants of one idea a common family so that they are counted together:

```python
study.evaluate(
    factor.ewm(span=10).mean(),
    prices,
    signal="smoothed_ewm",
    family="smoothed",
    parameters={"span": 10},
    horizons=[5],
    time_series={"bootstrap_samples": 0},
)
print(study.board()["trials"].tolist())
```

The count is a lower bound on what you tried: variants you ran outside the study, or dropped before
evaluating them, are not in it. Never delete a trial's directory to tidy up; removing the failures
makes the survivors look better than they are.

## Compute the signal from data before the window

`window` returns the window an evaluation will use before you run it. Compute the signal from data
before its end to keep holdout prices out of in-sample factor construction:

```python
start, end = study.window()  # UTC; the demo's prices have a naive index, which means UTC
history = prices[prices.index < end.replace(tzinfo=None)]
in_sample_factor = history / history.shift(20) - 1
assert in_sample_factor.index.max() < prices.index[450]
```

This restricts access to the holdout, but does not prevent look-ahead within the training sample.
Each score must still use only data available at its timestamp. See the [truncation
check](prepare-inputs.md#check-a-factor-for-look-ahead).

## Evaluate the holdout once

Fix the model and parameter choices before inspecting the holdout. Then evaluate with
`holdout=True`. Holdout scores may use earlier holdout observations once those observations would
have been available:

```python
choice = study.evaluate(
    factor.rolling(5).mean(),
    prices,
    signal="smoothed",
    parameters={"window": 5},
    holdout=True,
    horizons=[5],
    time_series={"bootstrap_samples": 0},
)
print(choice.sample, choice.start)
```

The board's `holdout_uses` counts these per family. A second look at the holdout means it no longer
tests a choice made without it. An in-sample window that reaches into the holdout is refused before
anything is evaluated:

```python
from alphatonic import HoldoutError

try:
    study.evaluate(factor, prices, signal="raw", end=prices.index[500], horizons=[5])
except HoldoutError as error:
    print(error)
```

## Browse the trials

`alphatonic serve` shows the board as a web page. Each row names the signal and its parameters, then
groups the cross-sectional statistics, the multiple-testing columns (the family's trial count, `p ×
trials` and the sample, with repeated looks at the holdout flagged), the time-series statistics and
the data. Sort it by any column, switch the horizon, filter by signal, and open each trial's
tearsheet from its name. It reads the records on every request, so a trial saved while it runs
appears on the next reload. A tearsheet that was not stored is drawn from the trial's tables when
you open it, which takes a few seconds; the server keeps the last few pages it drew. Pass `--name`
to show the study's name in those tearsheets, because the server knows only what you give it:

```bash
alphatonic serve smoothing-study    # http://127.0.0.1:8000
```

`alphatonic list` prints the board in a terminal, and `study.board(sort="adjusted_p")` sorts it the
same way in Python:

```bash
alphatonic list smoothing-study --sort adjusted_p
```

The same list is served as JSON at `/study.json`, with the page's `horizon`, `sort` and `order`
parameters, and `study.to_dict()` returns it in Python; the [results
reference](../reference/results.md#json-documents) describes it. The page needs
`alphatonic[report]`. The server listens on this machine only unless you pass `--host`, and it
serves nothing but the list and the trials' tearsheets and records.

## Read the trials back

```python
latest = study.trials()[0]
tables = study.evaluation(latest.id)
page = study.render_tearsheet(latest.id)
print(latest.signal, latest.sample, round(tables.metrics()["cs.h5.spearman.mean"], 4))
```

`study.render_tearsheet(latest.id)` returns the trial's tearsheet as HTML, drawn from its tables
with the study's name, the trial's context and its place in its family's count. It needs
`alphatonic[report]`.

`study.trials()` returns completed trials newest first. It skips directories without a
`record.json`: evaluations that did not finish. Records that exist but cannot be read are listed by
`unreadable`. The files and fields are described in [results and
metrics](../reference/results.md#files-written-by-a-study).
