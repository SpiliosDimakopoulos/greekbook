# -*- coding: utf-8 -*-
"""Academic — σοβαρό, επίσημο ύφος για δοκίμια/μελέτες, χωρίς drop caps."""
from .base import Theme


class AcademicTheme(Theme):
    name = "academic"
    description = "Σοβαρό, ακαδημαϊκό ύφος — serif DejaVu, σκούρο μπλε σε γκριζωπό χαρτί, χωρίς drop caps."
    font_label = "GBAcademic"
    font_files = {
        "regular": "DejaVuSerif.ttf",
        "bold": "DejaVuSerif-Bold.ttf",
        "italic": "DejaVuSerif-Italic.ttf",
        "bold_italic": "DejaVuSerif-BoldItalic.ttf",
    }
    palette = {
        "paper": "#f7f7f5",        # ελαφρώς γκριζωπό λευκό, όχι κάθαρο λευκό
        "ink": "#1c2430",          # πολύ σκούρο μπλε-γκρι, σχεδόν μαύρο
        "ink_soft": "#3c4656",     # απαλό σκούρο μπλε-γκρι, δευτερεύον κείμενο
        "muted": "#7c8696",        # γκρι-μπλε, folios / running heads
        "accent": "#5a3c1f",       # σκούρο μπρονζέ-καφέ, ρίγες / τίτλοι
        "cover_bg": "#1c2430",     # σκούρο μπλε-γκρι, εξώφυλλο
        "cover_fg": "#f0ede4",     # σπασμένο λευκό, κείμενο εξωφύλλου
        "cover_line": "#9a8156",   # μπρονζέ, πλαίσιο εξωφύλλου
    }
    use_drop_caps = False
    use_ornaments = True
    body_font_size = 10.2
    body_leading = 15.8
