"""Markdown → Typst markup.

The Markdown dialect is CommonMark plus the Pandoc extensions that people
writing books and theses actually use:

* footnotes (``[^1]`` and inline ``^[…]``), tables, ``~~strike~~``
* math: ``$…$`` and ``$$…$$`` in LaTeX syntax (or Typst syntax)
* citations: ``[@knuth1984, σ. 12]``, ``[@a; @b]``, prose ``@knuth1984``
* cross-references: ``{#fig:map}`` labels and ``@fig:map`` references,
  for figures, tables (``Table: caption {#tbl:x}``), equations
  (``$$…$$ (eq:x)``) and headings (``# Title {#sec:x}``)
* heading classes ``{.unnumbered}`` / ``{-}`` and ``{.part}``
* ``---`` between paragraphs is a scene break; ``\\newpage`` a page break

Text runs go through :mod:`greekbook.typography` before being escaped,
so the generated Typst never relies on Typst's own smart quotes.
"""

from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from markdown_it import MarkdownIt
from markdown_it.token import Token
from markdown_it.tree import SyntaxTreeNode
from mdit_py_plugins.attrs import attrs_plugin
from mdit_py_plugins.dollarmath import dollarmath_plugin
from mdit_py_plugins.footnote import footnote_plugin
from mdit_py_plugins.front_matter import front_matter_plugin

from .typography import QuoteState, typeset


def make_parser() -> MarkdownIt:
    md = MarkdownIt("commonmark", {"typographer": False})
    md.enable(["table", "strikethrough"])
    md.use(front_matter_plugin)
    md.use(footnote_plugin)
    md.use(dollarmath_plugin, allow_space=True, allow_digits=True, double_inline=True)
    md.use(attrs_plugin)
    return md


# ---------------------------------------------------------------------------
# Escaping and Typst values
# ---------------------------------------------------------------------------

_ALWAYS_ESCAPE = set("\\#*_`$<>@[]~\"'")
_LINE_START_RE = re.compile(r"^(\s*)([=+\-/]|\d+\.)")


def escape(text: str, line_start: bool = False) -> str:
    """Escape plain text for Typst markup mode."""
    out: list[str] = []
    n = len(text)
    for i, ch in enumerate(text):
        nxt = text[i + 1] if i + 1 < n else ""
        if (
            ch in _ALWAYS_ESCAPE
            or (ch == "/" and nxt in "/*")
            or (ch == "-" and nxt in "-?")
            or (ch == "." and text.startswith("...", i))
        ):
            out.append("\\" + ch)
        else:
            out.append(ch)
    result = "".join(out)
    if line_start:

        def guard(m: re.Match[str]) -> str:
            marker = m.group(2)
            if marker.endswith("."):  # "2024." would start a numbered list
                return m.group(1) + marker[:-1] + "\\."
            return m.group(1) + "\\" + marker

        result = _LINE_START_RE.sub(guard, result, count=1)
    return result


def string(value: str) -> str:
    """A Typst string literal."""
    return '"' + value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


@dataclass(frozen=True)
class Code:
    """Verbatim Typst code inside a value passed to :func:`value`."""

    code: str


def value(obj: Any) -> str:
    """Serialize a Python value as a Typst expression."""
    if isinstance(obj, Code):
        return obj.code
    if obj is None:
        return "none"
    if isinstance(obj, bool):
        return "true" if obj else "false"
    if isinstance(obj, (int, float)):
        return repr(obj)
    if isinstance(obj, str):
        return string(obj)
    if isinstance(obj, dict):
        if not obj:
            return "(:)"
        return "(" + ", ".join(f"{string(str(k))}: {value(v)}" for k, v in obj.items()) + ")"
    if isinstance(obj, (list, tuple)):
        return "(" + "".join(value(v) + ", " for v in obj) + ")"
    raise TypeError(f"cannot serialize {type(obj).__name__} to Typst")


# ---------------------------------------------------------------------------
# Citations and references inside text
# ---------------------------------------------------------------------------

_KEY = r"[\w][\w:.\-/]*[\w]|[\w]"
_BRACKET_CITE_RE = re.compile(r"\[([^\[\]]*?-?@(?:" + _KEY + r")[^\[\]]*)\]")
_BARE_CITE_RE = re.compile(r"(?<![\w@.\\])@(" + _KEY + r")")
_CITE_ITEM_RE = re.compile(
    r"^\s*(?P<pre>[^@]*?)\s*(?P<neg>-)?@(?P<key>" + _KEY + r")\s*,?\s*(?P<loc>.*?)\s*$"
)
_REF_PREFIXES = ("fig:", "tbl:", "eq:", "sec:", "lst:", "ch:", "app:")


def _label(key: str) -> str:
    return "<" + key + ">"


# ---------------------------------------------------------------------------
# Writer
# ---------------------------------------------------------------------------


@dataclass
class Diagnostic:
    file: str
    line: int
    message: str

    def __str__(self) -> str:
        return f"{self.file}:{self.line}: {self.message}"


@dataclass
class Context:
    """Per-document settings for the writer."""

    lang: str = "el"
    math: str = "latex"  # or "typst"
    source: str = "<string>"
    # Directory of the Markdown file relative to the Typst root, so that
    # images can be addressed as root-relative paths ("/chapters/img.png").
    base: PurePosixPath = field(default_factory=lambda: PurePosixPath("/"))
    diagnostics: list[Diagnostic] = field(default_factory=list)
    footnotes: dict[int, str] = field(default_factory=dict)
    labels: set[str] = field(default_factory=set)
    # Front matter (abstract, preface, …): headings are never numbered.
    unnumbered: bool = False

    def warn(self, node: SyntaxTreeNode | None, message: str) -> None:
        line = (node.map[0] + 1) if node is not None and node.map else 0
        self.diagnostics.append(Diagnostic(self.source, line, message))


_HEADING_ATTRS_RE = re.compile(r"\s*\{([^{}]*)\}\s*$")
_TABLE_CAPTION_RE = re.compile(r"^\s*(?:Table|Πίνακας|):\s*", re.IGNORECASE)
_PAGEBREAK = {"\\newpage", "\\pagebreak", "<!-- pagebreak -->", "<!-- newpage -->"}


def _parse_attr_string(s: str) -> tuple[str | None, list[str], dict[str, str]]:
    ident: str | None = None
    classes: list[str] = []
    kv: dict[str, str] = {}
    for part in s.split():
        if part.startswith("#"):
            ident = part[1:]
        elif part.startswith("."):
            classes.append(part[1:])
        elif part == "-":
            classes.append("unnumbered")
        elif "=" in part:
            k, _, v = part.partition("=")
            kv[k] = v.strip("\"'")
    return ident, classes, kv


class TypstWriter:
    def __init__(self, ctx: Context) -> None:
        self.ctx = ctx

    # -- entry -------------------------------------------------------------
    def convert(self, md_text: str) -> str:
        parser = make_parser()
        env: dict[str, Any] = {}
        tokens = parser.parse(md_text, env)
        root = SyntaxTreeNode(tokens)
        self._collect_footnotes(root)
        blocks = self._blocks(root.children)
        return "\n\n".join(b for b in blocks if b) + "\n"

    # -- footnotes ---------------------------------------------------------
    def _collect_footnotes(self, root: SyntaxTreeNode) -> None:
        """Render every footnote body up front; ``footnote_ref`` nodes then
        inline them as ``#footnote[…]`` (Typst places them on the page)."""
        for node in root.children:
            if node.type != "footnote_block":
                continue
            for fn in node.children:
                fid = fn.meta.get("id")
                if fid is not None:
                    body = [b for b in self._blocks(fn.children) if b]
                    self.ctx.footnotes[fid] = "\n\n".join(body)

    # -- blocks ------------------------------------------------------------
    def _blocks(self, nodes: Iterable[SyntaxTreeNode]) -> list[str]:
        out: list[str] = []
        nodes = list(nodes)
        i = 0
        while i < len(nodes):
            node = nodes[i]
            nxt = nodes[i + 1] if i + 1 < len(nodes) else None
            if node.type == "table":
                caption, label = None, None
                if nxt is not None and nxt.type == "paragraph":
                    text = nxt.children[0].content if nxt.children else ""
                    if _TABLE_CAPTION_RE.match(text):
                        caption, label = self._table_caption(nxt, text)
                        i += 1
                out.append(self._table(node, caption, label))
            else:
                out.append(self._block(node))
            i += 1
        return out

    def _block(self, node: SyntaxTreeNode) -> str:
        handler = getattr(self, "_b_" + node.type, None)
        if handler is None:
            if node.type not in ("footnote_block", "front_matter"):
                self.ctx.warn(node, f"αγνοήθηκε στοιχείο Markdown '{node.type}'")
            return ""
        result: str = handler(node)
        return result

    def _b_paragraph(self, node: SyntaxTreeNode) -> str:
        inline = node.children[0] if node.children else None
        if inline is None:
            return ""
        raw = inline.content.strip()
        if raw in _PAGEBREAK:
            return "#pagebreak()"
        kids = [c for c in inline.children if not (c.type == "text" and not c.content.strip())]
        if kids and kids[0].type == "image":
            # The attrs plugin rejects unquoted values like width=60%, which
            # then arrive as a trailing "{…}" text node: parse those here.
            if len(kids) == 2 and kids[1].type == "text":
                m = _HEADING_ATTRS_RE.fullmatch(kids[1].content)
                if m:
                    ident, _, kv = _parse_attr_string(m.group(1))
                    return self._figure(kids[0], ident, kv)
            if len(kids) == 1:
                return self._figure(kids[0])
        return self._inlines(inline.children, QuoteState(self.ctx.lang), line_start=True)

    def _b_heading(self, node: SyntaxTreeNode) -> str:
        level = int(node.tag[1])
        inline = node.children[0]
        children = list(inline.children)
        ident: str | None = None
        classes: list[str] = []
        if children and children[-1].type == "text":
            m = _HEADING_ATTRS_RE.search(children[-1].content)
            if m:
                ident, classes, _ = _parse_attr_string(m.group(1))
                trimmed = children[-1].content[: m.start()]
                children[-1] = _TextNode(trimmed)
        body = self._inlines(children, QuoteState(self.ctx.lang)).strip()
        label = ""
        if ident:
            label = " " + _label(ident)
            self.ctx.labels.add(ident)
        if "part" in classes:
            return f"#gb-part[{body}]{label}"
        if "unnumbered" in classes or self.ctx.unnumbered:
            return f"#heading(level: {level}, numbering: none)[{body}]{label}"
        return "=" * level + " " + body + label

    def _b_hr(self, node: SyntaxTreeNode) -> str:
        return "#gb-scene-break()"

    def _b_blockquote(self, node: SyntaxTreeNode) -> str:
        inner = "\n\n".join(b for b in self._blocks(node.children) if b)
        return f"#quote(block: true)[\n{inner}\n]"

    def _b_bullet_list(self, node: SyntaxTreeNode) -> str:
        return self._list(node, "list", "")

    def _b_ordered_list(self, node: SyntaxTreeNode) -> str:
        start = int(node.attrs.get("start", 1) or 1)
        return self._list(node, "enum", f"start: {start}, " if start != 1 else "")

    def _list(self, node: SyntaxTreeNode, func: str, extra: str) -> str:
        tight = all(
            p.hidden for item in node.children for p in item.children if p.type == "paragraph"
        )
        items = []
        for item in node.children:
            inner = "\n\n".join(b for b in self._blocks(item.children) if b)
            items.append(f"  [{inner}],")
        tight_arg = "" if tight else "tight: false, "
        return f"#{func}({extra}{tight_arg}\n" + "\n".join(items) + "\n)"

    def _b_fence(self, node: SyntaxTreeNode) -> str:
        lang = (node.info or "").strip().split()[0] if node.info else ""
        return self._raw_block(node.content, lang)

    def _b_code_block(self, node: SyntaxTreeNode) -> str:
        return self._raw_block(node.content, "")

    def _raw_block(self, content: str, lang: str) -> str:
        longest = max((len(m) for m in re.findall(r"`+", content)), default=0)
        fence = "`" * max(3, longest + 1)
        lang_id = re.sub(r"[^\w+#-]", "", lang)
        return f"{fence}{lang_id}\n{content.rstrip()}\n{fence}"

    def _b_html_block(self, node: SyntaxTreeNode) -> str:
        if node.content.strip() in _PAGEBREAK:
            return "#pagebreak()"
        if node.content.strip().startswith("<!--"):
            return ""
        self.ctx.warn(node, "το HTML δεν υποστηρίζεται στο PDF και αγνοήθηκε")
        return ""

    def _b_math_block(self, node: SyntaxTreeNode) -> str:
        return self._math(node.content, block=True)

    def _b_math_block_label(self, node: SyntaxTreeNode) -> str:
        label = str(node.info).strip()
        self.ctx.labels.add(label)
        return self._math(node.content, block=True) + " " + _label(label)

    def _b_footnote_block(self, node: SyntaxTreeNode) -> str:
        return ""

    # -- tables ------------------------------------------------------------
    def _table_caption(self, para: SyntaxTreeNode, text: str) -> tuple[str, str | None]:
        inline = para.children[0]
        children = list(inline.children)
        label = None
        if children and children[0].type == "text":
            children[0] = _TextNode(_TABLE_CAPTION_RE.sub("", children[0].content, count=1))
        if children and children[-1].type == "text":
            m = _HEADING_ATTRS_RE.search(children[-1].content)
            if m:
                label, _, _ = _parse_attr_string(m.group(1))
                children[-1] = _TextNode(children[-1].content[: m.start()])
        if label:
            self.ctx.labels.add(label)
        return self._inlines(children, QuoteState(self.ctx.lang)).strip(), label

    def _table(self, node: SyntaxTreeNode, caption: str | None, label: str | None) -> str:
        header: list[str] = []
        rows: list[list[str]] = []
        aligns: list[str] = []
        for section in node.children:
            for tr in section.children:
                cells = []
                for cell in tr.children:
                    content = self._inlines(
                        cell.children[0].children if cell.children else [],
                        QuoteState(self.ctx.lang),
                    )
                    cells.append(f"[{content.strip()}]")
                    if section.type == "thead":
                        style = str(cell.attrs.get("style", ""))
                        m = re.search(r"text-align:(\w+)", style)
                        aligns.append(m.group(1) if m else "auto")
                if section.type == "thead":
                    header = cells
                else:
                    rows.append(cells)
        ncols = max(len(header), *(len(r) for r in rows)) if rows else len(header)
        align = ", ".join(aligns) if any(a != "auto" for a in aligns) else ""
        lines = ["table(", f"  columns: {ncols},"]
        if align:
            lines.append(f"  align: ({align},),")
        if header:
            lines.append("  table.header(" + ", ".join(header) + "),")
        for r in rows:
            lines.append("  " + ", ".join(r) + ",")
        lines.append(")")
        table = "\n".join(lines)
        if caption is None:
            return "#" + table
        out = f"#figure(\n{table},\n  caption: [{caption}],\n)"
        return out + (" " + _label(label) if label else "")

    # -- figures -----------------------------------------------------------
    def _image_path(self, src: str) -> str:
        if re.match(r"^[a-z]+://", src):
            raise ValueError(src)
        p = PurePosixPath(src.replace("\\", "/"))
        return str(p if p.is_absolute() else self.ctx.base / p)

    def _image_call(self, node: SyntaxTreeNode, extra: dict[str, str] | None = None) -> str | None:
        src = str(node.attrs.get("src", ""))
        try:
            path = self._image_path(src)
        except ValueError:
            self.ctx.warn(node, f"οι εικόνες από το διαδίκτυο δεν υποστηρίζονται: {src}")
            return None
        args = [string(path)]
        width = (extra or {}).get("width") or str(node.attrs.get("width") or "")
        if width:
            try:
                args.append(f"width: {_length(str(width))}")
            except ValueError as exc:
                self.ctx.warn(node, str(exc))
        alt = "".join(c.content for c in node.children if c.type == "text")
        if alt:
            args.append(f"alt: {string(alt)}")
        return "image(" + ", ".join(args) + ")"

    def _figure(
        self,
        node: SyntaxTreeNode,
        ident: str | None = None,
        extra: dict[str, str] | None = None,
    ) -> str:
        call = self._image_call(node, extra)
        if call is None:
            return ""
        caption = self._inlines(node.children, QuoteState(self.ctx.lang)).strip()
        ident = ident or (str(node.attrs["id"]) if node.attrs.get("id") else None)
        label = ""
        if ident:
            label = " " + _label(str(ident))
            self.ctx.labels.add(str(ident))
        if caption:
            return f"#figure(\n  {call},\n  caption: [{caption}],\n){label}"
        return f"#figure({call}){label}"

    # -- math --------------------------------------------------------------
    def _math(self, content: str, block: bool) -> str:
        content = content.strip()
        if self.ctx.math == "typst":
            return f"$ {content} $" if block else f"${content}$"
        func = "mitex" if block else "mi"
        return f"#{func}({string(content)})"

    # -- inlines -----------------------------------------------------------
    def _inlines(
        self, nodes: Iterable[SyntaxTreeNode], state: QuoteState, line_start: bool = False
    ) -> str:
        out: list[str] = []
        pending_text: list[str] = []
        first = line_start

        def flush() -> None:
            nonlocal first
            if pending_text:
                out.append(self._text("".join(pending_text), state, first))
                pending_text.clear()
                first = False

        for node in nodes:
            if node.type == "text":
                pending_text.append(node.content)
                continue
            flush()
            first = False
            out.append(self._inline(node, state))
        flush()
        return "".join(out)

    def _text(self, text: str, state: QuoteState, line_start: bool) -> str:
        """Typography + citations + escaping for a merged text run."""
        pieces: list[str] = []
        pos = 0
        for m in _BRACKET_CITE_RE.finditer(text):
            pieces.append(self._plain(text[pos : m.start()], state, line_start and pos == 0))
            pieces.append(self._bracket_cite(m.group(1)))
            state.prev_char = "]"
            pos = m.end()
        pieces.append(self._plain(text[pos:], state, line_start and pos == 0))
        return "".join(pieces)

    def _plain(self, text: str, state: QuoteState, line_start: bool) -> str:
        pieces: list[str] = []
        pos = 0
        for m in _BARE_CITE_RE.finditer(text):
            key = m.group(1).rstrip(".:")
            end = m.start() + 1 + len(key)
            pieces.append(escape(typeset(text[pos : m.start()], state), line_start and pos == 0))
            pieces.append(self._bare_ref(key))
            state.prev_char = "x"
            pos = end
        pieces.append(escape(typeset(text[pos:], state), line_start and pos == 0))
        return "".join(pieces)

    def _bare_ref(self, key: str) -> str:
        if key.startswith(_REF_PREFIXES):
            return f"#ref({_label(key)})"
        return f'#cite({_label(key)}, form: "prose")'

    def _bracket_cite(self, inner: str) -> str:
        out = []
        for item in inner.split(";"):
            m = _CITE_ITEM_RE.match(item)
            if not m:
                continue
            key = m.group("key")
            args = [_label(key)]
            loc = m.group("loc")
            if loc:
                args.append(f"supplement: [{escape(typeset(loc, QuoteState(self.ctx.lang)))}]")
            is_ref = key.startswith(_REF_PREFIXES)
            if m.group("neg") and not is_ref:
                args.append('form: "year"')
            prefix = m.group("pre")
            if prefix:
                out.append(escape(typeset(prefix, QuoteState(self.ctx.lang))) + " ")
            if is_ref:
                # [-@tbl:x] → number only, so Greek authors can inflect the
                # noun themselves: «στον Πίνακα [-@tbl:x]».
                sup = ", supplement: none" if m.group("neg") else ""
                out.append(f"#ref({args[0]}{sup})")
            else:
                out.append("#cite(" + ", ".join(args) + ")")
        return "".join(out)

    def _inline(self, node: SyntaxTreeNode, state: QuoteState) -> str:
        t = node.type
        if t == "softbreak":
            state.prev_char = " "
            return " "
        if t == "hardbreak":
            state.prev_char = " "
            return "#linebreak()"
        if t == "em":
            return f"#emph[{self._inlines(node.children, state)}]"
        if t == "strong":
            return f"#strong[{self._inlines(node.children, state)}]"
        if t == "s":
            return f"#strike[{self._inlines(node.children, state)}]"
        if t == "code_inline":
            state.prev_char = "x"
            return f"#raw({string(node.content)})"
        if t == "math_inline" or t == "math_inline_double":
            state.prev_char = "x"
            return self._math(node.content, block=t == "math_inline_double")
        if t == "link":
            href = str(node.attrs.get("href", ""))
            body = self._inlines(node.children, state)
            if href.startswith("#"):
                return f"#link({_label(href[1:])})[{body}]"
            return f"#link({string(href)})[{body}]"
        if t == "image":
            call = self._image_call(node)
            return f"#box({call})" if call else ""
        if t == "footnote_ref":
            body = self.ctx.footnotes.get(int(node.meta.get("id", -1)), "")
            state.prev_char = "x"
            return f"#footnote[{body}]"
        if t == "footnote_anchor":
            return ""
        if t == "html_inline":
            if re.fullmatch(r"<br\s*/?>", node.content.strip(), re.IGNORECASE):
                return "#linebreak()"
            return ""
        self.ctx.warn(node, f"αγνοήθηκε στοιχείο '{t}'")
        return ""


def _TextNode(content: str) -> SyntaxTreeNode:
    """A text node (used after trimming ``{#id}`` from headings and captions)."""
    return SyntaxTreeNode([Token("text", "", 0, content=content)], create_root=True).children[0]


def _length(v: str) -> str:
    v = v.strip()
    if re.fullmatch(r"\d+(\.\d+)?%", v):
        return v
    if re.fullmatch(r"\d+(\.\d+)?(mm|cm|in|pt|em)", v):
        return v
    if re.fullmatch(r"\d+(\.\d+)?", v):
        return v + "pt"
    raise ValueError(f"μη έγκυρο πλάτος εικόνας: {v}")


def markdown_to_typst(
    md_text: str,
    lang: str = "el",
    math: str = "latex",
    source: str = "<string>",
    base: PurePosixPath | str = "/",
    unnumbered: bool = False,
) -> tuple[str, list[Diagnostic]]:
    """Convert one Markdown document to Typst markup.

    Returns the markup and any diagnostics (ignored constructs, …).
    """
    ctx = Context(
        lang=lang, math=math, source=source, base=PurePosixPath(base), unnumbered=unnumbered
    )
    typst = TypstWriter(ctx).convert(md_text)
    return typst, ctx.diagnostics


def relative_base(file: Path, root: Path) -> PurePosixPath:
    """Directory of ``file`` as a root-relative POSIX path for Typst."""
    rel = file.resolve().parent.relative_to(root.resolve())
    return PurePosixPath("/") / PurePosixPath(rel.as_posix())
