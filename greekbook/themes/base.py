# -*- coding: utf-8 -*-
"""
Base class for greekbook visual themes.
A theme owns three things: which font family is used for body text
(bundled inside the package, so nothing needs to be installed on the
system), the color palette, and a couple of stylistic toggles (drop
caps, scene-break ornaments). To add a new theme, subclass `Theme` and
override the class attributes — see sepia.py and clean.py for examples.
"""
import os
from reportlab.lib.colors import HexColor
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfbase.ttfonts import TTFont

FONTS_DIR = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "fonts"))
_REGISTERED_LABELS = set()


class Theme:
    name = "base"
    description = ""

    # Font family registered with ReportLab under `font_label` /
    # `font_label`-Bold / -Italic / -BoldItalic. The four files are
    # resolved relative to greekbook/fonts/.
    font_label = "GBSerif"
    font_files = {
        "regular": "LiberationSerif-Regular.ttf",
        "bold": "LiberationSerif-Bold.ttf",
        "italic": "LiberationSerif-Italic.ttf",
        "bold_italic": "LiberationSerif-BoldItalic.ttf",
    }

    # Every theme must define these eight colors as hex strings.
    palette = {
        "paper": "#ffffff",
        "ink": "#000000",
        "ink_soft": "#333333",
        "muted": "#888888",
        "accent": "#000000",
        "cover_bg": "#000000",
        "cover_fg": "#ffffff",
        "cover_line": "#888888",
    }

    use_drop_caps = True
    use_ornaments = True

    # Body text size/leading in points — themes may tune these for their
    # chosen typeface (e.g. a sans-serif theme often wants slightly more
    # leading at the same point size to stay equally readable).
    body_font_size = 10.3
    body_leading = 15.6

    @classmethod
    def register_fonts(cls):
        """Register this theme's fonts with ReportLab (once) and return
        a dict of font names usable directly as ParagraphStyle(fontName=...)."""
        if cls.font_label not in _REGISTERED_LABELS:
            names = cls.font_names()
            pdfmetrics.registerFont(TTFont(names["regular"], os.path.join(FONTS_DIR, cls.font_files["regular"])))
            pdfmetrics.registerFont(TTFont(names["bold"], os.path.join(FONTS_DIR, cls.font_files["bold"])))
            pdfmetrics.registerFont(TTFont(names["italic"], os.path.join(FONTS_DIR, cls.font_files["italic"])))
            pdfmetrics.registerFont(TTFont(names["bold_italic"], os.path.join(FONTS_DIR, cls.font_files["bold_italic"])))
            registerFontFamily(
                names["regular"], normal=names["regular"], bold=names["bold"],
                italic=names["italic"], boldItalic=names["bold_italic"],
            )
            _REGISTERED_LABELS.add(cls.font_label)
        return cls.font_names()

    @classmethod
    def font_names(cls):
        return {
            "regular": cls.font_label,
            "bold": f"{cls.font_label}-Bold",
            "italic": f"{cls.font_label}-Italic",
            "bold_italic": f"{cls.font_label}-BoldItalic",
        }

    @classmethod
    def color(cls, key):
        return HexColor(cls.palette[key])
