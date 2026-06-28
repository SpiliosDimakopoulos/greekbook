# -*- coding: utf-8 -*-
"""
EPUB export για greekbook.

Μετατρέπει ένα BookConfig σε .epub αρχείο δίπλα στο PDF output,
με CSS που αντικατοπτρίζει το επιλεγμένο theme (sepia / clean / academic).
Κάθε μέρος (.md) γίνεται ξεχωριστό κεφάλαιο/spine item.
"""
from __future__ import annotations

import re
from pathlib import Path

import markdown as _md
from ebooklib import epub

from .config import BookConfig

# ── Θεματικά CSS ────────────────────────────────────────────────────────────

_THEME_CSS: dict[str, str] = {
    "sepia": """
body  { background:#f4ecdd; color:#2b2117; font-family:Georgia,'Times New Roman',serif;
        font-size:1em; line-height:1.65; margin:1.8em 1.4em; }
h1,h2,h3 { color:#7c4a2d; font-weight:bold; margin-top:1.6em; }
h1    { font-size:1.5em; border-bottom:1px solid #a9824f; padding-bottom:.3em; }
h2    { font-size:1.2em; }
p     { margin:.7em 0; text-align:justify; }
p + p { text-indent:1.5em; }
blockquote { border-left:3px solid #a9824f; padding-left:1em; color:#4a3c2c; }
code  { font-family:monospace; background:#ede2cc; padding:.1em .3em; border-radius:3px; }
""",
    "clean": """
body  { background:#fff; color:#1a1a1a; font-family:'Helvetica Neue',Arial,sans-serif;
        font-size:1em; line-height:1.6; margin:1.8em 1.4em; }
h1,h2,h3 { color:#1a1a1a; font-weight:700; margin-top:1.6em; }
h1    { font-size:1.5em; }
h2    { font-size:1.2em; }
p     { margin:.7em 0; text-align:left; }
p + p { text-indent:0; }
blockquote { border-left:3px solid #ccc; padding-left:1em; color:#404040; }
code  { font-family:monospace; background:#f0f0f0; padding:.1em .3em; border-radius:3px; }
""",
    "academic": """
body  { background:#f7f7f5; color:#1c2430; font-family:'DejaVu Serif',Georgia,serif;
        font-size:1em; line-height:1.7; margin:1.8em 1.4em; }
h1,h2,h3 { color:#5a3c1f; font-weight:bold; margin-top:1.6em; }
h1    { font-size:1.4em; border-bottom:1px solid #9a8156; padding-bottom:.3em; }
h2    { font-size:1.15em; }
p     { margin:.75em 0; text-align:justify; }
p + p { text-indent:1.5em; }
blockquote { border-left:3px solid #9a8156; padding-left:1em; color:#3c4656; }
code  { font-family:monospace; background:#eae8e2; padding:.1em .3em; border-radius:3px; }
""",
}

_FALLBACK_CSS = _THEME_CSS["sepia"]

# ── Cover HTML ───────────────────────────────────────────────────────────────

_COVER_COLORS: dict[str, dict] = {
    "sepia":    {"bg": "#241b14", "fg": "#e8d9b8", "line": "#a9824f"},
    "clean":    {"bg": "#111111", "fg": "#ffffff",  "line": "#9c9c9c"},
    "academic": {"bg": "#1c2430", "fg": "#f0ede4",  "line": "#9a8156"},
}


def _cover_html(config: BookConfig) -> str:
    c = _COVER_COLORS.get(config.theme, _COVER_COLORS["sepia"])
    subtitle = f'<p class="subtitle">{_esc(config.subtitle)}</p>' if config.subtitle else ""
    return f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{config.language}">
<head><meta charset="utf-8"/><title>Εξώφυλλο</title>
<style>
body  {{ background:{c["bg"]}; margin:0; padding:0; height:100%; display:flex;
         align-items:center; justify-content:center; }}
.frame {{ border:1px solid {c["line"]}; margin:2.5em; padding:3em 2em;
          text-align:center; flex:1; }}
.title {{ color:{c["fg"]}; font-size:2em; font-weight:bold;
          font-family:Georgia,serif; margin:0 0 .4em; }}
.subtitle {{ color:{c["line"]}; font-size:1.1em; font-family:Georgia,serif; margin:.3em 0; }}
.author {{ color:{c["line"]}; font-size:1em; font-family:Georgia,serif;
           margin-top:2em; letter-spacing:.05em; }}
</style></head>
<body><div class="frame">
  <p class="title">{_esc(config.title)}</p>
  {subtitle}
  <p class="author">{_esc(config.author)}</p>
</div></body></html>"""


# ── Helpers ──────────────────────────────────────────────────────────────────

def _esc(s: str | None) -> str:
    if not s:
        return ""
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;"))


def _md_to_html(text: str, title: str | None) -> str:
    """Convert Markdown body → XHTML fragment, with optional chapter title."""
    html_body = _md.markdown(
        text,
        extensions=["extra", "smarty"],
        output_format="xhtml",
    )
    heading = f"<h1>{_esc(title)}</h1>\n" if title else ""
    return heading + html_body


def _safe_id(s: str) -> str:
    return re.sub(r"[^\w\-]", "_", s).lower()


# ── Main export function ─────────────────────────────────────────────────────

def build_epub(config: BookConfig) -> Path:
    """Build an EPUB from *config* and return the output path."""
    parts = config.discover_parts()

    book = epub.EpubBook()
    book.set_identifier(f"greekbook-{_safe_id(config.title)}")
    book.set_title(config.title)
    book.set_language(config.language)
    book.add_author(config.author)
    if config.subtitle:
        book.add_metadata("DC", "description", config.subtitle)

    # ── CSS ──────────────────────────────────────────────────────────────────
    css_text = _THEME_CSS.get(config.theme, _FALLBACK_CSS)
    css_item = epub.EpubItem(
        uid="style",
        file_name="style/book.css",
        media_type="text/css",
        content=css_text.encode("utf-8"),
    )
    book.add_item(css_item)

    # ── Cover page ───────────────────────────────────────────────────────────
    cover = epub.EpubHtml(
        uid="cover",
        file_name="cover.xhtml",
        title="Εξώφυλλο",
        lang=config.language,
    )
    cover.content = _cover_html(config).encode("utf-8")
    book.add_item(cover)

    # ── Chapters ─────────────────────────────────────────────────────────────
    chapters: list[epub.EpubHtml] = []
    toc_entries: list[epub.Link] = [epub.Link("cover.xhtml", "Εξώφυλλο", "cover")]

    for idx, part in enumerate(parts, start=1):
        chap_id = f"chap{idx:02d}"
        fname   = f"{chap_id}.xhtml"
        title   = part.label or f"Κεφάλαιο {idx}"
        body_html = _md_to_html(part.body, title if not part.label else None)

        xhtml = f"""<?xml version='1.0' encoding='utf-8'?>
<!DOCTYPE html>
<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{config.language}">
<head><meta charset="utf-8"/><title>{_esc(title)}</title>
<link rel="stylesheet" type="text/css" href="style/book.css"/>
</head><body>
{'<h1>' + _esc(title) + '</h1>' if part.label else ''}
{body_html}
</body></html>"""

        chap = epub.EpubHtml(uid=chap_id, file_name=fname,
                             title=title, lang=config.language)
        chap.content = xhtml.encode("utf-8")
        chap.add_item(css_item)
        book.add_item(chap)
        chapters.append(chap)
        toc_entries.append(epub.Link(fname, title, chap_id))

    # ── Navigation ───────────────────────────────────────────────────────────
    book.toc = toc_entries
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = ["nav", cover] + chapters

    # ── Write ────────────────────────────────────────────────────────────────
    epub_path = config.output_path.with_suffix(".epub")
    epub.write_epub(str(epub_path), book, {})
    return epub_path
