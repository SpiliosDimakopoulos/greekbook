# -*- coding: utf-8 -*-
"""Clean — minimal modern black-on-white theme, sans-serif, no drop caps."""
from .base import Theme


class CleanTheme(Theme):
    name = "clean"
    description = "Μοντέρνο, λιτό, sans-serif ύφος — μαύρο σε λευκό, χωρίς drop caps."
    font_label = "GBSans"
    font_files = {
        "regular": "LiberationSans-Regular.ttf",
        "bold": "LiberationSans-Bold.ttf",
        "italic": "LiberationSans-Italic.ttf",
        "bold_italic": "LiberationSans-BoldItalic.ttf",
    }
    palette = {
        "paper": "#ffffff",
        "ink": "#1a1a1a",
        "ink_soft": "#404040",
        "muted": "#8c8c8c",
        "accent": "#1a1a1a",
        "cover_bg": "#111111",
        "cover_fg": "#ffffff",
        "cover_line": "#9c9c9c",
    }
    use_drop_caps = False
    use_ornaments = True
    body_font_size = 10.0
    body_leading = 15.5
