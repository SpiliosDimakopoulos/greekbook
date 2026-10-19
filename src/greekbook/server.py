"""``greekbook serve``: a local editor with a live preview.

The server only listens on 127.0.0.1 and is meant for one person editing
their own project. It still defends against the two ways a malicious web
page could reach a localhost server:

* DNS rebinding: requests whose ``Host`` header is not this server are refused.
* Cross-site requests: every write needs a random per-session token that is
  only embedded in the editor page; browsers refuse to let other origins read
  that page or send the custom header without a CORS preflight we never allow.

File access is limited to text files inside the project directory.
"""

from __future__ import annotations

import contextlib
import json
import re
import secrets
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .build import BuildError, compile_typst, generate_typst
from .config import ConfigError, load_config

EDITABLE_SUFFIXES = {".md", ".yaml", ".yml", ".bib", ".csl"}
MAX_BODY = 5 * 1024 * 1024
WEB_DIR = Path(__file__).parent / "web"


@dataclass
class BuildState:
    version: int = 0
    title: str = ""
    building: bool = False
    ok: bool = True
    error: str = ""
    seconds: float = 0.0
    pages: list[bytes] = field(default_factory=list)
    pdf: bytes = b""
    diagnostics: list[str] = field(default_factory=list)
    issues: list[dict[str, Any]] = field(default_factory=list)


class Project:
    """The project being edited, plus a debounced background builder."""

    def __init__(self, root: Path, debounce: float = 0.4) -> None:
        self.root = root.resolve()
        self.debounce = debounce
        self.state = BuildState()
        self._lock = threading.Lock()
        self._pending = threading.Event()
        self._last_change = 0.0
        threading.Thread(target=self._worker, daemon=True).start()
        self.request_build()

    # -- files ---------------------------------------------------------------
    def resolve(self, rel: str) -> Path:
        """Map a client path to a file inside the project, or raise."""
        if not rel or "\x00" in rel:
            raise PermissionError("invalid path")
        path = (self.root / rel).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() not in EDITABLE_SUFFIXES:
            raise PermissionError(rel)
        return path

    def files(self) -> list[dict[str, str]]:
        groups: list[dict[str, str]] = []
        try:
            cfg = load_config(self.root)
        except ConfigError:
            return [{"path": "book.yaml", "group": "settings"}]

        def add(paths: list[Path], group: str) -> None:
            for p in paths:
                groups.append({"path": p.relative_to(self.root).as_posix(), "group": group})

        add([self.root / "book.yaml"], "settings")
        for getter, group in (
            (cfg.front_matter_files, "front"),
            (cfg.chapter_files, "chapters"),
            (cfg.appendix_files, "appendices"),
            (cfg.bibliography_files, "bibliography"),
        ):
            with contextlib.suppress(ConfigError):
                add(getter(), group)
        return groups

    def new_chapter(self, title: str) -> str:
        cfg = load_config(self.root)
        directory = self.root / cfg.chapters_dir
        directory.mkdir(exist_ok=True)
        number = len(list(directory.glob("*.md"))) + 1
        from .docx_import import _slug

        path = directory / f"{number:02d}-{_slug(title)}.md"
        path.write_text(f"# {title}\n\n", encoding="utf-8")
        self.request_build()
        return path.relative_to(self.root).as_posix()

    # -- building ------------------------------------------------------------
    def request_build(self) -> None:
        self._last_change = time.monotonic()
        self._pending.set()

    def _worker(self) -> None:
        while True:
            self._pending.wait()
            while time.monotonic() - self._last_change < self.debounce:
                time.sleep(0.05)
            self._pending.clear()
            self.build_now()

    def build_now(self) -> None:
        from .lint import lint_project

        with self._lock:
            self.state.building = True
        started = time.perf_counter()
        try:
            cfg = load_config(self.root)
            source, diagnostics = generate_typst(cfg)
            pages = compile_typst(source, self.root, fmt="svg")
            pdf = compile_typst(source, self.root, pdf_standard=cfg.pdf_standard)
            assert isinstance(pages, list) and isinstance(pdf, bytes)
            cfg.output_path.write_bytes(pdf)
            issues = [
                {"file": i.file, "line": i.line, "level": i.level, "message": i.message}
                for i in lint_project(cfg)
            ]
            with self._lock:
                self.state = BuildState(
                    version=self.state.version + 1,
                    title=cfg.title,
                    seconds=time.perf_counter() - started,
                    pages=pages,
                    pdf=pdf,
                    diagnostics=[str(d) for d in diagnostics],
                    issues=issues,
                )
        except (ConfigError, BuildError, OSError) as exc:
            with self._lock:
                self.state.version += 1
                self.state.ok = False
                self.state.error = str(exc)
        finally:
            with self._lock:
                self.state.building = False

    def status(self) -> dict[str, Any]:
        with self._lock:
            s = self.state
            return {
                "version": s.version,
                "title": s.title,
                "building": s.building,
                "ok": s.ok,
                "error": s.error,
                "seconds": round(s.seconds, 2),
                "pages": len(s.pages),
                "diagnostics": s.diagnostics,
                "issues": s.issues,
            }


def make_handler(project: Project, token: str, port_ref: list[int]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "greekbook"

        def log_message(self, format: str, *args: Any) -> None:
            pass

        # -- helpers ----------------------------------------------------------
        def _send(self, status: int, body: bytes, ctype: str) -> None:
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, status: int = 200) -> None:
            self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

        def _host_ok(self) -> bool:
            host = self.headers.get("Host", "")
            return host in {f"127.0.0.1:{port_ref[0]}", f"localhost:{port_ref[0]}"}

        def _authorized(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Greekbook-Token", ""), token)

        def _body(self) -> bytes:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > MAX_BODY:
                raise ValueError("too large")
            return self.rfile.read(length)

        # -- routes -------------------------------------------------------------
        def do_GET(self) -> None:
            if not self._host_ok():
                return self._send(HTTPStatus.FORBIDDEN, b"bad host", "text/plain")
            url = urlparse(self.path)
            query = parse_qs(url.query)
            if url.path == "/":
                html = (WEB_DIR / "editor.html").read_text(encoding="utf-8")
                html = html.replace("__TOKEN__", token)
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if url.path == "/api/files":
                return self._json(project.files())
            if url.path == "/api/status":
                return self._json(project.status())
            if url.path == "/api/file":
                try:
                    path = project.resolve(query.get("path", [""])[0])
                    return self._send(200, path.read_bytes(), "text/plain; charset=utf-8")
                except (PermissionError, FileNotFoundError):
                    return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")
            m = re.fullmatch(r"/page/(\d+)\.svg", url.path)
            if m:
                pages = project.state.pages
                index = int(m.group(1))
                if index < len(pages):
                    return self._send(200, pages[index], "image/svg+xml")
                return self._send(HTTPStatus.NOT_FOUND, b"", "text/plain")
            if url.path == "/book.pdf":
                return self._send(200, project.state.pdf, "application/pdf")
            return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        def do_PUT(self) -> None:
            if not (self._host_ok() and self._authorized()):
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            url = urlparse(self.path)
            if url.path != "/api/file":
                return self._send(HTTPStatus.NOT_FOUND, b"", "text/plain")
            try:
                path = project.resolve(parse_qs(url.query).get("path", [""])[0])
                text = self._body().decode("utf-8")
            except (PermissionError, ValueError, UnicodeDecodeError) as exc:
                return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8", newline="")
            project.request_build()
            return self._json({"saved": True})

        def do_POST(self) -> None:
            if not (self._host_ok() and self._authorized()):
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            url = urlparse(self.path)
            try:
                data = json.loads(self._body() or b"{}")
            except (ValueError, UnicodeDecodeError):
                return self._json({"error": "bad json"}, HTTPStatus.BAD_REQUEST)
            if url.path == "/api/chapter":
                title = str(data.get("title", "")).strip() or "Νέο κεφάλαιο"
                try:
                    return self._json({"path": project.new_chapter(title)})
                except ConfigError as exc:
                    return self._json({"error": str(exc)}, HTTPStatus.BAD_REQUEST)
            if url.path == "/api/build":
                project.request_build()
                return self._json({"queued": True})
            return self._send(HTTPStatus.NOT_FOUND, b"", "text/plain")

    return Handler


def serve(root: Path, port: int = 8420, open_browser: bool = True) -> None:
    project = Project(root)
    token = secrets.token_urlsafe(24)
    port_ref = [port]
    server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(project, token, port_ref))
    port_ref[0] = server.server_address[1]
    url = f"http://127.0.0.1:{port_ref[0]}/"
    print(f"greekbook editor: {url}  (Ctrl+C για έξοδο)")
    if open_browser:
        threading.Timer(0.5, webbrowser.open, args=(url,)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print()
    finally:
        server.server_close()
