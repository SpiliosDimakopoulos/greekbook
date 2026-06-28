# -*- coding: utf-8 -*-
"""
English hyphenator. Wraps `pyphen` (Liang/TeX hyphenation patterns) behind
the same .iterate(word) interface used throughout greekbook, so English
parts can be mixed into the same pipeline as Greek ones (e.g. a bilingual
book, or an all-English book built with this tool).

If pyphen is not installed, falls back to no hyphenation rather than
crashing the build — long English words will simply not break at the
line edge, which only matters cosmetically for narrow page widths.
"""
import warnings

try:
    import pyphen as _pyphen
    _HAS_PYPHEN = True
except ImportError:
    _HAS_PYPHEN = False


class EnglishHyphenator:
    """Mimics pyphen.Pyphen's .iterate(word) interface for ReportLab."""

    def __init__(self, lang="en_US"):
        self._dic = None
        if _HAS_PYPHEN:
            try:
                self._dic = _pyphen.Pyphen(lang=lang)
            except KeyError:
                warnings.warn(
                    f"greekbook: άγνωστο pyphen dictionary '{lang}', "
                    "ο αγγλικός συλλαβισμός απενεργοποιείται."
                )
        else:
            warnings.warn(
                "greekbook: το πακέτο 'pyphen' δεν είναι εγκατεστημένο — ο "
                "αγγλικός συλλαβισμός απενεργοποιείται (pip install pyphen)."
            )

    def iterate(self, word):
        if self._dic is None:
            return
        yield from self._dic.iterate(word)
