# -*- coding: utf-8 -*-
"""
Builds the full set of ParagraphStyles, page geometry, and theme-bound
colors/fonts needed to lay out a book. Everything that build_book.py used
to keep as module-level globals lives here instead, bundled into a single
StyleKit object so a build never leaks state between runs (important once
this is a library that might build more than one book in one process).
"""
from dataclasses import dataclass
from typing import Any, Dict

from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm

MARGIN_OUTER = 17 * mm
MARGIN_INNER = 22 * mm
MARGIN_TOP = 22 * mm
MARGIN_BOTTOM = 20 * mm


@dataclass
class StyleKit:
    page_w: float
    page_h: float
    content_width: float
    content_height: float
    fonts: Dict[str, str]
    colors: Dict[str, Any]
    body_style: ParagraphStyle
    body_style_noindent: ParagraphStyle
    body_style_dropcap: ParagraphStyle
    section_tag_style: ParagraphStyle
    part_title_style: ParagraphStyle
    part_number_style: ParagraphStyle
    toc_title_style: ParagraphStyle
    toc_label_font: tuple
    toc_page_font: tuple
    colophon_style: ParagraphStyle
    cover_title_style: ParagraphStyle
    cover_subtitle_style: ParagraphStyle
    cover_author_style: ParagraphStyle
    title_page_title_style: ParagraphStyle
    title_page_author_style: ParagraphStyle
    use_drop_caps: bool
    use_ornaments: bool


def build_style_kit(theme_cls, page_w: float, page_h: float, hyphenator) -> StyleKit:
    fonts = theme_cls.register_fonts()
    colors = {key: theme_cls.color(key) for key in theme_cls.palette}

    content_width = page_w - MARGIN_INNER - MARGIN_OUTER
    content_height = page_h - MARGIN_TOP - MARGIN_BOTTOM

    body_style = ParagraphStyle(
        "Body", fontName=fonts["regular"], fontSize=theme_cls.body_font_size,
        leading=theme_cls.body_leading, alignment=TA_JUSTIFY,
        spaceAfter=7.5, textColor=colors["ink"], firstLineIndent=15,
        hyphenationLang=hyphenator.iterate, hyphenationMinWordLength=7,
        allowWidows=0, allowOrphans=0,
    )
    body_style_noindent = ParagraphStyle(
        "BodyNoIndent", parent=body_style, firstLineIndent=0,
    )
    body_style_dropcap = ParagraphStyle(
        "BodyDropCap", parent=body_style, firstLineIndent=0,
    )
    section_tag_style = ParagraphStyle(
        "SectionTag", fontName=fonts["italic"], fontSize=9.2, leading=13,
        alignment=TA_CENTER, textColor=colors["muted"], spaceBefore=2, spaceAfter=13,
    )
    part_title_style = ParagraphStyle(
        "PartTitle", fontName=fonts["bold"], fontSize=27, leading=33,
        alignment=TA_CENTER, textColor=colors["ink"], spaceBefore=0, spaceAfter=4,
    )
    part_number_style = ParagraphStyle(
        "PartNumber", fontName=fonts["regular"], fontSize=11.5, leading=14,
        alignment=TA_CENTER, textColor=colors["accent"], spaceBefore=0, spaceAfter=8,
    )
    toc_title_style = ParagraphStyle(
        "TocTitle", fontName=fonts["bold"], fontSize=17, leading=21,
        alignment=TA_CENTER, textColor=colors["ink"], spaceAfter=20,
    )
    toc_label_font = (fonts["regular"], 11.5)
    toc_page_font = (fonts["regular"], 11.5)
    colophon_style = ParagraphStyle(
        "Colophon", fontName=fonts["regular"], fontSize=8.5, leading=13,
        alignment=TA_CENTER, textColor=colors["muted"],
    )
    cover_title_style = ParagraphStyle(
        "CoverTitle", fontName=fonts["bold"], fontSize=33, leading=40,
        alignment=TA_CENTER, textColor=colors["cover_fg"], spaceAfter=0,
    )
    cover_subtitle_style = ParagraphStyle(
        "CoverSubtitle", fontName=fonts["italic"], fontSize=10.5, leading=14,
        alignment=TA_CENTER, textColor=colors["cover_line"], spaceAfter=0,
    )
    cover_author_style = ParagraphStyle(
        "CoverAuthor", fontName=fonts["regular"], fontSize=13, leading=17,
        alignment=TA_CENTER, textColor=colors["cover_fg"], spaceBefore=0,
    )
    title_page_title_style = ParagraphStyle(
        "TitlePageTitle", fontName=fonts["bold"], fontSize=22, leading=28,
        alignment=TA_CENTER, textColor=colors["ink"],
    )
    title_page_author_style = ParagraphStyle(
        "TitlePageAuthor", fontName=fonts["italic"], fontSize=12.5, leading=16,
        alignment=TA_CENTER, textColor=colors["ink_soft"],
    )

    return StyleKit(
        page_w=page_w, page_h=page_h,
        content_width=content_width, content_height=content_height,
        fonts=fonts, colors=colors,
        body_style=body_style, body_style_noindent=body_style_noindent,
        body_style_dropcap=body_style_dropcap, section_tag_style=section_tag_style,
        part_title_style=part_title_style, part_number_style=part_number_style,
        toc_title_style=toc_title_style, toc_label_font=toc_label_font,
        toc_page_font=toc_page_font, colophon_style=colophon_style,
        cover_title_style=cover_title_style, cover_subtitle_style=cover_subtitle_style,
        cover_author_style=cover_author_style,
        title_page_title_style=title_page_title_style,
        title_page_author_style=title_page_author_style,
        use_drop_caps=theme_cls.use_drop_caps, use_ornaments=theme_cls.use_ornaments,
    )
