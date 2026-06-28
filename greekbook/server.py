# -*- coding: utf-8 -*-
"""
Τοπικό web UI για greekbook (`greekbook serve <book_dir>`).

Χρησιμοποιεί μόνο την Python stdlib (http.server) — καμία νέα εξάρτηση.
Σερβίρει μία σελίδα με: πεδία book.yaml, textarea ανά αρχείο .md,
κουμπί Build, inline προεπισκόπηση PDF, upload εγγράφων (PDF/DOCX/TXT→MD),
και διαχείριση examples.
"""
import cgi
import io
import json
import os
import re
import shutil
import tempfile
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

import yaml

from .builder import build_book
from .config import ConfigError, load_config
from .epub_builder import build_epub
from .themes import available_themes

_HTML_PATH = Path(__file__).parent / "web" / "index.html"
_WIZARD_PATH = Path(__file__).parent / "web" / "wizard.html"


# ---------------------------------------------------------------------------
# Document → Markdown conversion
# ---------------------------------------------------------------------------

def _docx_to_md(data: bytes) -> str:
    """Convert a .docx file (bytes) to a plain-text Markdown string."""
    import docx as _docx
    doc = _docx.Document(io.BytesIO(data))
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if not text:
            lines.append("")
            continue
        style = (para.style.name or "").lower()
        if "heading 1" in style:
            lines.append(f"# {text}")
        elif "heading 2" in style:
            lines.append(f"## {text}")
        elif "heading 3" in style:
            lines.append(f"### {text}")
        else:
            lines.append(text)
    return "\n".join(lines)


def _pdf_to_md(data: bytes) -> str:
    """Extract text from a PDF (bytes) and return as Markdown."""
    import pdfplumber
    pages_text = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t.strip())
    return "\n\n".join(pages_text)


def _txt_to_md(data: bytes) -> str:
    """Decode a text file and return as-is."""
    for enc in ("utf-8", "utf-8-sig", "iso-8859-7", "cp1253", "latin-1"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _convert_document(filename: str, data: bytes) -> str:
    ext = Path(filename).suffix.lower()
    if ext == ".docx":
        return _docx_to_md(data)
    elif ext == ".pdf":
        return _pdf_to_md(data)
    elif ext in (".txt", ".md"):
        return _txt_to_md(data)
    else:
        raise ValueError(f"Μη υποστηριζόμενος τύπος αρχείου: {ext}")


# ---------------------------------------------------------------------------
# State helpers (unchanged from original)
# ---------------------------------------------------------------------------

def _read_parts(book_dir: Path, parts_dir: str):
    parts_path = book_dir / parts_dir
    if not parts_path.is_dir():
        return []
    out = []
    for p in sorted(parts_path.glob("*.md")):
        out.append({"filename": p.name, "text": p.read_text(encoding="utf-8")})
    return out


def _state(book_dir: Path):
    yaml_path = book_dir / "book.yaml"
    raw = {}
    if yaml_path.exists():
        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
    return {
        "title": raw.get("title", ""),
        "author": raw.get("author", ""),
        "subtitle": raw.get("subtitle", ""),
        "language": raw.get("language", "el"),
        "theme": raw.get("theme", "sepia"),
        "page_size": raw.get("page_size", "A5"),
        "parts_dir": raw.get("parts_dir", "parts"),
        "output": raw.get("output", "book.pdf"),
        "cover_image": raw.get("cover_image", ""),
        "available_themes": available_themes(),
        "parts": _read_parts(book_dir, raw.get("parts_dir", "parts")),
    }


def _save(book_dir: Path, payload: dict):
    fields = {k: payload.get(k, "") for k in
              ("title", "author", "subtitle", "language", "theme", "page_size", "parts_dir", "output")}
    # Preserve cover_image if it exists on disk (don't wipe it via normal save)
    ci = payload.get("cover_image") or ""
    if ci:
        fields["cover_image"] = ci
    else:
        # Check if one already exists on disk and keep it
        yaml_path = book_dir / "book.yaml"
        if yaml_path.exists():
            existing = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
            if existing.get("cover_image"):
                fields["cover_image"] = existing["cover_image"]
    yaml_path = book_dir / "book.yaml"
    yaml_path.write_text(
        yaml.safe_dump(fields, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    parts_path = book_dir / fields["parts_dir"]
    parts_path.mkdir(parents=True, exist_ok=True)
    sent_filenames = {part["filename"] for part in payload.get("parts", [])}
    for existing in parts_path.glob("*.md"):
        if existing.name not in sent_filenames:
            existing.unlink()
    for part in payload.get("parts", []):
        (parts_path / part["filename"]).write_text(part["text"], encoding="utf-8")


# ---------------------------------------------------------------------------
# Examples helpers
# ---------------------------------------------------------------------------

def _examples_dir(book_dir: Path) -> Path:
    """The examples folder sits two levels up from book_dir: project_root/examples/"""
    # Walk up looking for a directory that has a pyproject.toml or examples/ sibling
    candidate = book_dir.parent
    examples = candidate / "examples"
    if examples.is_dir():
        return examples
    # Fallback: create an examples dir next to book_dir
    examples = book_dir.parent / "examples"
    examples.mkdir(parents=True, exist_ok=True)
    return examples


def _list_examples(book_dir: Path):
    examples = _examples_dir(book_dir)
    result = []
    for child in sorted(examples.iterdir()):
        if child.is_dir():
            yaml_path = child / "book.yaml"
            meta = {}
            if yaml_path.exists():
                try:
                    meta = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                except Exception:
                    pass
            result.append({
                "name": child.name,
                "title": meta.get("title", child.name),
                "author": meta.get("author", ""),
            })
    return result


def _upload_as_example(book_dir: Path, example_name: str, state: dict):
    """Save the current state as a new example folder."""
    examples = _examples_dir(book_dir)
    # Sanitise name
    safe = re.sub(r"[^\w\-]", "_", example_name).strip("_") or "example"
    dest = examples / safe
    dest.mkdir(parents=True, exist_ok=True)
    parts_path = dest / "parts"
    parts_path.mkdir(exist_ok=True)
    # Write book.yaml
    fields = {k: state.get(k, "") for k in
              ("title", "author", "subtitle", "language", "theme", "page_size", "parts_dir", "output")}
    (dest / "book.yaml").write_text(
        yaml.safe_dump(fields, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    # Write parts
    for part in state.get("parts", []):
        (parts_path / part["filename"]).write_text(part["text"], encoding="utf-8")
    return safe


def _load_example_state(book_dir: Path, name: str):
    """Read an example folder's contents as a state dict, ready to send to the UI.
    Returns None if the name is invalid or the example doesn't exist.
    An example folder shares the same book.yaml + parts/ layout as a real
    book_dir, so the existing _state() reader can be reused as-is.
    """
    if not name or not re.fullmatch(r"[\w\-]+", name):
        return None
    examples = _examples_dir(book_dir)
    example_dir = (examples / name).resolve()
    # Guard against path traversal: the resolved path must stay inside examples/
    if examples.resolve() not in example_dir.parents and example_dir != examples.resolve():
        return None
    if not example_dir.is_dir() or not (example_dir / "book.yaml").exists():
        return None
    return _state(example_dir)


# ---------------------------------------------------------------------------
# Background build engine
# ---------------------------------------------------------------------------

class _BuildEngine:
    """Runs greekbook builds on a background thread.
    The UI posts /api/autosave → engine schedules a build after a quiet period.
    Status is polled via GET /api/build-status.
    """
    def __init__(self, book_dir: Path, debounce: float = 2.5):
        self.book_dir = book_dir
        self.debounce = debounce
        self._lock = threading.Lock()
        self._status = "idle"   # idle | building | ok | error
        self._error = ""
        self._pdf_mtime = 0.0
        self._timer: threading.Timer | None = None
        self._refresh_pdf_mtime()

    def _get_pdf_path(self) -> Path:
        """Read actual output path from book.yaml (falls back to book.pdf)."""
        yaml_path = self.book_dir / "book.yaml"
        if yaml_path.exists():
            try:
                raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                output = raw.get("output", "book.pdf")
                p = Path(output)
                return p if p.is_absolute() else self.book_dir / p
            except Exception:
                pass
        return self.book_dir / "book.pdf"

    def _refresh_pdf_mtime(self):
        p = self._get_pdf_path()
        self._pdf_mtime = p.stat().st_mtime if p.exists() else 0.0

    def schedule(self):
        """Called after every autosave; resets the debounce timer."""
        with self._lock:
            if self._timer is not None:
                self._timer.cancel()
            self._timer = threading.Timer(self.debounce, self._run)
            self._timer.daemon = True
            self._timer.start()

    def _run(self):
        with self._lock:
            self._status = "building"
            self._error = ""
        try:
            config = load_config(str(self.book_dir / "book.yaml"))
            build_book(config, quiet=True)
            with self._lock:
                self._status = "ok"
                self._refresh_pdf_mtime()
        except Exception as exc:
            with self._lock:
                self._status = "error"
                self._error = str(exc)

    def status(self) -> dict:
        with self._lock:
            return {
                "status": self._status,
                "error": self._error,
                "pdf_mtime": self._pdf_mtime,
            }


# ---------------------------------------------------------------------------
# HTTP Handler
# ---------------------------------------------------------------------------

def make_handler(book_dir: Path):
    engine = _BuildEngine(book_dir)

    class Handler(BaseHTTPRequestHandler):
        def _json(self, obj, status=200):
            body = json.dumps(obj, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt, *args):
            pass  # σιωπή

        def _serve_html(self, html_path):
            html = html_path.read_text(encoding="utf-8")
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _redirect(self, location):
            self.send_response(302)
            self.send_header("Location", location)
            self.end_headers()

        def do_GET(self):
            path = urlparse(self.path).path
            yaml_exists = (book_dir / "book.yaml").exists()

            if path == "/":
                if not yaml_exists:
                    self._redirect("/wizard")
                    return
                self._serve_html(_HTML_PATH)
            elif path == "/wizard":
                self._serve_html(_WIZARD_PATH)
            elif path == "/api/state":
                self._json(_state(book_dir))
            elif path == "/api/examples":
                self._json({"ok": True, "examples": _list_examples(book_dir)})
            elif path == "/api/load-example":
                qs = parse_qs(urlparse(self.path).query)
                name = (qs.get("name") or [""])[0]
                loaded = _load_example_state(book_dir, name)
                if loaded is None:
                    self._json({"ok": False, "error": "Το example δεν βρέθηκε."}, status=404)
                else:
                    self._json({"ok": True, "state": loaded})
            elif path == "/api/build-status":
                self._json(engine.status())
            elif path == "/preview.pdf":
                try:
                    config = load_config(str(book_dir / "book.yaml"))
                    pdf_path = config.output_path
                except Exception:
                    pdf_path = book_dir / "book.pdf"
                if not pdf_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                data = pdf_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "application/pdf")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/cover-image":
                yaml_path = book_dir / "book.yaml"
                cover_rel = ""
                if yaml_path.exists():
                    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                    cover_rel = raw.get("cover_image", "")
                if not cover_rel:
                    self.send_response(404); self.end_headers(); return
                cover_path = (book_dir / cover_rel).resolve()
                if not cover_path.exists():
                    self.send_response(404); self.end_headers(); return
                ext = cover_path.suffix.lower()
                mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg",
                        "png": "image/png", "webp": "image/webp"}.get(ext.lstrip("."), "image/jpeg")
                data = cover_path.read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", mime)
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            elif path == "/download.epub":
                from urllib.parse import quote
                config = load_config(str(book_dir / "book.yaml"))
                epub_path = config.output_path.with_suffix(".epub")
                if not epub_path.exists():
                    self.send_response(404)
                    self.end_headers()
                    return
                data = epub_path.read_bytes()
                safe_name = quote(epub_path.name)
                self.send_response(200)
                self.send_header("Content-Type", "application/epub+zip")
                self.send_header("Content-Disposition",
                                 f'attachment; filename="{safe_name}"')
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            else:
                self.send_response(404)
                self.end_headers()

        def do_POST(self):
            path = urlparse(self.path).path
            content_type = self.headers.get("Content-Type", "")

            # ── Multipart: document upload ──────────────────────────────────
            if path == "/api/upload-doc":
                if "multipart/form-data" not in content_type:
                    self._json({"ok": False, "error": "Expected multipart/form-data"}, status=400)
                    return
                length = int(self.headers.get("Content-Length", 0))
                raw_body = self.rfile.read(length)
                # Parse boundary
                boundary = None
                for part in content_type.split(";"):
                    part = part.strip()
                    if part.startswith("boundary="):
                        boundary = part[len("boundary="):].strip('"')
                        break
                if not boundary:
                    self._json({"ok": False, "error": "No boundary in multipart"}, status=400)
                    return
                # Manual multipart parse (stdlib cgi removed in 3.13, use our own)
                files = _parse_multipart(raw_body, boundary)
                results = []
                for fname, fdata in files:
                    try:
                        md_text = _convert_document(fname, fdata)
                        # Make a safe .md filename
                        stem = re.sub(r"[^\w\-]", "_", Path(fname).stem)
                        md_name = f"{stem}.md"
                        results.append({"filename": md_name, "text": md_text})
                    except Exception as e:
                        self._json({"ok": False, "error": f"Σφάλμα μετατροπής '{fname}': {e}"}, status=400)
                        return
                self._json({"ok": True, "parts": results})
                return

            if path == "/api/upload-cover":
                try:
                    if "multipart/form-data" not in content_type:
                        self._json({"ok": False, "error": "Expected multipart/form-data"}, status=400)
                        return
                    length = int(self.headers.get("Content-Length", 0))
                    raw_body = self.rfile.read(length)
                    boundary = None
                    for part in content_type.split(";"):
                        part = part.strip()
                        if part.startswith("boundary="):
                            boundary = part[len("boundary="):].strip('"')
                            break
                    if not boundary:
                        self._json({"ok": False, "error": "No boundary"}, status=400)
                        return
                    files = _parse_multipart(raw_body, boundary)
                    if not files:
                        self._json({"ok": False, "error": "Δεν βρέθηκε αρχείο."}, status=400)
                        return
                    fname, fdata = files[0]
                    ext = Path(fname).suffix.lower()
                    if ext not in (".jpg", ".jpeg", ".png", ".webp"):
                        self._json({"ok": False, "error": f"Μη αποδεκτός τύπος '{ext}'. Αποδεκτά: JPG, PNG, WEBP"}, status=400)
                        return
                    if len(fdata) == 0:
                        self._json({"ok": False, "error": "Το αρχείο είναι άδειο."}, status=400)
                        return
                    cover_dir = book_dir / "assets"
                    cover_dir.mkdir(exist_ok=True)
                    dest = cover_dir / f"cover{ext}"
                    dest.write_bytes(fdata)
                    rel = f"assets/cover{ext}"
                    # Persist in book.yaml
                    yaml_path = book_dir / "book.yaml"
                    raw = {}
                    if yaml_path.exists():
                        raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                    raw["cover_image"] = rel
                    yaml_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
                    self._json({"ok": True, "cover_image": rel})
                except Exception as e:
                    self._json({"ok": False, "error": f"Σφάλμα αποθήκευσης: {e}"}, status=500)
                return

            # ── JSON endpoints ───────────────────────────────────────────────
            length = int(self.headers.get("Content-Length", 0))
            payload = json.loads(self.rfile.read(length) or b"{}")

            if path == "/api/autosave":
                try:
                    _save(book_dir, payload)
                    engine.schedule()
                    self._json({"ok": True})
                except OSError as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return

            if path == "/api/save":
                try:
                    _save(book_dir, payload)
                    self._json({"ok": True})
                except OSError as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return

            if path == "/api/build":
                try:
                    _save(book_dir, payload)
                    config = load_config(str(book_dir / "book.yaml"))
                    build_book(config, quiet=True)
                    self._json({"ok": True})
                except ConfigError as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                except Exception as e:
                    self._json({"ok": False, "error": f"Αποτυχία build: {e}"}, status=400)
                return

            if path == "/api/remove-cover":
                yaml_path = book_dir / "book.yaml"
                if yaml_path.exists():
                    raw = yaml.safe_load(yaml_path.read_text(encoding="utf-8")) or {}
                    rel = raw.pop("cover_image", "")
                    yaml_path.write_text(yaml.safe_dump(raw, allow_unicode=True, sort_keys=False), encoding="utf-8")
                    if rel:
                        p = (book_dir / rel)
                        if p.exists():
                            p.unlink(missing_ok=True)
                self._json({"ok": True})
                return

            if path == "/api/build-epub":
                try:
                    _save(book_dir, payload)
                    config = load_config(str(book_dir / "book.yaml"))
                    epub_path = build_epub(config)
                    self._json({"ok": True, "filename": epub_path.name})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return

            if path == "/api/upload-example":
                try:
                    _save(book_dir, payload)
                    name = payload.get("example_name", "").strip()
                    if not name:
                        self._json({"ok": False, "error": "Δεν δόθηκε όνομα για το example."}, status=400)
                        return
                    saved = _upload_as_example(book_dir, name, payload)
                    self._json({"ok": True, "saved_as": saved})
                except Exception as e:
                    self._json({"ok": False, "error": str(e)}, status=400)
                return

            self.send_response(404)
            self.end_headers()

    return Handler


def _parse_multipart(body: bytes, boundary: str):
    """Minimal multipart/form-data parser. Returns list of (filename, data)."""
    sep = ("--" + boundary).encode()
    end = ("--" + boundary + "--").encode()
    parts = []
    segments = body.split(sep)
    for seg in segments:
        seg = seg.strip(b"\r\n")
        if not seg or seg == b"--":
            continue
        if b"\r\n\r\n" not in seg:
            continue
        header_block, _, file_data = seg.partition(b"\r\n\r\n")
        # Strip trailing --
        if file_data.endswith(b"\r\n--"):
            file_data = file_data[:-4]
        file_data = file_data.rstrip(b"\r\n")
        # Find filename
        header_str = header_block.decode("utf-8", errors="replace")
        fname = None
        for line in header_str.splitlines():
            if "filename=" in line:
                m = re.search(r'filename="([^"]+)"', line)
                if m:
                    fname = m.group(1)
        if fname and file_data:
            parts.append((fname, file_data))
    return parts


def run_server(book_dir: Path, port: int = 8420, open_browser: bool = True) -> None:
    import os
    book_dir = book_dir.resolve()
    host = "0.0.0.0" if os.environ.get("FLY_APP_NAME") or os.environ.get("GREEKBOOK_HOST") == "0.0.0.0" else "127.0.0.1"
    server = ThreadingHTTPServer((host, port), make_handler(book_dir))
    url = f"http://127.0.0.1:{port}/"
    print(f"greekbook: UI στο {url}  (Ctrl+C για έξοδο)")

    if open_browser:
        threading.Timer(0.4, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\ngreekbook: έξοδος.")
