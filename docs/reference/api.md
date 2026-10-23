# API

Everything on this page is rendered from the docstrings in the source. The names in the
first section are the public API: import them from `alphatonic`.

## Evaluate

::: alphatonic.evaluate

## Result

::: alphatonic.Evaluation
    options:
      members: [config, start, end, bar, periods, summary, quantiles, time_series, forward_returns, ic, monthly_ic, metrics, save, load, render_tearsheet, tearsheet]

::: alphatonic.TimeSeriesEvaluation
    options:
      members: [assets, monthly, rolling, summary, quantiles, tables]

## Configuration

::: alphatonic.EvaluationConfig

::: alphatonic.TimeSeriesOptions

::: alphatonic.ReportOptions

## Building blocks

::: alphatonic.forward_returns

::: alphatonic.summarize_ic

## Demo data

::: alphatonic.demo.synthetic_market

## Progress reporting

::: alphatonic.progress
    options:
      members: [Advance, ProgressFactory, silent, track]

The progress hook lets a command-line tool or notebook display progress without alphatonic
depending on a UI library. For example, with [Rich](https://rich.readthedocs.io):

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
