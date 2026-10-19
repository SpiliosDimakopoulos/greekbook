"""``greekbook import``: turn a Word document into a greekbook project.

Most theses start life in Word. This converts a ``.docx`` into Markdown
chapters (split at Heading 1), keeping what matters for a thesis: headings,
bold/italic, footnotes, bulleted and numbered lists, tables, images and links.
Styles are recognised by their built-in identity, so Greek Word
("Επικεφαλίδα 1") and English Word ("Heading 1") both work.

Requires the optional dependency: ``pip install "greekbook[docx]"``.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"
A = "{http://schemas.openxmlformats.org/drawingml/2006/main}"

_HEADING_RE = re.compile(r"(?:heading|επικεφαλίδα|titre|überschrift)\s*(\d)", re.IGNORECASE)
_MD_SPECIAL_RE = re.compile(r"([\\`*_\[\]$<>])")


class ImportError_(Exception):  # trailing "_": do not shadow the builtin ImportError
    """The document could not be imported."""


@dataclass
class _Chapter:
    title: str
    lines: list[str] = field(default_factory=list)


def _escape(text: str) -> str:
    return _MD_SPECIAL_RE.sub(r"\\\1", text)


_TRANSLIT = dict(
    zip(
        "αβγδεζηθικλμνξοπρσςτυφχψω",
        [
            "a",
            "v",
            "g",
            "d",
            "e",
            "z",
            "i",
            "th",
            "i",
            "k",
            "l",
            "m",
            "n",
            "x",
            "o",
            "p",
            "r",
            "s",
            "s",
            "t",
            "y",
            "f",
            "ch",
            "ps",
            "o",
        ],
        strict=True,
    )
)


def _slug(text: str) -> str:
    """ASCII file-name slug; Greek is transliterated (Εισαγωγή → eisagogi)."""
    plain = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c)
    )
    latin = "".join(_TRANSLIT.get(c, c) for c in plain)
    latin = latin.replace("oy", "ou").replace("ey", "ev").replace("ay", "av")
    return re.sub(r"[^a-z0-9]+", "-", latin).strip("-")[:40] or "chapter"


class _Converter:
    def __init__(self, document: Any, images_dir: Path) -> None:
        self.doc = document
        self.images_dir = images_dir
        self.footnotes = self._read_footnotes()
        self.numbering = self._read_numbering()
        self.style_names = {s.style_id: s.name or "" for s in document.styles}
        self.image_count = 0
        self.warnings: list[str] = []

    # -- document parts ----------------------------------------------------
    def _read_footnotes(self) -> dict[str, str]:
        notes: dict[str, str] = {}
        for rel in self.doc.part.rels.values():
            if rel.reltype.endswith("/footnotes"):
                from lxml import etree

                root = etree.fromstring(rel.target_part.blob)
                for fn in root.iter(f"{W}footnote"):
                    fid = fn.get(f"{W}id")
                    text = "".join(self._runs_text(p) for p in fn.iter(f"{W}p")).strip()
                    if fid is not None and text:
                        notes[fid] = text
        return notes

    def _read_numbering(self) -> dict[tuple[str, str], str]:
        """(numId, level) → numFmt ("bullet", "decimal", …)."""
        formats: dict[tuple[str, str], str] = {}
        try:
            numbering = self.doc.part.numbering_part.element
        except (KeyError, NotImplementedError, AttributeError):
            return formats
        abstract: dict[str, dict[str, str]] = {}
        for an in numbering.iter(f"{W}abstractNum"):
            levels = {}
            for lvl in an.iter(f"{W}lvl"):
                fmt = lvl.find(f"{W}numFmt")
                levels[lvl.get(f"{W}ilvl")] = fmt.get(f"{W}val") if fmt is not None else "bullet"
            abstract[an.get(f"{W}abstractNumId")] = levels
        for num in numbering.iter(f"{W}num"):
            ref = num.find(f"{W}abstractNumId")
            if ref is not None:
                for lvl, fmt in abstract.get(ref.get(f"{W}val"), {}).items():
                    formats[(num.get(f"{W}numId"), lvl)] = fmt
        return formats

    # -- inline content ----------------------------------------------------
    @staticmethod
    def _runs_text(p: Any) -> str:
        return "".join(t.text or "" for t in p.iter(f"{W}t"))

    def _run_markdown(self, run: Any) -> str:
        rpr = run.find(f"{W}rPr")

        def on(tag: str) -> bool:
            el = rpr.find(f"{W}{tag}") if rpr is not None else None
            return el is not None and el.get(f"{W}val") not in ("0", "false")

        parts: list[str] = []
        for child in run:
            if child.tag == f"{W}t":
                parts.append(_escape(child.text or ""))
            elif child.tag == f"{W}tab":
                parts.append(" ")
            elif child.tag in (f"{W}br", f"{W}cr"):
                parts.append("\\\n" if child.get(f"{W}type") != "page" else "\n\n\\newpage\n\n")
            elif child.tag == f"{W}footnoteReference":
                note = self.footnotes.get(child.get(f"{W}id") or "", "")
                if note:
                    parts.append("^[" + _escape(note) + "]")
            elif child.tag == f"{W}drawing":
                parts.append(self._image(child))
        text = "".join(parts)
        if not text.strip() or text.startswith("^["):
            return text
        lead = text[: len(text) - len(text.lstrip())]
        trail = text[len(text.rstrip()) :]
        core = text.strip()
        if on("b"):
            core = f"**{core}**"
        if on("i"):
            core = f"*{core}*"
        return lead + core + trail

    def _image(self, drawing: Any) -> str:
        blip = next(drawing.iter(f"{A}blip"), None)
        rid = blip.get(f"{R}embed") if blip is not None else None
        if not rid or rid not in self.doc.part.rels:
            return ""
        part = self.doc.part.rels[rid].target_part
        ext = Path(part.partname).suffix or ".png"
        self.image_count += 1
        name = f"image{self.image_count:02d}{ext}"
        self.images_dir.mkdir(parents=True, exist_ok=True)
        (self.images_dir / name).write_bytes(part.blob)
        return f"![](../{self.images_dir.name}/{name})"

    def _paragraph_markdown(self, p: Any) -> str:
        out: list[str] = []
        for child in p:
            if child.tag == f"{W}r":
                out.append(self._run_markdown(child))
            elif child.tag == f"{W}hyperlink":
                text = "".join(self._run_markdown(r) for r in child.iter(f"{W}r"))
                rid = child.get(f"{R}id")
                if rid and rid in self.doc.part.rels:
                    out.append(f"[{text}]({self.doc.part.rels[rid].target_ref})")
                else:
                    out.append(text)
        md = "".join(out)
        return re.sub(r"\*\*\*\*|(?<!\*)\*\*(?!\*)(?=\s*\*\*)", "", md).strip()

    # -- blocks ------------------------------------------------------------
    def _style(self, p: Any) -> tuple[str, int]:
        """("heading", level) / ("title", 0) / ("list:<fmt>", level) / ("p", 0)."""
        ppr = p.find(f"{W}pPr")
        style_id = ""
        if ppr is not None:
            ps = ppr.find(f"{W}pStyle")
            style_id = ps.get(f"{W}val") if ps is not None else ""
            numpr = ppr.find(f"{W}numPr")
            outline = ppr.find(f"{W}outlineLvl")
        else:
            numpr = outline = None
        name = self.style_names.get(style_id, style_id)
        if name.lower() == "title" or style_id.lower() == "title":
            return "title", 0
        m = _HEADING_RE.search(name) or _HEADING_RE.search(style_id)
        if m:
            return "heading", int(m.group(1))
        if outline is not None and outline.get(f"{W}val", "9").isdigit():
            level = int(outline.get(f"{W}val")) + 1
            if level <= 6:
                return "heading", level
        if numpr is not None:
            num_id = numpr.find(f"{W}numId")
            ilvl = numpr.find(f"{W}ilvl")
            key = (num_id.get(f"{W}val") if num_id is not None else "0",
                   ilvl.get(f"{W}val") if ilvl is not None else "0")  # fmt: skip
            return f"list:{self.numbering.get(key, 'bullet')}", int(key[1])
        if "list" in name.lower():
            return ("list:decimal" if "number" in name.lower() else "list:bullet"), 0
        return "p", 0

    def _table(self, tbl: Any) -> list[str]:
        rows = []
        for tr in tbl.iter(f"{W}tr"):
            cells = []
            for tc in tr.iter(f"{W}tc"):
                text = " ".join(self._paragraph_markdown(p) for p in tc.iter(f"{W}p")).strip()
                cells.append(text.replace("|", "\\|").replace("\n", " ") or " ")
            rows.append(cells)
        if not rows:
            return []
        width = max(len(r) for r in rows)
        rows = [r + [" "] * (width - len(r)) for r in rows]
        lines = ["| " + " | ".join(rows[0]) + " |", "|" + "---|" * width]
        lines += ["| " + " | ".join(r) + " |" for r in rows[1:]]
        return [*lines, ""]

    def convert(self) -> tuple[str, list[_Chapter]]:
        title = ""
        chapters: list[_Chapter] = [_Chapter("")]
        prev_list = False
        for block in self.doc.element.body:
            if block.tag == f"{W}tbl":
                if prev_list or (chapters[-1].lines and chapters[-1].lines[-1]):
                    chapters[-1].lines.append("")
                chapters[-1].lines.extend(self._table(block))
                prev_list = False
                continue
            if block.tag != f"{W}p":
                continue
            kind, level = self._style(block)
            text = self._paragraph_markdown(block)
            if not text:
                if prev_list:
                    chapters[-1].lines.append("")
                prev_list = False
                continue
            if kind == "title":
                title = title or re.sub(r"[*\\]", "", text)
                continue
            if kind == "heading" and level == 1:
                chapters.append(_Chapter(re.sub(r"[*\\]", "", text)))
                chapters[-1].lines += [f"# {text}", ""]
                prev_list = False
                continue
            if kind == "heading":
                chapters[-1].lines += ["#" * min(level, 6) + " " + text, ""]
                prev_list = False
                continue
            if kind.startswith("list:"):
                marker = "-" if kind.endswith(("bullet", "none")) else "1."
                chapters[-1].lines.append("    " * level + f"{marker} {text}")
                prev_list = True
                continue
            if prev_list:
                chapters[-1].lines.append("")
            prev_list = False
            chapters[-1].lines += [text, ""]
        if not chapters[0].lines:
            chapters.pop(0)
        elif len(chapters) > 1:  # text before the first heading becomes a preface
            chapters[0].title = "Πρόλογος"
            chapters[0].lines = ["# Πρόλογος {-}", "", *chapters[0].lines]
        return title, chapters


def import_docx(docx_path: Path, target: Path, template: str = "thesis") -> list[str]:
    """Create a greekbook project in ``target`` from ``docx_path``.

    Returns warnings for the user.
    """
    try:
        import docx
    except ModuleNotFoundError as exc:  # pragma: no cover - depends on extras
        raise ImportError_('Χρειάζεται το python-docx: pip install "greekbook[docx]"') from exc
    if target.exists() and any(target.iterdir()):
        raise ImportError_(f"Ο φάκελος {target} υπάρχει ήδη και δεν είναι άδειος.")
    try:
        document = docx.Document(str(docx_path))
    except Exception as exc:
        raise ImportError_(f"Δεν είναι έγκυρο αρχείο Word (.docx): {docx_path}") from exc

    converter = _Converter(document, target / "figures")
    title, chapters = converter.convert()
    if not chapters:
        raise ImportError_("Το έγγραφο δεν περιέχει κείμενο.")
    chapters_dir = target / "chapters"
    chapters_dir.mkdir(parents=True, exist_ok=True)
    for idx, chapter in enumerate(chapters, 1):
        name = f"{idx:02d}-{_slug(chapter.title) if chapter.title else 'keimeno'}.md"
        body = "\n".join(chapter.lines).strip() + "\n"
        (chapters_dir / name).write_text(re.sub(r"\n{3,}", "\n\n", body), encoding="utf-8")

    props = document.core_properties
    config = {
        "title": title or props.title or docx_path.stem,
        "author": props.author or "Συγγραφέας",
        "template": template,
        "output": f"{_slug(docx_path.stem)}.pdf",
    }
    (target / "book.yaml").write_text(
        yaml.safe_dump(config, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    warnings = list(converter.warnings)
    if len(chapters) == 1:
        warnings.append(
            "Δεν βρέθηκαν επικεφαλίδες «Επικεφαλίδα 1»: όλο το κείμενο μπήκε σε ένα κεφάλαιο."
        )
    return warnings
