"""EPUB 3 export.

E-readers lay out text themselves, so the EPUB carries clean XHTML: the same
Greek typography as the PDF (quotes, dashes, ellipses) plus soft hyphens
from greekbook's own syllabifier, because many readers ship no Greek
hyphenation patterns and justify Greek text with ugly gaps.

Citations are rendered as plain ``(key)`` markers and math as LaTeX source:
EPUB output is meant for prose (novels, essays), the PDF for theses.
"""

from __future__ import annotations

import html
import re
import uuid
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from ebooklib import epub
from markdown_it.renderer import RendererHTML
from markdown_it.token import Token
from markdown_it.utils import EnvType, OptionsDict

from .config import BookConfig
from .hyphenation import syllabify
from .markdown import make_parser
from .typography import QuoteState, typeset, upper_el

SHY = "­"
_GREEK_WORD_RE = re.compile(r"[Ͱ-Ͽἀ-῿]{7,}")
_CITE_RE = re.compile(r"\[(-?@[^\]]+)\]")


def hyphenate_greek(text: str, min_fragment: int = 2) -> str:
    """Insert soft hyphens at Greek syllable boundaries (words ≥ 7 letters)."""

    def word(m: re.Match[str]) -> str:
        w = m.group(0)
        syllables = syllabify(w.lower())
        out, pos = [], 0
        for syl in syllables[:-1]:
            pos += len(syl)
            out.append(pos)
        breaks = [p for p in out if p >= min_fragment and len(w) - p >= min_fragment]
        result, last = [], 0
        for p in breaks:
            result.append(w[last:p])
            last = p
        result.append(w[last:])
        return SHY.join(result)

    return _GREEK_WORD_RE.sub(word, text)


_CSS = {
    "base": """
body { font-family: serif; line-height: 1.5; margin: 0 4%; }
p { margin: 0; text-align: justify; text-indent: 1.3em; hyphens: auto; -epub-hyphens: auto; }
h1 + p, h2 + p, h3 + p, hr + p, blockquote + p, .first { text-indent: 0; }
h1 { font-weight: normal; font-size: 1.6em; text-align: center; margin: 3em 0 2em; }
h1 .label { display: block; font-size: .55em; letter-spacing: .25em; margin-bottom: 1em; }
h2 { font-size: 1.2em; margin: 1.8em 0 .8em; }
h3 { font-size: 1.05em; font-style: italic; margin: 1.5em 0 .6em; }
hr { border: 0; text-align: center; margin: 1.4em 0; }
hr::after { content: "⁂"; }
blockquote { margin: 1em 1.6em; font-size: .95em; }
pre, code { font-family: monospace; font-size: .85em; }
pre { white-space: pre-wrap; background: #f4f4f4; padding: .6em; }
table { border-collapse: collapse; margin: 1em auto; }
th, td { padding: .3em .6em; border-bottom: 1px solid #999; }
img { max-width: 100%; }
.footnotes { font-size: .85em; }
.title-page { text-align: center; margin-top: 30%; }
.title-page .author { letter-spacing: .2em; font-size: .9em; }
.title-page .title { font-size: 2em; margin: 1.5em 0 .5em; }
.title-page .subtitle { font-style: italic; }
""",
    "sepia": "body { color: #2b2117; } h1 .label, hr::after { color: #7c4a2d; }",
    "clean": "body { font-family: sans-serif; } p { text-indent: 0; margin-bottom: .8em; }",
}


class _Renderer(RendererHTML):
    """HTML renderer that applies Greek typography to text runs."""

    def __init__(self, parser: Any = None) -> None:
        super().__init__(parser)
        self.lang = "el"
        self.state = QuoteState(self.lang)

    def text(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        content = _CITE_RE.sub(
            lambda m: "(" + m.group(1).replace("@", "") + ")", tokens[idx].content
        )
        content = hyphenate_greek(typeset(content, self.state))
        return html.escape(content, quote=False)

    def paragraph_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        self.state = QuoteState(self.lang)
        return super().renderToken(tokens, idx, options, env)

    def heading_open(
        self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType
    ) -> str:
        self.state = QuoteState(self.lang)
        return super().renderToken(tokens, idx, options, env)

    def hr(self, tokens: Sequence[Token], idx: int, options: OptionsDict, env: EnvType) -> str:
        return "<hr/>\n"


def _xhtml(title: str, body: str, lang: str) -> str:
    return (
        "<?xml version='1.0' encoding='utf-8'?>\n<!DOCTYPE html>\n"
        f'<html xmlns="http://www.w3.org/1999/xhtml" xml:lang="{lang}" lang="{lang}">\n'
        f'<head><meta charset="utf-8"/><title>{html.escape(title)}</title>'
        '<link rel="stylesheet" type="text/css" href="style/book.css"/></head>\n'
        f"<body>\n{body}\n</body></html>"
    )


_HEADING_ATTRS_RE = re.compile(r"\s*\{[^{}]*\}\s*$", re.MULTILINE)


def build_epub(cfg: BookConfig, output: Path | None = None) -> Path:
    """Write ``<output>.epub`` next to the PDF and return its path."""
    parser = make_parser()
    renderer = _Renderer(parser)
    renderer.lang = cfg.language
    parser.renderer = renderer

    book = epub.EpubBook()
    book.set_identifier(f"urn:uuid:{uuid.uuid5(uuid.NAMESPACE_URL, cfg.title + cfg.author)}")
    book.set_title(cfg.title)
    book.set_language(cfg.language)
    book.add_author(cfg.author)
    if cfg.subtitle:
        book.add_metadata("DC", "description", cfg.subtitle)

    css = _CSS["base"] + _CSS.get(cfg.template, "")
    style = epub.EpubItem(uid="style", file_name="style/book.css", media_type="text/css",
                          content=css.encode("utf-8"))  # fmt: skip
    book.add_item(style)

    def esc(s: str) -> str:
        return html.escape(typeset(s, QuoteState(cfg.language)))

    title_body = (
        '<section class="title-page" epub:type="titlepage">'
        f'<p class="author">{html.escape(upper_el(cfg.author))}</p>'
        f'<h1 class="title">{esc(cfg.title)}</h1>'
        + (f'<p class="subtitle">{esc(cfg.subtitle)}</p>' if cfg.subtitle else "")
        + "</section>"
    )
    title_page = epub.EpubHtml(uid="title", file_name="title.xhtml", title=cfg.title,
                               lang=cfg.language)  # fmt: skip
    title_page.content = _xhtml(cfg.title, title_body, cfg.language).encode("utf-8")
    title_page.add_item(style)
    book.add_item(title_page)

    chapters: list[epub.EpubHtml] = []
    toc: list[epub.Link] = []
    files = cfg.front_matter_files() + cfg.chapter_files() + cfg.appendix_files()
    for idx, path in enumerate(files, 1):
        text = _HEADING_ATTRS_RE.sub("", path.read_text(encoding="utf-8"))
        m = re.search(r"^#\s+(.+)$", text, re.MULTILINE)
        title = m.group(1).strip() if m else f"{idx}"
        body = parser.render(text)
        for img in re.findall(r'<img src="([^"]+)"', body):
            src = (path.parent / img).resolve()
            if src.is_file():
                name = f"images/{src.name}"
                book.add_item(epub.EpubItem(file_name=name, content=src.read_bytes(),
                                            media_type=_media_type(src)))  # fmt: skip
                body = body.replace(f'src="{img}"', f'src="{name}"')
        uid = f"ch{idx:02d}"
        chapter = epub.EpubHtml(uid=uid, file_name=f"{uid}.xhtml", title=title, lang=cfg.language)
        chapter.content = _xhtml(title, body, cfg.language).encode("utf-8")
        chapter.add_item(style)
        book.add_item(chapter)
        chapters.append(chapter)
        toc.append(epub.Link(f"{uid}.xhtml", title, uid))

    book.toc = toc
    book.add_item(epub.EpubNcx())
    book.add_item(epub.EpubNav())
    book.spine = [title_page, "nav", *chapters]
    out = (output or cfg.output_path).with_suffix(".epub")
    out.parent.mkdir(parents=True, exist_ok=True)
    epub.write_epub(str(out), book, {})
    return out


def _media_type(path: Path) -> str:
    return {
        ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
        ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp",
    }.get(path.suffix.lower(), "application/octet-stream")  # fmt: skip
