"""The `alphatonic` command: list the trials of a study, or serve them as a web page.

    alphatonic list research --sort adjusted_p
    alphatonic serve research --port 8000

`python -m alphatonic` runs the same command.
"""

from __future__ import annotations

import argparse
from collections.abc import Sequence
from pathlib import Path

import pandas as pd

from alphatonic.study import Study

_LISTED = ("signal", "sample", "cs_ic", "cs_z", "adjusted_p", "ts_ic", "trials")
"""Board columns `alphatonic list` prints, after the identifier."""


def main(argv: Sequence[str] | None = None) -> int:
    """Run the command with `argv`, or with the process's arguments, and return its exit status."""
    parser = _parser()
    arguments = parser.parse_args(argv)
    study = Study(arguments.directory, name=getattr(arguments, "name", None))
    if arguments.command == "list":
        try:
            board = study.board(
                arguments.horizon, sort=arguments.sort, descending=arguments.descending
            )
        except ValueError as error:
            parser.error(str(error))
        print(_table(board.head(arguments.limit), study))
        unreadable = study.unreadable()
        if unreadable:
            print(f"{len(unreadable)} records could not be read: {', '.join(map(str, unreadable))}")
        return 0
    from alphatonic.server import serve

    print(f"Serving {study.directory} on http://{arguments.host}:{arguments.port}", flush=True)
    serve(study, arguments.host, arguments.port)
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="alphatonic", description="List or serve the trials of a study."
    )
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser("list", help="Print the trials, sorted by a board column.")
    listing.add_argument("directory", type=Path, help="The study's directory.")
    listing.add_argument("--horizon", type=int, help="Horizon in bars; default: the smallest.")
    listing.add_argument("--sort", help="Board column to sort by, such as adjusted_p.")
    direction = listing.add_mutually_exclusive_group()
    direction.add_argument("--ascending", dest="descending", action="store_false")
    direction.add_argument("--descending", dest="descending", action="store_true")
    listing.set_defaults(descending=None)
    listing.add_argument("--limit", type=int, default=20, help="Rows to print (default 20).")

    serving = commands.add_parser("serve", help="Serve the trials as a sortable web page.")
    serving.add_argument("directory", type=Path, help="The study's directory.")
    serving.add_argument("--host", default="127.0.0.1", help="Address (default 127.0.0.1).")
    serving.add_argument("--port", type=int, default=8000, help="Port (default 8000).")
    serving.add_argument("--name", help="The project's name, shown in the page's title.")
    return parser


def _table(board: pd.DataFrame, study: Study) -> str:
    """The listed columns as text, numbers to four decimals and an en dash where undefined."""
    if board.empty:
        return f"No trials in {study.directory}."
    horizon = int(board["horizon"].iloc[0])
    table = board[list(_LISTED)].to_string(float_format=lambda value: f"{value:.4f}", na_rep="–")
    return f"Horizon: {horizon} bar{'' if horizon == 1 else 's'}\n{table}"


__all__ = ["main"]
