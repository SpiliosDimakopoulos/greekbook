"""greekbook — Markdown to beautifully typeset Greek books and theses.

from greekbook import load_config, build

config = load_config("my-thesis/book.yaml")
result = build(config)          # PDF (and optionally EPUB)
"""

__version__ = "0.2.0.dev0"
