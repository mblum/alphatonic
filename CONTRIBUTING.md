# Contributing

Thanks for helping. Bug reports with a minimal, runnable example are the most useful
contribution; `alphatonic.demo.synthetic_market` makes it easy to share one without data.

- **Questions about correct usage or interpretation:** open an issue with the label you expect
  (question). The [documentation](docs/index.md) covers inputs, statuses and methodology.
- **Statistical changes** (what a number means) need a reference to a source or a simulation in
  `tests/test_inference.py` that shows the calibration, and an update to
  `docs/explanation/methodology.md`.
- **Code changes** follow [docs/contributing/development.md](docs/contributing/development.md):
  `uv sync --all-extras --locked`, then `uv run pytest`, `uv run ruff check .` and
  `uv run ruff format --check .` must pass.
- Add a line to `CHANGELOG.md` for anything a user would notice.

By contributing you agree that your contribution is licensed under the Apache License 2.0.
