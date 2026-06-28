# -*- coding: utf-8 -*-
"""
Core build pipeline. Given a BookConfig, this discovers the parts/*.md
files, lays out the whole book with ReportLab, and runs the two-pass
build automatically (no more manually copy-pasting PAGES_FOUND back into
a second command — `greekbook build` does both passes itself).
"""
from pathlib import Path
from typing import Dict, List, Tuple

import pdfplumber
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    BaseDocTemplate, Frame, NextPageTemplate, PageBreak, PageTemplate,
    Paragraph, Spacer,
)

from .config import BookConfig, PartSource
from .flowables import OrnamentRule, PageRecorder, TocEntry
from .hyphenators import get_hyphenator
from .md_parser import parse_markdown_to_flowables
from .styles import MARGIN_BOTTOM, MARGIN_INNER, MARGIN_OUTER, MARGIN_TOP, build_style_kit
from .themes import get_theme

GREEK_CAPS = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
_ROMAN_TABLE = [
    (1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"),
    (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I"),
]


def int_to_roman(n: int) -> str:
    result = []
    for value, symbol in _ROMAN_TABLE:
        while n >= value:
            result.append(symbol)
            n -= value
    return "".join(result)


def default_part_label(language: str, idx: int) -> str:
    if language == "el":
        if idx < len(GREEK_CAPS):
            return f"ΜΕΡΟΣ {GREEK_CAPS[idx]}"
        return f"ΜΕΡΟΣ {idx + 1}"
    return f"PART {int_to_roman(idx + 1)}"


def build_book(config: BookConfig, quiet: bool = False) -> Path:
    theme_cls = get_theme(config.theme)
    hyphenator = get_hyphenator(config.language)
    page_w, page_h = config.page_size_pt
    kit = build_style_kit(theme_cls, page_w, page_h, hyphenator)

    parts = config.discover_parts()
    part_info = []
    for idx, part in enumerate(parts):
        label = part.label or default_part_label(config.language, idx)
        part_info.append({"label": label, "roman": int_to_roman(idx + 1), "page": None})

    output_path = config.output_path
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # ---------------- Pass 1: discovery ----------------
    if not quiet:
        print("greekbook: πάσο 1/2 — ανακάλυψη σελιδοποίησης…", flush=True)
    _render_pdf(config, kit, parts, part_info, label_ranges={}, output_path=output_path,
                quiet=quiet, pass_label="πάσο 1/2")
    pages_found, label_ranges = _discover_pagination(output_path, part_info)
    for info, page_num in zip(part_info, pages_found):
        info["page"] = page_num

    # ---------------- Pass 2: final, with real TOC numbers + running heads ----------------
    if not quiet:
        print("greekbook: πάσο 2/2 — τελικό PDF…", flush=True)
    _render_pdf(config, kit, parts, part_info, label_ranges=label_ranges, output_path=output_path,
                quiet=quiet, pass_label="πάσο 2/2")

    if not quiet:
        print(f"greekbook: ✓ PDF έτοιμο → {output_path}")
    return output_path


def _render_pdf(config: BookConfig, kit, parts: List[PartSource], part_info: List[dict],
                 label_ranges: Dict[str, Tuple[int, int]], output_path: Path,
                 quiet: bool = False, pass_label: str = ""):
    recorder_registry: Dict[str, set] = {}

    def label_for_abs_page(abs_page):
        for label, (start, end) in label_ranges.items():
            if start <= abs_page <= end:
                return label
        return ""

    doc = BaseDocTemplate(
        str(output_path), pagesize=(kit.page_w, kit.page_h),
        title=config.title, author=config.author,
        topMargin=MARGIN_TOP, bottomMargin=MARGIN_BOTTOM,
    )

    frame_right = Frame(MARGIN_INNER, MARGIN_BOTTOM, kit.content_width, kit.content_height,
                         id="right", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame_left = Frame(MARGIN_OUTER, MARGIN_BOTTOM, kit.content_width, kit.content_height,
                        id="left", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    frame_full_right = Frame(MARGIN_INNER, MARGIN_BOTTOM, kit.content_width, kit.content_height,
                              id="full_right", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)

    def draw_cover_background(c, doc_):
        c.saveState()
        # ── Cover image (if provided) ──────────────────────────────────────
        cover_img_path = None
        if config.cover_image:
            p = Path(config.cover_image)
            if not p.is_absolute():
                p = config.base_dir / p
            if p.exists():
                cover_img_path = str(p)
        if cover_img_path:
            # Fill page with image, centered/cropped to fill
            c.drawImage(cover_img_path, 0, 0,
                        width=kit.page_w, height=kit.page_h,
                        preserveAspectRatio=False, mask="auto")
            # Subtle dark overlay at bottom for text legibility
            from reportlab.lib.colors import Color
            overlay = Color(0, 0, 0, alpha=0.45)
            c.setFillColor(overlay)
            c.rect(0, 0, kit.page_w, kit.page_h * 0.42, stroke=0, fill=1)
        else:
            # ── Default generated cover ────────────────────────────────────
            c.setFillColor(kit.colors["cover_bg"])
            c.rect(0, 0, kit.page_w, kit.page_h, stroke=0, fill=1)
            margin = 11 * mm
            c.setStrokeColor(kit.colors["cover_line"])
            c.setLineWidth(0.9)
            c.rect(margin, margin, kit.page_w - 2 * margin, kit.page_h - 2 * margin, stroke=1, fill=0)
            inner = margin + 3.2 * mm
            c.setLineWidth(0.5)
            c.rect(inner, inner, kit.page_w - 2 * inner, kit.page_h - 2 * inner, stroke=1, fill=0)
            for cx, cy in [(margin, margin), (kit.page_w - margin, margin),
                           (margin, kit.page_h - margin), (kit.page_w - margin, kit.page_h - margin)]:
                c.setFillColor(kit.colors["cover_line"])
                c.saveState()
                c.translate(cx, cy)
                c.rotate(45)
                c.rect(-2.2, -2.2, 4.4, 4.4, stroke=0, fill=1)
                c.restoreState()
        c.restoreState()

    def draw_paper_background(c, doc_):
        c.saveState()
        c.setFillColor(kit.colors["paper"])
        c.rect(0, 0, kit.page_w, kit.page_h, stroke=0, fill=1)
        c.restoreState()

    def make_content_page_drawer():
        def _draw(c, doc_):
            c.saveState()
            c.setFillColor(kit.colors["paper"])
            c.rect(0, 0, kit.page_w, kit.page_h, stroke=0, fill=1)
            c.restoreState()

            page_no = c.getPageNumber()
            if not quiet:
                print(f"\rgreekbook: {pass_label} — σελίδα {page_no}…", end="", flush=True)
            unnumbered = recorder_registry.get("unnumbered", set())
            is_odd = (page_no % 2 == 1)

            c.saveState()
            c.setFont(kit.fonts["italic"], 8)
            c.setFillColor(kit.colors["muted"])
            head_y = kit.page_h - MARGIN_TOP + 7 * mm
            label = label_for_abs_page(page_no)
            if page_no not in unnumbered:
                if is_odd:
                    text = label
                    x_center = MARGIN_INNER + kit.content_width / 2.0
                else:
                    text = config.title.upper()
                    x_center = MARGIN_OUTER + kit.content_width / 2.0
                c.drawCentredString(x_center, head_y, text)
                c.setStrokeColor(kit.colors["muted"])
                c.setLineWidth(0.4)
                if is_odd:
                    c.line(MARGIN_INNER, head_y - 3.2 * mm, MARGIN_INNER + kit.content_width, head_y - 3.2 * mm)
                else:
                    c.line(MARGIN_OUTER, head_y - 3.2 * mm, MARGIN_OUTER + kit.content_width, head_y - 3.2 * mm)
            c.restoreState()

            c.saveState()
            c.setFont(kit.fonts["regular"], 8.5)
            c.setFillColor(kit.colors["accent"])
            if page_no not in unnumbered:
                skipped_before = sum(1 for p in unnumbered if p < page_no)
                n = page_no - skipped_before
                text = str(n)
                if is_odd:
                    c.drawRightString(kit.page_w - MARGIN_OUTER, MARGIN_BOTTOM - 9 * mm, text)
                else:
                    c.drawString(MARGIN_OUTER, MARGIN_BOTTOM - 9 * mm, text)
            c.restoreState()
        return _draw

    templates = [
        PageTemplate(id="Cover", frames=[frame_full_right], onPage=draw_cover_background),
        PageTemplate(id="FrontMatter", frames=[frame_full_right], onPage=draw_paper_background),
        PageTemplate(id="PartTitleRight", frames=[frame_full_right], onPage=draw_paper_background),
        PageTemplate(id="Right", frames=[frame_right], onPage=make_content_page_drawer()),
        PageTemplate(id="Left", frames=[frame_left], onPage=make_content_page_drawer()),
    ]
    doc.addPageTemplates(templates)

    story = []

    # ---------- Front cover ----------
    story.append(PageRecorder(recorder_registry, "unnumbered"))
    story.append(Spacer(1, 58 * mm))
    story.append(Paragraph(config.title, kit.cover_title_style))
    if config.subtitle:
        story.append(Spacer(1, 7 * mm))
        story.append(Paragraph("• • •", ParagraphStyle(
            "CoverOrnament", fontName=kit.fonts["regular"], fontSize=12,
            leading=14, alignment=TA_CENTER, textColor=kit.colors["cover_line"],
        )))
        story.append(Spacer(1, 7 * mm))
        story.append(Paragraph(config.subtitle, kit.cover_subtitle_style))
    story.append(Spacer(1, 55 * mm))
    story.append(Paragraph(config.author, kit.cover_author_style))
    story.append(NextPageTemplate("FrontMatter"))
    story.append(PageBreak())

    # ---------- Title page ----------
    story.append(PageRecorder(recorder_registry, "unnumbered"))
    story.append(Spacer(1, 75 * mm))
    story.append(Paragraph(config.title, kit.title_page_title_style))
    story.append(Spacer(1, 7 * mm))
    if kit.use_ornaments:
        story.append(OrnamentRule(kit.content_width, kit.colors["accent"]))
    story.append(Spacer(1, 7 * mm))
    story.append(Paragraph(config.author, kit.title_page_author_style))
    story.append(NextPageTemplate("FrontMatter"))
    story.append(PageBreak())

    # ---------- Colophon ----------
    story.append(PageRecorder(recorder_registry, "unnumbered"))
    story.append(Spacer(1, 100 * mm))
    story.append(Paragraph(f"© {config.author}", kit.colophon_style))
    story.append(Spacer(1, 3 * mm))
    story.append(Paragraph("Όλα τα δικαιώματα διατηρούνται." if config.language == "el"
                            else "All rights reserved.", kit.colophon_style))
    story.append(NextPageTemplate("FrontMatter"))
    story.append(PageBreak())

    # ---------- Table of contents ----------
    story.append(PageRecorder(recorder_registry, "unnumbered"))
    story.append(Spacer(1, 28 * mm))
    story.append(Paragraph("Περιεχόμενα" if config.language == "el" else "Contents", kit.toc_title_style))
    if kit.use_ornaments:
        story.append(OrnamentRule(kit.content_width, kit.colors["accent"]))
    story.append(Spacer(1, 10 * mm))
    for info in part_info:
        page_str = str(info["page"]) if info["page"] else "—"
        story.append(TocEntry(
            info["label"], page_str, kit.content_width,
            kit.toc_label_font, kit.toc_page_font,
            kit.colors["ink"], kit.colors["muted"],
        ))
    story.append(NextPageTemplate("PartTitleRight"))
    story.append(PageBreak())

    # ---------- Parts ----------
    for idx, (part, info) in enumerate(zip(parts, part_info)):
        story.append(PageRecorder(recorder_registry, "unnumbered"))
        story.append(Spacer(1, 68 * mm))
        story.append(Paragraph(info["roman"], kit.part_number_style))
        if kit.use_ornaments:
            story.append(OrnamentRule(kit.content_width, kit.colors["accent"]))
        story.append(Spacer(1, 6 * mm))
        story.append(Paragraph(info["label"], kit.part_title_style))
        story.append(NextPageTemplate("Right"))
        story.append(PageBreak())

        story.extend(parse_markdown_to_flowables(part.body, kit, drop_cap_once=kit.use_drop_caps))

        if idx < len(parts) - 1:
            story.append(NextPageTemplate("PartTitleRight"))
            story.append(PageBreak())

    doc.build(story)
    if not quiet:
        print()


def _discover_pagination(output_path: Path, part_info: List[dict]):
    """Re-opens the just-built PDF and figures out, for each part: which
    displayed folio number its first content page shows, and which
    absolute page range it spans (for running heads). Mirrors how a part
    title page is recognised: its first line of extracted text is exactly
    the part's roman numeral (that's the only thing on that page above
    the fold)."""
    with pdfplumber.open(str(output_path)) as pdf:
        total_pages = len(pdf.pages)
        found_pages = []
        title_pages = []
        for i, page in enumerate(pdf.pages, start=1):
            text = (page.extract_text() or "").strip()
            first_line = text.split("\n")[0] if text else ""
            if any(first_line == info["roman"] for info in part_info):
                title_pages.append(i)
                found_pages.append(i + 1)

        displayed = []
        for abs_page in found_pages:
            p = pdf.pages[abs_page - 1]
            words = p.extract_words()
            displayed.append(max(words, key=lambda w: w["top"])["text"] if words else "?")

        label_ranges = {}
        for idx, start in enumerate(found_pages):
            if idx + 1 < len(title_pages):
                end = title_pages[idx + 1] - 1
            else:
                end = total_pages
            if idx < len(part_info):
                label_ranges[part_info[idx]["label"]] = (start, end)

    pages_found_ints = []
    for d in displayed:
        try:
            pages_found_ints.append(int(d))
        except (TypeError, ValueError):
            pages_found_ints.append(None)
    return pages_found_ints, label_ranges
