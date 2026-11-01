import http.client
import json
import threading
from contextlib import contextmanager

from alphatonic import Study
from alphatonic.server import make_server


@contextmanager
def running_server(study):
    server = make_server(study, "127.0.0.1", 0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server.server_address
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


def test_http_get_head_lengths_and_live_records(panel, config, tmp_path):
    s = Study(tmp_path)
    with running_server(s) as address:
        client = http.client.HTTPConnection(*address, timeout=10)
        try:
            for method in ["GET", "HEAD"]:
                client.request(method, "/study.json")
                response = client.getresponse()
                body = response.read()
                assert (
                    response.status == 200
                    and response.getheader("Content-Type") == "application/json"
                )
                if method == "HEAD":
                    assert body == b"" and int(response.getheader("Content-Length")) > 0
                else:
                    assert (
                        len(body) == int(response.getheader("Content-Length"))
                        and json.loads(body)["trials"] == []
                    )
            trial = s.evaluate(*panel, config, signal="live")
            client.request("GET", "/study.json")
            response = client.getresponse()
            assert json.loads(response.read())["trials"][0]["id"] == trial.id
        finally:
            client.close()


def test_http_attachment_and_internal_failure(panel, config, tmp_path, monkeypatch):
    s = Study(tmp_path)
    trial = s.evaluate(*panel, config, signal="http")
    with running_server(s) as address:
        client = http.client.HTTPConnection(*address, timeout=10)
        try:
            client.request("GET", f"/{trial.id}/record.json?download")
            response = client.getresponse()
            body = response.read()
            assert response.status == 200 and json.loads(body)["id"] == trial.id
            assert (
                response.getheader("Content-Disposition")
                == f'attachment; filename="{trial.id}-record.json"'
            )

            def fail(*args, **kwargs):
                raise RuntimeError("injected render error")

            monkeypatch.setattr("alphatonic.server.respond", fail)
            client.request("GET", "/")
            response = client.getresponse()
            assert response.status == 500 and b"injected render error" in response.read()
        finally:
            client.close()
