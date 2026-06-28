# -*- coding: utf-8 -*-
"""
Decorative ReportLab Flowables used by the layout engine: scene-break
ornaments, thin rules, drop caps, table-of-contents rows, and an invisible
"recorder" flowable used to discover which absolute page numbers certain
story elements land on (needed for the two-pass build).

Everything here is parameterized by color/font instead of hardcoded, so
the same classes work for every theme.
"""
from reportlab.pdfbase import pdfmetrics
from reportlab.platypus import Flowable, Paragraph
from reportlab.lib.styles import ParagraphStyle


class OrnamentRule(Flowable):
    """Three small diamonds centred — scene break ornament."""

    def __init__(self, width, color, size=2.2):
        Flowable.__init__(self)
        self.width = width
        self.color = color
        self.size = size
        self.height = 16

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(self.color)
        cx = self.width / 2.0
        s = self.size
        gap = 9
        for dx in (-gap, 0, gap):
            x = cx + dx
            y = 6
            c.saveState()
            c.translate(x, y)
            c.rotate(45)
            c.rect(-s / 2, -s / 2, s, s, stroke=0, fill=1)
            c.restoreState()
        c.restoreState()


class TopRule(Flowable):
    """A thin horizontal rule, used under running heads / above folios."""

    def __init__(self, width, color, thickness=0.5):
        Flowable.__init__(self)
        self.width = width
        self.color = color
        self.thickness = thickness
        self.height = thickness

    def draw(self):
        c = self.canv
        c.saveState()
        c.setStrokeColor(self.color)
        c.setLineWidth(self.thickness)
        c.line(0, 0, self.width, 0)
        c.restoreState()


class PageRecorder(Flowable):
    """Invisible flowable: when drawn, records the absolute page number it
    landed on into `registry[key]`. Used to discover where unnumbered
    front-matter / part-title pages fall during the discovery pass."""

    def __init__(self, registry, key):
        Flowable.__init__(self)
        self.width = 0
        self.height = 0
        self.registry = registry
        self.key = key

    def draw(self):
        page_no = self.canv.getPageNumber()
        self.registry.setdefault(self.key, set()).add(page_no)


def _wrap_label(text, max_width, font_name, font_size):
    """Greedy word-wrap of `text` into lines whose rendered width is each
    <= max_width. Used by TocEntry so long part titles wrap instead of
    silently overflowing/clipping past the dotted leader."""
    words = text.split()
    if not words:
        return [text]
    lines = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if pdfmetrics.stringWidth(candidate, font_name, font_size) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines


class TocEntry(Flowable):
    """A table-of-contents row: label left-aligned, page number
    right-aligned, dotted leader between them, all within a centred block
    of fixed width — like a real typeset TOC.

    Most labels fit on one line, but a long part title can be too wide
    for the block (previously this overflowed/clipped silently). When
    that happens, the label wraps across multiple lines and the row's
    height grows to match, instead of losing text."""

    LINE_HEIGHT = 24

    def __init__(self, label, page_str, width, label_font, page_font,
                 ink_color, dot_color, block_width=None):
        Flowable.__init__(self)
        self.label = label
        self.page_str = page_str
        self.width = width
        self.label_font = label_font
        self.page_font = page_font
        self.ink_color = ink_color
        self.dot_color = dot_color
        self.block_width = block_width or (width * 0.90)

        label_font_name, label_font_size = label_font
        page_font_name, page_font_size = page_font
        self._page_w = pdfmetrics.stringWidth(page_str, page_font_name, page_font_size)
        full_label_w = pdfmetrics.stringWidth(label, label_font_name, label_font_size)

        # Minimum room reserved for the dotted leader between label and
        # page number, so the two text blocks never collide.
        min_gap = 18

        if full_label_w + min_gap + self._page_w <= self.block_width:
            self._lines = [label]
        else:
            # Doesn't fit on one line — wrap it. Wrap against a width
            # that already reserves room for the page number + gap so
            # the final line never collides with them either.
            wrap_width = max(self.block_width - min_gap - self._page_w, 40)
            self._lines = _wrap_label(label, wrap_width, label_font_name, label_font_size)

        self.height = self.LINE_HEIGHT * len(self._lines)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        label_font_name, label_font_size = self.label_font
        page_font_name, page_font_size = self.page_font
        x0 = (self.width - self.block_width) / 2.0
        x1 = x0 + self.block_width
        last_idx = len(self._lines) - 1
        last_baseline = 7

        c.saveState()
        c.setFont(label_font_name, label_font_size)
        c.setFillColor(self.ink_color)
        for i, line in enumerate(self._lines):
            baseline = last_baseline + self.LINE_HEIGHT * (last_idx - i)
            c.drawString(x0, baseline, line)
        last_line_w = pdfmetrics.stringWidth(self._lines[last_idx], label_font_name, label_font_size)

        c.setFont(page_font_name, page_font_size)
        c.drawString(x1 - self._page_w, last_baseline, self.page_str)

        dot_start = x0 + last_line_w + 6
        dot_end = x1 - self._page_w - 6
        if dot_end > dot_start:
            c.setFillColor(self.dot_color)
            c.setFont(label_font_name, 9)
            dot_spacing = 5.2
            n_dots = max(int((dot_end - dot_start) / dot_spacing), 0)
            for i in range(n_dots):
                c.drawString(dot_start + i * dot_spacing, last_baseline + 0.5, ".")
        c.restoreState()


class DropCapParagraph(Flowable):
    """
    Renders a paragraph with a large decorative first letter (drop cap)
    that sits to the left of the first few lines, with the remaining text
    wrapping in a Paragraph alongside it.

    The drop cap is drawn as the real glyph straight from the font (accent
    included, if the letter has one) via a plain drawString — no manual
    decomposition. Modern fonts and PDF viewers render precomposed Greek
    tonos capitals correctly, so this is both simpler and more robust than
    hand-building an accent mark.
    """

    def __init__(self, first_letter, rest_text, width, style, cap_font,
                 cap_color, cap_size=38, lines_high=3):
        Flowable.__init__(self)
        self.full_first_letter = first_letter
        self.prefix_punct = ""
        core = first_letter
        while core and core[0] in "«\"'\u2018\u2019":
            self.prefix_punct += core[0]
            core = core[1:]
        self.cap_letter = core

        self.rest_text = rest_text
        self.width = width
        self.style = style
        self.cap_font = cap_font
        self.cap_size = cap_size
        self.cap_color = cap_color
        self.lines_high = lines_high
        measured_text = self.prefix_punct + self.cap_letter
        self.cap_width = pdfmetrics.stringWidth(measured_text, cap_font, cap_size) + 2
        self.line_height = style.leading
        self.indent_para = Paragraph(rest_text, ParagraphStyle(
            "DropCapBody", parent=style, firstLineIndent=0,
        ))
        avail_width = max(width - self.cap_width, 10)
        w, h = self.indent_para.wrap(avail_width, 5000)
        self.body_height = h
        self.height = max(h, self.line_height * self.lines_high)

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        c = self.canv
        c.saveState()
        c.setFillColor(self.cap_color)
        c.setFont(self.cap_font, self.cap_size)
        cap_baseline = self.height - self.cap_size * 0.82

        x = 0
        if self.prefix_punct:
            c.drawString(x, cap_baseline, self.prefix_punct)
            x += pdfmetrics.stringWidth(self.prefix_punct, self.cap_font, self.cap_size)
        c.drawString(x, cap_baseline, self.cap_letter)

        c.restoreState()
        self.indent_para.drawOn(c, self.cap_width, self.height - self.body_height)
