"""An optional progress hook, so long evaluations can report to any display.

Evaluation is silent by default. Pass `progress=` to `evaluate` a callable with the signature
of [`silent`][alphatonic.progress.silent]: it receives a description and an optional total, and
returns a context manager that yields an `advance` function. This is how a command-line tool can
draw a [Rich](https://rich.readthedocs.io) or [tqdm](https://tqdm.github.io) bar without
alphatonic depending on either.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Sequence
from contextlib import AbstractContextManager, contextmanager
from typing import Protocol, TypeVar

T = TypeVar("T")


class Advance(Protocol):
    """Moves a progress task forward."""

    def __call__(self, steps: int = 1, *, description: str | None = None) -> None:
        """Advance by `steps` (zero only updates the description)."""


ProgressFactory = Callable[[str, int | None], AbstractContextManager[Advance]]
"""Starts a task with a description and a total (`None` if unknown); yields `advance`."""


@contextmanager
def silent(description: str, total: int | None = None) -> Iterator[Advance]:
    """Report nothing. This is the default progress display."""

    def advance(steps: int = 1, *, description: str | None = None) -> None:
        return None

    yield advance


def track(items: Sequence[T], description: str, progress: ProgressFactory = silent) -> Iterator[T]:
    """Iterate over `items` while reporting progress."""
    with progress(description, len(items)) as advance:
        for item in items:
            yield item
            advance()
