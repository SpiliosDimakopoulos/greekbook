# -*- coding: utf-8 -*-
"""
Converts the small greekbook markdown dialect into a list of ReportLab
flowables for one part of the book.

Supported syntax (documented in the main README):
- Blank line = new paragraph.
- `_word_` -> italics, `**word**` -> bold.
- `---` alone on a line -> decorative scene-break ornament.
- `*[Text]*` alone on a line, right after a `---` -> small italic scene
  subtitle (e.g. *[Ο εργάτης, γέρος πια]*).
- Straight double quotes `"..."` -> typographic guillemets «...» (el) or
  curly quotes (other languages use ReportLab's own rendering as-is).
- The very first paragraph of the whole book gets a decorative drop cap,
  if the active theme enables them.
"""
import re

from reportlab.platypus import Paragraph, Spacer

from .flowables import DropCapParagraph, OrnamentRule

SECTION_TAG_RE = re.compile(r"^\*\[(.+?)\]\*$")


def smart_quotes(text: str) -> str:
    """Convert straight double quotes to Greek-style guillemets «»,
    alternating opening/closing based on position."""
    out = []
    open_next = True
    for ch in text:
        if ch == '"':
            out.append("«" if open_next else "»")
            open_next = not open_next
        else:
            out.append(ch)
    return "".join(out)


def inline_markup(text: str) -> str:
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(r"_(.+?)_", r"<i>\1</i>", text)
    text = text.replace("--", "—")
    text = smart_quotes(text)
    text = text.replace("'", "\u2019")
    return text


def parse_markdown_to_flowables(md_text: str, kit, drop_cap_once: bool = False):
    lines = md_text.split("\n")
    flowables = []
    paragraph_buffer = []
    drop_cap_pending = [False]  # drop caps disabled
    first_para_of_block = [True]

    def flush_paragraph():
        if not paragraph_buffer:
            return
        joined = " ".join(paragraph_buffer).strip()
        paragraph_buffer.clear()
        if not joined:
            return
        marked = inline_markup(joined)

        if drop_cap_pending[0]:
            plain = re.sub(r"<[^>]+>", "", marked)
            m = re.match(r"([«\"'\u2018\u2019]?)(\w)", plain, re.UNICODE)
            if m and len(plain) > 40:
                prefix_punct = m.group(1)
                cap_letter = m.group(2)
                search_str = prefix_punct + cap_letter
                idx = marked.find(search_str)
                if idx != -1:
                    rest = marked[idx + len(search_str):]
                    cap_display = prefix_punct + cap_letter
                    flowables.append(DropCapParagraph(
                        cap_display, rest, kit.content_width, kit.body_style_dropcap,
                        cap_font=kit.fonts["bold"], cap_color=kit.colors["accent"],
                        cap_size=38, lines_high=3,
                    ))
                    flowables.append(Spacer(1, kit.body_style.spaceAfter))
                    drop_cap_pending[0] = False
                    first_para_of_block[0] = False
                    return

        if first_para_of_block[0]:
            style = kit.body_style_noindent
            first_para_of_block[0] = False
        else:
            style = kit.body_style
        flowables.append(Paragraph(marked, style))

    i, n = 0, len(lines)
    while i < n:
        stripped = lines[i].strip()

        if stripped == "":
            flush_paragraph()
            i += 1
            continue

        if stripped == "---":
            flush_paragraph()
            flowables.append(Spacer(1, 8))
            flowables.append(OrnamentRule(kit.content_width, kit.colors["accent"]))
            flowables.append(Spacer(1, 4))
            i += 1
            continue

        m = SECTION_TAG_RE.match(stripped)
        if m:
            flush_paragraph()
            flowables.append(Paragraph(inline_markup(m.group(1)), kit.section_tag_style))
            first_para_of_block[0] = True
            i += 1
            continue

        paragraph_buffer.append(stripped)
        i += 1

    flush_paragraph()
    return flowables
