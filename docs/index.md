# alphatonic documentation

alphatonic measures how well trading signals predict future returns, using scores and prices as
pandas tables. It produces information coefficients, uncertainty estimates and offline HTML reports.

## Run your first evaluation

Evaluate a signal on synthetic data, inspect its information coefficients and confidence intervals,
and create an offline HTML tearsheet. You need Python 3.11 or newer; no market data is required.
The tutorial includes installation.

[Start your first evaluation](tutorials/first-evaluation.md){ .md-button .md-button--primary }

## Find what you need

### Learn with an example — Tutorials

[Your first evaluation](tutorials/first-evaluation.md) guides you through generating data,
evaluating a signal and interpreting the results.

### Complete a task — How-to guides

- [Prepare factor and prices](how-to/prepare-inputs.md).
- [Configure an evaluation](how-to/configure-evaluation.md).
- [Read a tearsheet](how-to/read-a-tearsheet.md).
- [Keep every trial in a study](how-to/run-a-study.md).

### Look up details — Reference

- [Python API](reference/api.md): functions, result objects and options.
- [Command line](reference/cli.md): commands and arguments.
- [Results and metrics](reference/results.md): tables, columns and units.

### Understand the methods — Explanation

- [Evaluation methodology](explanation/methodology.md): returns, information coefficients and uncertainty.
- [Signal persistence](explanation/signal-persistence.md): changes in scores, ranks and membership.
- [Targets, scaling and the cosine IC](explanation/targets-and-scaling.md).
- [Scope and alternatives](explanation/scope.md): where alphatonic fits in a research workflow.

## Need help?

Check [troubleshooting](how-to/troubleshooting.md), or
[report an issue](https://github.com/mblum/alphatonic/issues).

[Changelog](changelog.md) · [Contributing](contributing/development.md)
