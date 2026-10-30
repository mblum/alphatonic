# API

This page lists functions, result objects and configuration options. Entries are generated from
source docstrings. Import names such as `evaluate` and `Study` from `alphatonic`; server, demo and
progress utilities live in the submodules shown below.

## Evaluate

::: alphatonic.evaluate

## Result

::: alphatonic.Evaluation
    options:
      members: [config, start, end, bar, periods, summary, quantiles, time_series, persistence, forward_returns, volatility, ic, monthly_ic, metrics, to_dict, save, load, render_tearsheet, tearsheet]

::: alphatonic.TimeSeriesEvaluation
    options:
      members: [assets, monthly, rolling, summary, quantiles, tables]

::: alphatonic.PersistenceEvaluation

## Study

::: alphatonic.Study
    options:
      members: [window, evaluate, trials, unreadable, trial, evaluation, render_tearsheet, board, to_dict]

::: alphatonic.Trial

::: alphatonic.HoldoutError

::: alphatonic.UnknownTrialError

### Serve a study

::: alphatonic.server.serve

::: alphatonic.server.make_server

For command syntax and defaults, see the [command-line reference](cli.md).

## Configuration

::: alphatonic.EvaluationConfig

::: alphatonic.TimeSeriesOptions

::: alphatonic.PersistenceOptions

::: alphatonic.ReportOptions

## Building blocks

::: alphatonic.forward_returns

::: alphatonic.bar_volatility

::: alphatonic.summarize_ic

## Demo data

::: alphatonic.demo.synthetic_market

## Progress reporting

::: alphatonic.progress
    options:
      members: [Advance, ProgressFactory, silent, track]

The progress hook lets a command-line tool or notebook display progress without alphatonic depending
on a UI library. For example, with [Rich](https://rich.readthedocs.io):

<!-- notest -->
```python
from contextlib import contextmanager

from rich.progress import Progress


@contextmanager
def rich_progress(description, total=None):
    with Progress() as progress:
        task = progress.add_task(description, total=total)

        def advance(steps=1, *, description=None):
            progress.update(
                task, advance=steps, **({"description": description} if description else {})
            )

        yield advance


result = evaluate(factor, prices, progress=rich_progress)
```
