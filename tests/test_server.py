import http.client
import json
import threading
import time
from collections.abc import Iterator
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

from greekbook.server import Project, make_handler

TOKEN = "secret-token"


@pytest.fixture
def server(novel: Path) -> Iterator[tuple[int, Project]]:
    project = Project(novel, debounce=0.05)
    port_ref = [0]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(project, TOKEN, port_ref))
    port_ref[0] = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    yield port_ref[0], project
    httpd.shutdown()
    httpd.server_close()


def request(port: int, method: str, path: str, body: bytes | None = None,
            headers: dict[str, str] | None = None) -> tuple[int, bytes]:  # fmt: skip
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    conn.request(method, path, body=body, headers=headers or {})
    res = conn.getresponse()
    return res.status, res.read()


def wait_for_build(port: int, after: int = 0) -> dict[str, object]:
    for _ in range(200):
        status = json.loads(request(port, "GET", "/api/status")[1])
        if not status["building"] and status["version"] > after:
            return status  # type: ignore[no-any-return]
        time.sleep(0.05)
    raise AssertionError("build did not finish")


def test_editor_page_has_token(server: tuple[int, Project]) -> None:
    port, _ = server
    code, body = request(port, "GET", "/")
    assert code == 200 and TOKEN.encode() in body


def test_initial_build_and_preview(server: tuple[int, Project]) -> None:
    port, _ = server
    status = wait_for_build(port)
    assert status["ok"] and status["pages"] >= 4 and status["title"] == "Το φως του φάρου"
    code, svg = request(port, "GET", "/page/0.svg")
    assert code == 200 and svg.startswith(b"<svg")
    code, pdf = request(port, "GET", "/book.pdf")
    assert code == 200 and pdf.startswith(b"%PDF")
    files = json.loads(request(port, "GET", "/api/files")[1])
    assert {"path": "chapters/01.md", "group": "chapters"} in files


def test_save_rebuilds(server: tuple[int, Project], novel: Path) -> None:
    port, _ = server
    before = wait_for_build(port)
    text = '# Νέο\n\nΚείμενο "με" αλλαγή.\n'
    code, _ = request(port, "PUT", "/api/file?path=chapters/01.md", text.encode(),
                      {"X-Greekbook-Token": TOKEN})  # fmt: skip
    assert code == 200
    assert (novel / "chapters" / "01.md").read_text(encoding="utf-8") == text
    assert wait_for_build(port, int(before["version"]))["ok"]  # type: ignore[call-overload]


def test_new_chapter(server: tuple[int, Project], novel: Path) -> None:
    port, _ = server
    code, body = request(port, "POST", "/api/chapter", json.dumps({"title": "Επίλογος"}).encode(),
                         {"X-Greekbook-Token": TOKEN})  # fmt: skip
    assert code == 200 and json.loads(body)["path"] == "chapters/03-epilogos.md"
    assert (novel / "chapters" / "03-epilogos.md").is_file()


def test_writes_need_token(server: tuple[int, Project]) -> None:
    port, _ = server
    assert request(port, "PUT", "/api/file?path=chapters/01.md", b"x")[0] == 403
    assert request(port, "POST", "/api/build", b"{}", {"X-Greekbook-Token": "wrong"})[0] == 403


def test_dns_rebinding_is_refused(server: tuple[int, Project]) -> None:
    port, _ = server
    assert request(port, "GET", "/api/files", headers={"Host": "evil.example:80"})[0] == 403


@pytest.mark.parametrize("path", ["../outside.md", "chapters/../../x.md", "book.pdf", "%00.md", ""])
def test_path_traversal_is_refused(server: tuple[int, Project], path: str) -> None:
    port, _ = server
    headers = {"X-Greekbook-Token": TOKEN}
    assert request(port, "GET", f"/api/file?path={path}")[0] == 404
    assert request(port, "PUT", f"/api/file?path={path}", b"x", headers)[0] == 400


def test_broken_config_is_reported(server: tuple[int, Project]) -> None:
    port, project = server
    wait_for_build(port)
    before = project.status()["version"]
    request(port, "PUT", "/api/file?path=book.yaml", b"title: [", {"X-Greekbook-Token": TOKEN})
    status = wait_for_build(port, before)
    assert not status["ok"] and "YAML" in str(status["error"])
