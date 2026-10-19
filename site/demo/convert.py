# Runs inside Pyodide: one Markdown document with YAML front matter → Typst source,
# through exactly the same code path as `greekbook build`.
import re
import shutil
import sys
from pathlib import Path

import yaml

sys.path.insert(0, "/src")

from greekbook.build import LIB_IMPORT, generate_typst
from greekbook.config import ConfigError, load_config

ROOT = Path("/project")
FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
# A citation (not a cross-reference): only then is a bibliography added.
CITATION = re.compile(r"(?<![\w@.])-?@(?!(?:fig|tbl|eq|sec|lst|ch|app):)\w")


def convert(text):
    meta, body = {}, text
    m = FRONT_MATTER.match(text)
    if m:
        try:
            meta = yaml.safe_load(m.group(1)) or {}
        except yaml.YAMLError as exc:
            return {"error": f"Σφάλμα στις ρυθμίσεις (YAML): {exc}"}
        body = text[m.end() :]
    if not isinstance(meta, dict):
        return {"error": "Οι ρυθμίσεις στην αρχή πρέπει να είναι ζεύγη key: value."}
    meta.setdefault("title", "Χωρίς τίτλο")
    meta.setdefault("author", "Ανώνυμος")
    if meta.get("template") != "sepia":
        meta.setdefault("paper_color", "#ffffff")  # visible pages in dark mode too
    if CITATION.search(body) and "bibliography" not in meta:
        meta["bibliography"] = "references.bib"

    shutil.rmtree(ROOT, ignore_errors=True)
    (ROOT / "chapters").mkdir(parents=True)
    (ROOT / "chapters" / "01.md").write_text(body, encoding="utf-8")
    (ROOT / "references.bib").write_text("", encoding="utf-8")
    (ROOT / "book.yaml").write_text(yaml.safe_dump(meta, allow_unicode=True), encoding="utf-8")
    try:
        source, diagnostics = generate_typst(load_config(ROOT))
    except ConfigError as exc:
        return {"error": str(exc)}
    source = source.replace(LIB_IMPORT, '#import "/greekbook/lib.typ": *')
    return {"source": source, "diagnostics": [str(d) for d in diagnostics]}
