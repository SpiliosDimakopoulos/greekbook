"""``greekbook app`` / ``greekbook serve``: the greekbook application in the browser.

One local server shows a home screen (create, open or import a project) and an
editor with live page preview, a settings form, image upload and chapter
management, so that nobody has to touch a terminal or a YAML file.

The server only listens on 127.0.0.1 and still defends against the two ways a
malicious web page could reach a localhost server:

* DNS rebinding: requests whose ``Host`` header is not this server are refused.
* Cross-site requests: every write needs a random per-session token that is only
  embedded in our own pages; other origins can neither read those pages nor send
  the custom header without a CORS preflight that we never allow.

File access is limited to the open project's folder.
"""

from __future__ import annotations

import contextlib
import json
import re
import secrets
import shutil
import tempfile
import threading
import time
import webbrowser
from dataclasses import dataclass, field
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, unquote, urlparse

import yaml

from .build import BuildError, compile_typst, generate_typst
from .config import TEMPLATES, ConfigError, config_from_dict, load_config
from .projects import (
    KINDS,
    create_project,
    default_workspace,
    list_projects,
    project_info,
    remember,
    slugify,
    unique_folder,
)

EDITABLE_SUFFIXES = {".md", ".yaml", ".yml", ".bib", ".csl"}
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp"}
MAX_TEXT = 5 * 1024 * 1024
MAX_UPLOAD = 60 * 1024 * 1024
WEB_DIR = Path(__file__).parent / "web"
TRASH = ".kados"  # deleted files go here, never straight to oblivion
_LIST_KEYS = ("chapters", "front_matter", "appendices")


class UserError(Exception):
    """A problem to show to the user as is (already in plain Greek)."""


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
        self.closed = False
        self._lock = threading.Lock()
        self._pending = threading.Event()
        self._last_change = 0.0
        threading.Thread(target=self._worker, daemon=True).start()
        self.request_build()

    def close(self) -> None:
        self.closed = True
        self._pending.set()

    # -- paths ---------------------------------------------------------------
    def resolve(self, rel: str, suffixes: set[str] = EDITABLE_SUFFIXES) -> Path:
        """Map a client path to a file inside the project, or raise."""
        if not rel or "\x00" in rel:
            raise PermissionError("invalid path")
        path = (self.root / rel).resolve()
        if not path.is_relative_to(self.root) or path.suffix.lower() not in suffixes:
            raise PermissionError(rel)
        if TRASH in path.relative_to(self.root).parts:
            raise PermissionError(rel)
        return path

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root).as_posix()

    # -- configuration ---------------------------------------------------------
    def raw_config(self) -> dict[str, Any]:
        data = yaml.safe_load((self.root / "book.yaml").read_text(encoding="utf-8")) or {}
        if not isinstance(data, dict):
            raise UserError("Το book.yaml δεν έχει τη σωστή μορφή.")
        return data

    def save_config(self, raw: dict[str, Any]) -> None:
        clean = {k: v for k, v in raw.items() if v not in (None, "", [], {})}
        if isinstance(clean.get("thesis"), dict):
            clean["thesis"] = {k: v for k, v in clean["thesis"].items() if v not in (None, "", [])}
        try:
            config_from_dict(clean, self.root)
        except ConfigError as exc:
            raise UserError(str(exc)) from exc
        text = yaml.safe_dump(clean, allow_unicode=True, sort_keys=False)
        (self.root / "book.yaml").write_text(text, encoding="utf-8")
        self.request_build()

    def _update_lists(self, old: str, new: str | None) -> None:
        raw = self.raw_config()
        changed = False
        for key in _LIST_KEYS:
            value = raw.get(key)
            items = [value] if isinstance(value, str) else value
            if isinstance(items, list) and old in items:
                raw[key] = [new if i == old else i for i in items if not (i == old and new is None)]
                changed = True
        if changed:
            text = yaml.safe_dump(raw, allow_unicode=True, sort_keys=False)
            (self.root / "book.yaml").write_text(text, encoding="utf-8")

    # -- files -----------------------------------------------------------------
    def files(self) -> list[dict[str, str]]:
        groups: list[dict[str, str]] = []
        try:
            cfg = load_config(self.root)
        except ConfigError:
            return [{"path": "book.yaml", "group": "settings", "title": "book.yaml"}]

        def add(paths: list[Path], group: str) -> None:
            for p in paths:
                groups.append({"path": self.rel(p), "group": group, "title": _title_of(p)})

        for getter, group in (
            (cfg.front_matter_files, "front"),
            (cfg.chapter_files, "chapters"),
            (cfg.appendix_files, "appendices"),
            (cfg.bibliography_files, "bibliography"),
        ):
            with contextlib.suppress(ConfigError):
                add(getter(), group)
        return groups

    def _chapter_dir(self) -> Path:
        cfg = load_config(self.root)
        for name in (cfg.chapters_dir, "parts"):
            if (self.root / name).is_dir():
                return self.root / name
        return self.root / cfg.chapters_dir

    def new_chapter(self, title: str, group: str = "chapters") -> str:
        title = title.strip() or "Νέο κεφάλαιο"
        group = group or "chapters"
        raw = self.raw_config()
        if group == "chapters" and not raw.get("chapters"):
            directory = self._chapter_dir()
            directory.mkdir(exist_ok=True)
            numbers = [int(m.group(1)) for p in directory.glob("*.md")
                       if (m := re.match(r"(\d+)", p.name))]  # fmt: skip
            number = max(numbers, default=0) + 1
            path = directory / f"{number:02d}-{slugify(title, 'kefalaio')}.md"
        else:
            folder = {"front": "front", "appendices": "appendices"}.get(group, "chapters")
            path = self.root / folder / f"{slugify(title, 'keimeno')}.md"
            n = 2
            while path.exists():
                path = path.with_name(f"{slugify(title, 'keimeno')}-{n}.md")
                n += 1
            key = {"front": "front_matter", "appendices": "appendices"}.get(group, "chapters")
            items = raw.get(key) or []
            raw[key] = [*([items] if isinstance(items, str) else items), self.rel_new(path)]
            (self.root / "book.yaml").write_text(
                yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
            )
        path.parent.mkdir(parents=True, exist_ok=True)
        heading = f"# {title}" + (" {-}" if group == "front" else "")
        path.write_text(f"{heading}\n\n", encoding="utf-8")
        self.request_build()
        return self.rel(path)

    def rel_new(self, path: Path) -> str:
        return path.relative_to(self.root).as_posix()

    def rename_chapter(self, rel: str, title: str) -> str:
        path = self.resolve(rel, {".md"})
        title = title.strip()
        if not title:
            raise UserError("Ο τίτλος δεν μπορεί να είναι κενός.")
        text = path.read_text(encoding="utf-8")
        new_text, count = re.subn(r"^#\s+(.+?)(\s*\{[^}]*\})?\s*$",
                                  lambda m: f"# {title}{m.group(2) or ''}",
                                  text, count=1, flags=re.MULTILINE)  # fmt: skip
        if not count:
            new_text = f"# {title}\n\n{text}"
        path.write_text(new_text, encoding="utf-8")
        prefix = m.group(1) + "-" if (m := re.match(r"(\d+)[-_ ]", path.name)) else ""
        target = path.with_name(f"{prefix}{slugify(title, 'kefalaio')}.md")
        if target != path and not target.exists():
            path.rename(target)
            self._update_lists(rel, self.rel(target))
            path = target
        self.request_build()
        return self.rel(path)

    def delete(self, rel: str) -> None:
        path = self.resolve(rel, {".md", ".bib"})
        trash = self.root / TRASH
        trash.mkdir(exist_ok=True)
        shutil.move(str(path), trash / f"{time.strftime('%Y%m%d-%H%M%S')}-{path.name}")
        self._update_lists(rel, None)
        self.request_build()

    def move(self, rel: str, direction: int) -> None:
        raw = self.raw_config()
        path = self.resolve(rel, {".md"})
        for key in _LIST_KEYS:
            items = raw.get(key)
            if isinstance(items, list) and rel in items:
                i = items.index(rel)
                j = i + direction
                if 0 <= j < len(items):
                    items[i], items[j] = items[j], items[i]
                    raw[key] = items
                    (self.root / "book.yaml").write_text(
                        yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8"
                    )
                    self.request_build()
                return
        chapters = load_config(self.root).chapter_files()
        i = chapters.index(path)
        j = i + direction
        if not 0 <= j < len(chapters):
            return
        chapters[i], chapters[j] = chapters[j], chapters[i]
        # renumber every chapter so the filename order matches the new order
        staged = []
        for n, p in enumerate(chapters, 1):
            rest = re.sub(r"^\d+[-_ ]*", "", p.name)  # "02-telos.md" → "telos.md", "02.md" → ".md"
            name = f"{n:02d}{rest}" if rest.startswith(".") else f"{n:02d}-{rest}"
            tmp = p.with_name(f".tmp-{name}")
            p.rename(tmp)
            staged.append((tmp, p.with_name(name)))
        for tmp, final in staged:
            tmp.rename(final)
        self.request_build()

    def save_image(self, filename: str, data: bytes, for_file: str) -> str:
        suffix = Path(filename).suffix.lower()
        if suffix not in IMAGE_SUFFIXES:
            raise UserError("Δεκτές εικόνες: PNG, JPG, GIF, SVG, WebP.")
        figures = self.root / "figures"
        figures.mkdir(exist_ok=True)
        stem = slugify(Path(filename).stem, "eikona")
        target = figures / f"{stem}{suffix}"
        n = 2
        while target.exists():
            target = figures / f"{stem}-{n}{suffix}"
            n += 1
        target.write_bytes(data)
        try:
            base = self.resolve(for_file).parent
        except PermissionError:
            base = self.root
        rel = Path(_relpath(target, base)).as_posix()
        label = slugify(Path(filename).stem, "eikona")
        return f"![Λεζάντα της εικόνας]({rel}){{#fig:{label} width=80%}}"

    def bib_entries(self) -> list[dict[str, str]]:
        entries = []
        with contextlib.suppress(ConfigError):
            for bib in load_config(self.root).bibliography_files():
                text = bib.read_text(encoding="utf-8")
                for m in re.finditer(r"@\w+\s*\{\s*([^,\s]+)\s*,(.*?)(?=\n@|\Z)", text, re.S):
                    title = re.search(r"title\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", m.group(2))
                    author = re.search(r"author\s*=\s*[{\"](.+?)[}\"]\s*,?\s*\n", m.group(2))
                    entries.append({
                        "key": m.group(1),
                        "title": title.group(1).strip("{}") if title else "",
                        "author": author.group(1) if author else "",
                    })  # fmt: skip
        return entries

    def epub(self) -> bytes:
        from .epub import build_epub

        with tempfile.TemporaryDirectory() as tmp:
            out = build_epub(load_config(self.root), Path(tmp) / "book.epub")
            return out.read_bytes()

    # -- building ----------------------------------------------------------------
    def request_build(self) -> None:
        self._last_change = time.monotonic()
        self._pending.set()

    def _worker(self) -> None:
        while not self.closed:
            self._pending.wait()
            if self.closed:
                return
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
            with contextlib.suppress(OSError):  # e.g. the PDF is open in a viewer on Windows
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


def _title_of(path: Path) -> str:
    if path.suffix == ".bib":
        return "Βιβλιογραφία (" + path.name + ")"
    with contextlib.suppress(OSError, UnicodeDecodeError):
        for line in path.read_text(encoding="utf-8").splitlines():
            m = re.match(r"^#\s+(.+?)(\s*\{[^}]*\})?\s*$", line)
            if m:
                return m.group(1)
    return path.stem


def _relpath(target: Path, base: Path) -> str:
    import os

    return os.path.relpath(target, base)


class App:
    """Which project is open, plus the workspace where new ones are created."""

    def __init__(self, workspace: Path | None = None, project: Path | None = None) -> None:
        self.workspace = (workspace or default_workspace()).resolve()
        self.project: Project | None = None
        self.quit_requested = threading.Event()
        if project is not None:
            self.open(project)

    def open(self, path: Path) -> Project:
        path = path.expanduser().resolve()
        if path.name == "book.yaml":
            path = path.parent
        if not (path / "book.yaml").is_file():
            raise UserError(f"Ο φάκελος {path} δεν είναι εργασία greekbook (δεν έχει book.yaml).")
        try:
            load_config(path)
        except ConfigError as exc:
            raise UserError(str(exc)) from exc
        if self.project is not None:
            self.project.close()
        self.project = Project(path)
        remember(path)
        return self.project

    def close_project(self) -> None:
        if self.project is not None:
            self.project.close()
        self.project = None

    def info(self) -> dict[str, Any]:
        current = project_info(self.project.root) if self.project else None
        return {
            "workspace": str(self.workspace),
            "project": current.as_dict() if current else None,
            "projects": [p.as_dict() for p in list_projects(self.workspace)],
            "kinds": KINDS,
            "templates": list(TEMPLATES),
        }

    def create(self, data: dict[str, Any]) -> Project:
        kind = str(data.get("kind", "thesis"))
        if kind not in KINDS:
            raise UserError("Διάλεξε τι θέλεις να γράψεις.")
        title = str(data.get("title", "")).strip()
        if not title:
            raise UserError("Γράψε έναν τίτλο (μπορείς να τον αλλάξεις αργότερα).")
        self.workspace.mkdir(parents=True, exist_ok=True)
        target = unique_folder(self.workspace, title)
        thesis = data.get("thesis") if isinstance(data.get("thesis"), dict) else None
        create_project(target, kind, title, str(data.get("author", "")),
                       example=bool(data.get("example")), thesis=thesis)  # fmt: skip
        return self.open(target)

    def import_docx(self, filename: str, data: bytes, kind: str) -> tuple[Project, list[str]]:
        from .docx_import import ImportError_, import_docx

        if not filename.lower().endswith(".docx"):
            raise UserError("Δεκτά είναι μόνο αρχεία Word .docx (όχι το παλιό .doc).")
        template = {"thesis": "thesis", "book": "novel", "notes": "academic"}.get(kind, "thesis")
        self.workspace.mkdir(parents=True, exist_ok=True)
        target = unique_folder(self.workspace, Path(filename).stem)
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "document.docx"
            src.write_bytes(data)
            try:
                warnings = import_docx(src, target, template)
            except ImportError_ as exc:
                shutil.rmtree(target, ignore_errors=True)
                raise UserError(str(exc)) from exc
        return self.open(target), warnings


# ---------------------------------------------------------------------------
# HTTP
# ---------------------------------------------------------------------------


def make_handler(app: App, token: str, port_ref: list[int]) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = "greekbook"

        def log_message(self, format: str, *args: Any) -> None:
            pass

        # -- helpers ----------------------------------------------------------
        def _send(self, status: int, body: bytes, ctype: str, extra: dict[str, str] | None = None
                  ) -> None:  # fmt: skip
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            for k, v in (extra or {}).items():
                self.send_header(k, v)
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj: Any, status: int = 200) -> None:
            self._send(status, json.dumps(obj, ensure_ascii=False).encode(), "application/json")

        def _error(self, message: str, status: int = HTTPStatus.BAD_REQUEST) -> None:
            self._json({"error": message}, status)

        def _page(self, name: str) -> None:
            html = (WEB_DIR / name).read_text(encoding="utf-8").replace("__TOKEN__", token)
            self._send(200, html.encode(), "text/html; charset=utf-8")

        def _host_ok(self) -> bool:
            host = self.headers.get("Host", "")
            return host in {f"127.0.0.1:{port_ref[0]}", f"localhost:{port_ref[0]}"}

        def _authorized(self) -> bool:
            return secrets.compare_digest(self.headers.get("X-Greekbook-Token", ""), token)

        def _body(self, limit: int = MAX_TEXT) -> bytes:
            length = int(self.headers.get("Content-Length", "0") or 0)
            if length > limit:
                raise UserError("Το αρχείο είναι πολύ μεγάλο.")
            return self.rfile.read(length)

        def _project(self) -> Project:
            if app.project is None:
                raise UserError("Δεν είναι ανοιχτή καμία εργασία.")
            return app.project

        # -- GET ----------------------------------------------------------------
        def do_GET(self) -> None:
            if not self._host_ok():
                return self._send(HTTPStatus.FORBIDDEN, b"bad host", "text/plain")
            url = urlparse(self.path)
            query = parse_qs(url.query)
            try:
                return self._get(url.path, query)
            except UserError as exc:
                return self._error(str(exc))
            except (PermissionError, FileNotFoundError):
                return self._send(HTTPStatus.NOT_FOUND, b"not found", "text/plain")

        def _get(self, path: str, query: dict[str, list[str]]) -> None:
            if path == "/":
                return self._page("editor.html" if app.project else "home.html")
            if path == "/home":
                return self._page("home.html")
            if path.startswith("/img/"):
                name = Path(unquote(path[5:])).name
                file = WEB_DIR / "img" / name
                if file.suffix == ".png" and file.is_file():
                    return self._send(200, file.read_bytes(), "image/png")
                raise FileNotFoundError(name)
            if path == "/api/app":
                return self._json(app.info())
            project = self._project()
            if path == "/api/files":
                return self._json(project.files())
            if path == "/api/status":
                return self._json(project.status())
            if path == "/api/config":
                return self._json({"config": project.raw_config(), "templates": list(TEMPLATES)})
            if path == "/api/bib":
                return self._json(project.bib_entries())
            if path == "/api/file":
                file = project.resolve(query.get("path", [""])[0])
                return self._send(200, file.read_bytes(), "text/plain; charset=utf-8")
            if path == "/api/asset":
                file = project.resolve(query.get("path", [""])[0], IMAGE_SUFFIXES)
                ctype = "image/svg+xml" if file.suffix == ".svg" else f"image/{file.suffix[1:]}"
                return self._send(200, file.read_bytes(), ctype)
            m = re.fullmatch(r"/page/(\d+)\.svg", path)
            if m:
                pages = project.state.pages
                if int(m.group(1)) < len(pages):
                    return self._send(200, pages[int(m.group(1))], "image/svg+xml")
                raise FileNotFoundError(path)
            if path in ("/book.pdf", "/book.epub"):
                name = slugify(project.state.title or "biblio")
                if path.endswith(".pdf"):
                    body, ctype, ext = project.state.pdf, "application/pdf", "pdf"
                else:
                    body, ctype, ext = project.epub(), "application/epub+zip", "epub"
                disposition = "attachment" if query.get("download") else "inline"
                header = {"Content-Disposition": f'{disposition}; filename="{name}.{ext}"'}
                return self._send(200, body, ctype, header)
            raise FileNotFoundError(path)

        # -- writes -------------------------------------------------------------
        def _write(self, method: str) -> None:
            if not (self._host_ok() and self._authorized()):
                return self._send(HTTPStatus.FORBIDDEN, b"forbidden", "text/plain")
            url = urlparse(self.path)
            query = parse_qs(url.query)
            try:
                return self._route_write(method, url.path, query)
            except UserError as exc:
                return self._error(str(exc))
            except (PermissionError, FileNotFoundError, ValueError, UnicodeDecodeError) as exc:
                return self._error(f"Μη έγκυρο αίτημα ({type(exc).__name__}).")

        def do_PUT(self) -> None:
            self._write("PUT")

        def do_POST(self) -> None:
            self._write("POST")

        def _route_write(self, method: str, path: str, query: dict[str, list[str]]) -> None:
            if method == "PUT" and path == "/api/file":
                file = self._project().resolve(query.get("path", [""])[0])
                text = self._body().decode("utf-8")
                file.parent.mkdir(parents=True, exist_ok=True)
                file.write_text(text, encoding="utf-8", newline="")
                self._project().request_build()
                return self._json({"saved": True})
            if method == "PUT" and path == "/api/config":
                data = json.loads(self._body() or b"{}")
                if not isinstance(data, dict):
                    raise UserError("Μη έγκυρες ρυθμίσεις.")
                self._project().save_config(data)
                return self._json({"saved": True})
            if path == "/api/image":
                name = unquote(self.headers.get("X-Filename", "eikona.png"))
                md = self._project().save_image(name, self._body(MAX_UPLOAD),
                                                query.get("for", [""])[0])  # fmt: skip
                return self._json({"markdown": md})
            if path == "/api/projects/import":
                name = unquote(self.headers.get("X-Filename", "document.docx"))
                project, warnings = app.import_docx(name, self._body(MAX_UPLOAD),
                                                    query.get("kind", ["thesis"])[0])  # fmt: skip
                return self._json({"path": str(project.root), "warnings": warnings})
            data = json.loads(self._body() or b"{}")
            if not isinstance(data, dict):
                raise UserError("Μη έγκυρο αίτημα.")
            if path == "/api/projects/create":
                return self._json({"path": str(app.create(data).root)})
            if path == "/api/projects/open":
                return self._json({"path": str(app.open(Path(str(data.get("path", "")))).root)})
            if path == "/api/projects/close":
                app.close_project()
                return self._json({"closed": True})
            if path == "/api/quit":
                app.quit_requested.set()
                return self._json({"bye": True})
            project = self._project()
            if path == "/api/chapter":
                title = str(data.get("title", ""))
                return self._json({"path": project.new_chapter(title, str(data.get("group", "")))})
            if path == "/api/chapter/rename":
                return self._json(
                    {"path": project.rename_chapter(str(data["path"]), str(data["title"]))}
                )
            if path == "/api/chapter/delete":
                project.delete(str(data["path"]))
                return self._json({"deleted": True})
            if path == "/api/chapter/move":
                project.move(str(data["path"]), -1 if data.get("direction") == "up" else 1)
                return self._json({"moved": True})
            if path == "/api/build":
                project.request_build()
                return self._json({"queued": True})
            raise FileNotFoundError(path)

    return Handler


def run_app(
    project: Path | None = None,
    port: int = 8420,
    open_browser: bool = True,
    workspace: Path | None = None,
) -> None:
    """Start the application and block until Ctrl+C or the «Έξοδος» button."""
    app = App(workspace, project)
    token = secrets.token_urlsafe(24)
    port_ref = [port]
    try:
        server = ThreadingHTTPServer(("127.0.0.1", port), make_handler(app, token, port_ref))
    except OSError:  # port taken (another greekbook?) → let the OS pick one
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app, token, port_ref))
    port_ref[0] = server.server_address[1]
    url = f"http://127.0.0.1:{port_ref[0]}/"
    print(f"\n  Το greekbook άνοιξε στον browser σου: {url}")
    print("  Άφησε αυτό το παράθυρο ανοιχτό όσο γράφεις. Για έξοδο: Ctrl+C.\n")
    if open_browser:
        threading.Timer(0.6, webbrowser.open, args=(url,)).start()
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        while not app.quit_requested.wait(0.5):
            pass
    except KeyboardInterrupt:
        print()
    finally:
        server.shutdown()
        server.server_close()
        app.close_project()


def serve(root: Path, port: int = 8420, open_browser: bool = True) -> None:
    """Open the editor directly on one project (``greekbook serve``)."""
    run_app(root, port, open_browser)
