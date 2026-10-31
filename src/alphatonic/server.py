"""Serve a study's trials as a sortable list linking to their tearsheets.

The server uses only the standard library and renders the list with Jinja2. It
reads the records on every request, so a trial saved while it runs appears on the next reload. It
serves the list at `/`, the same list as JSON ([`Study.to_dict`][alphatonic.Study.to_dict]) at
`/study.json`, and, for each finished trial, `/<id>/tearsheet.html` and `/<id>/record.json`;
every other path is not found. A request for a trial's file with `?download` in the query makes the
browser save it as `<id>-<name>` instead of showing it. A tearsheet that the study did not store is
drawn from the trial's tables when it is asked for, which takes a few seconds; the server keeps the
last few pages it drew.
It binds to the local machine by default and is meant for one researcher, not for the open
internet.
"""

from __future__ import annotations

import contextlib
import json
from dataclasses import dataclass
from functools import lru_cache, partial
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import parse_qs, unquote, urlsplit

from alphatonic.study import RECORD, TEARSHEET, Study, UnknownTrialError

_FILES = {TEARSHEET: "text/html; charset=utf-8", RECORD: "application/json"}
"""The files of a trial the server sends, by name, with their media types."""


@dataclass(frozen=True)
class Response:
    """What the server sends for one request."""

    status: int
    """HTTP status code."""

    content_type: str
    """Media type of the body."""

    body: bytes
    """The body."""

    filename: str | None = None
    """Name under which the browser should save the body, or `None` to show it."""


def respond(study: Study, target: str) -> Response:
    """Answer a GET request for `target`, a path with an optional query string.

    Args:
        study: The study to serve.
        target: The request target, such as `/?sort=cs_ic&order=desc`.

    Returns:
        The list for `/`, the list as JSON for `/study.json` (400 for an unknown `sort`), a
        finished trial's tearsheet or record (an attachment if the query has `download`), or 404
        for anything else.
    """
    url = urlsplit(target)
    path = unquote(url.path)
    query = {name: values[-1] for name, values in parse_qs(url.query).items()}
    if path == "/study.json":
        horizon = query.get("horizon", "")
        try:
            document = study.to_dict(
                int(horizon) if horizon.isdigit() else None,
                sort=query.get("sort"),
                descending={"asc": False, "desc": True}.get(query.get("order", "")),
            )
        except ValueError as error:
            message = f"{error}\n".encode()
            return Response(HTTPStatus.BAD_REQUEST, "text/plain; charset=utf-8", message)
        body = json.dumps(document, allow_nan=False).encode("utf-8")
        return Response(HTTPStatus.OK, "application/json", body)
    if path == "/":
        from alphatonic.report.board import render_board

        page = render_board(
            study,
            horizon=query.get("horizon"),
            sort=query.get("sort"),
            order=query.get("order"),
            signal=query.get("signal"),
        )
        return Response(HTTPStatus.OK, "text/html; charset=utf-8", page.encode("utf-8"))
    parts = path.strip("/").split("/")
    if len(parts) == 2 and parts[1] in _FILES:
        identifier, name = parts
        try:
            study.trial(identifier)
        except (UnknownTrialError, ValueError):
            return _not_found()
        saved_as = (
            f"{identifier}-{name}"
            if "download" in parse_qs(url.query, keep_blank_values=True)
            else None
        )
        file = study.directory / identifier / name
        if file.is_file():
            return Response(HTTPStatus.OK, _FILES[name], file.read_bytes(), saved_as)
        if name == TEARSHEET:
            try:
                page = _drawn_tearsheet(study, identifier)
            except FileNotFoundError as error:
                return _not_found(f"{error}\n")
            return Response(HTTPStatus.OK, _FILES[name], page, saved_as)
    return _not_found()


def make_server(study: Study, host: str = "127.0.0.1", port: int = 8000) -> ThreadingHTTPServer:
    """Return a server for the study, bound but not yet serving; port 0 picks a free port."""
    return ThreadingHTTPServer((host, port), partial(_Handler, study=study))


def serve(study: Study, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Serve the study's trials until interrupted.

    Args:
        study: The study to serve.
        host: Address to listen on. The default accepts connections from this machine only.
        port: Port to listen on.
    """
    with make_server(study, host, port) as server, contextlib.suppress(KeyboardInterrupt):
        server.serve_forever()


@lru_cache(maxsize=4)
def _drawn_tearsheet(study: Study, identifier: str) -> bytes:
    """Draw a trial's tearsheet from its tables; a trial never changes, so the page is reusable."""
    return study.render_tearsheet(identifier).encode("utf-8")


def _not_found(message: str = "Not found\n") -> Response:
    return Response(HTTPStatus.NOT_FOUND, "text/plain; charset=utf-8", message.encode())


class _Handler(BaseHTTPRequestHandler):
    """Send what `respond` answers, for GET and HEAD requests."""

    def __init__(self, *args: Any, study: Study, **kwargs: Any) -> None:
        # The base class handles the request inside __init__, so the study must be set first.
        self.study = study
        super().__init__(*args, **kwargs)

    def do_GET(self) -> None:
        self._send(body=True)

    def do_HEAD(self) -> None:
        self._send(body=False)

    def _send(self, *, body: bool) -> None:
        try:
            response = respond(self.study, self.path)
        except Exception as error:  # Answer, rather than drop the connection, and log why.
            self.log_error("%s: %s", type(error).__name__, error)
            message = f"{type(error).__name__}: {error}\n".encode()
            response = Response(
                HTTPStatus.INTERNAL_SERVER_ERROR, "text/plain; charset=utf-8", message
            )
        self.send_response(response.status)
        self.send_header("Content-Type", response.content_type)
        self.send_header("Content-Length", str(len(response.body)))
        if response.filename:
            self.send_header("Content-Disposition", f'attachment; filename="{response.filename}"')
        self.end_headers()
        if body:
            self.wfile.write(response.body)


__all__ = ["Response", "make_server", "respond", "serve"]
