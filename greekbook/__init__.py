# -*- coding: utf-8 -*-
"""
greekbook — a PDF book typesetter for Greek (and English) prose.

Minimal public API:

    from greekbook import build_book, load_config, available_themes

    config = load_config("my_book/book.yaml")
    output = build_book(config)          # returns Path to the generated PDF

See https://github.com/... for a full usage guide and book.yaml reference.
"""

__version__ = "0.1.0"
__author__ = "greekbook contributors"

from .builder import build_book
from .config import BookConfig, ConfigError, load_config
from .themes import available_themes, get_theme
from .hyphenators import get_hyphenator

__all__ = [
    "build_book",
    "load_config",
    "BookConfig",
    "ConfigError",
    "get_theme",
    "available_themes",
    "get_hyphenator",
    "__version__",
]
