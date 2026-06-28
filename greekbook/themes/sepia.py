# -*- coding: utf-8 -*-
"""Sepia — warm, aged-paper / vintage theme."""
from .base import Theme


class SepiaTheme(Theme):
    name = "sepia"
    description = "Vintage, serif, ζεστό ύφος — παλαιωμένο χαρτί με drop caps."
    font_label = "GBSerif"
    font_files = {
        "regular": "LiberationSerif-Regular.ttf",
        "bold": "LiberationSerif-Bold.ttf",
        "italic": "LiberationSerif-Italic.ttf",
        "bold_italic": "LiberationSerif-BoldItalic.ttf",
    }
    palette = {
        "paper": "#f4ecdd",        # warm cream page background
        "ink": "#2b2117",          # near-black warm brown, body text
        "ink_soft": "#4a3c2c",     # softer brown, secondary text
        "muted": "#8a7458",        # tan-brown, folios / running heads
        "accent": "#7c4a2d",       # rust-brown, rules / drop caps
        "cover_bg": "#241b14",     # near-black espresso, cover background
        "cover_fg": "#e8d9b8",     # warm parchment, cover text
        "cover_line": "#a9824f",   # bronze/gold, cover frame line
    }
    use_drop_caps = True
    use_ornaments = True
    body_font_size = 10.3
    body_leading = 15.6
