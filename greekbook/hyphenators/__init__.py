# -*- coding: utf-8 -*-
"""
Registry that maps a book's `language` field (from book.yaml) to a
hyphenator instance exposing the .iterate(word) interface ReportLab
expects for ParagraphStyle(hyphenationLang=...).

Currently supported:
- "el" (Greek)            -> GreekHyphenator (bundled rule-based syllabifier)
- "en", "en_US", "en_GB"  -> EnglishHyphenator (wraps pyphen, if installed)
"""
from .greek import GreekHyphenator
from .english import EnglishHyphenator

_GREEK_CODES = {"el", "el_gr", "gr", "greek"}


def get_hyphenator(language: str):
    """Return a hyphenator instance for the given language code.

    Greek codes ("el", "el_GR", ...) get the bundled rule-based Greek
    syllabifier. Anything starting with "en" is treated as English and
    passed straight through to pyphen (e.g. "en_GB" works as-is). Any
    other code raises a clear error rather than silently disabling
    hyphenation, since that's surprising in a typesetting tool.
    """
    lang = (language or "el").strip()
    key = lang.lower()

    if key in _GREEK_CODES:
        return GreekHyphenator(min_word_length=7, min_fragment=2)

    if key.startswith("en"):
        pyphen_lang = lang if "_" in lang else "en_US"
        return EnglishHyphenator(lang=pyphen_lang)

    raise ValueError(
        f"Άγνωστη γλώσσα συλλαβισμού: '{language}'. "
        f"Υποστηρίζονται προς το παρόν: 'el' (ελληνικά) και 'en'/'en_GB'/... (αγγλικά)."
    )


__all__ = ["get_hyphenator", "GreekHyphenator", "EnglishHyphenator"]
