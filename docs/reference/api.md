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
on a UI library. This one prints each task when it finishes; a [Rich](https://rich.readthedocs.io)
or [tqdm](https://tqdm.github.io) bar has the same shape, creating the bar in place of `done` and
updating it in `advance`:

```python
from contextlib import contextmanager

from alphatonic import evaluate
from alphatonic.demo import synthetic_market


@contextmanager
def print_progress(description, total=None):
    done = 0

    def advance(steps=1, *, description=None):
        nonlocal done
        done += steps

    yield advance
    print(f"{description}: {done} of {total if total is not None else '?'}")


factor, prices = synthetic_market(n_assets=10, n_bars=200, seed=0)
result = evaluate(factor, prices, horizons=[1], progress=print_progress)
```
