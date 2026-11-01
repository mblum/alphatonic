import json

import pytest

from alphatonic import Study, server


@pytest.fixture(autouse=True)
def reset_cache():
    server._KEPT.clear()
    yield
    server._KEPT.clear()


@pytest.mark.parametrize(
    "path",
    [
        "/etc/passwd",
        "/../record.json",
        "/%2e%2e/record.json",
        "/x/a/b",
        "/missing/record.json",
        "/favicon.ico",
    ],
)
def test_router_rejects_unknown_and_traversal(tmp_path, path):
    assert server.respond(Study(tmp_path), path).status == 404


def test_router_json_sort_board_fallback_download_and_lazy_cache(
    panel, config, tmp_path, monkeypatch
):
    s = Study(tmp_path)
    trial = s.evaluate(*panel, config, signal="signal")
    assert json.loads(server.respond(s, "/study.json").body)["trials"][0]["id"] == trial.id
    assert server.respond(s, "/study.json?sort=unknown").status == 400
    assert server.respond(s, "/?sort=unknown").status == 200
    response = server.respond(s, f"/{trial.id}/record.json?download")
    assert response.filename == f"{trial.id}-record.json" and response.status == 200
    lazy = server.respond(s, f"/{trial.id}/tearsheet.html")
    assert b"Drawing" in lazy.body
    calls = []

    def render(identifier):
        calls.append(identifier)
        return "<html>rendered</html>"

    monkeypatch.setattr(s, "render_tearsheet", render)
    first = server.respond(s, f"/{trial.id}/tearsheet.html?render")
    second = server.respond(s, f"/{trial.id}/tearsheet.html?download")
    assert first.body == second.body == b"<html>rendered</html>" and len(calls) == 1
    assert second.filename == f"{trial.id}-tearsheet.html"


def test_lru_eviction_and_study_isolation(tmp_path, monkeypatch):
    a = Study(tmp_path / "a")
    b = Study(tmp_path / "b")
    monkeypatch.setattr(a, "render_tearsheet", lambda identifier: f"a:{identifier}")
    monkeypatch.setattr(b, "render_tearsheet", lambda identifier: f"b:{identifier}")
    for identifier in ["one", "two", "three", "four", "five"]:
        server._drawn_tearsheet(a, identifier)
    assert not server._is_kept(a, "one")
    assert server._drawn_tearsheet(a, "five") == b"a:five"
    assert server._drawn_tearsheet(b, "five") == b"b:five"


def test_finished_record_without_tables_has_no_report(panel, config, tmp_path):
    import shutil

    s = Study(tmp_path)
    trial = s.evaluate(*panel, config, signal="no tables")
    shutil.rmtree(tmp_path / trial.id / "tables")
    assert server.respond(s, f"/{trial.id}/tearsheet.html?render").status == 404
    assert server.respond(s, f"/{trial.id}/arbitrary.csv").status == 404
