"""Creating, finding and remembering projects.

Shared by the terminal wizard and the browser app, so that people who never
open a terminal get exactly the same projects as those who do.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sys
import time
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import ConfigError, load_config

STARTERS = Path(__file__).parent / "starters"

KINDS = {
    "thesis": "Πτυχιακή ή διπλωματική εργασία",
    "book": "Βιβλίο (μυθιστόρημα, διηγήματα, ποίηση)",
    "notes": "Σημειώσεις, άρθρο ή τεχνική αναφορά",
}
_KIND_TEMPLATE = {"thesis": "thesis", "book": "novel", "notes": "academic"}
_KIND_STARTER = {"thesis": "thesis", "book": "novel", "notes": "thesis"}

_LATIN = "a v g d e z i th i k l m n x o p r s s t y f ch ps o".split()
_TRANSLIT = dict(zip("αβγδεζηθικλμνξοπρσςτυφχψω", _LATIN, strict=True))


def slugify(text: str, fallback: str = "ergasia") -> str:
    """ASCII folder/file name; Greek is transliterated (Η Εργασία μου → i-ergasia-mou)."""
    plain = "".join(
        c for c in unicodedata.normalize("NFD", text.lower()) if not unicodedata.combining(c)
    )
    latin = "".join(_TRANSLIT.get(c, c) for c in plain)
    latin = latin.replace("oy", "ou").replace("ey", "ev").replace("ay", "av")
    return re.sub(r"[^a-z0-9]+", "-", latin).strip("-")[:40] or fallback


# ---------------------------------------------------------------------------
# where projects live
# ---------------------------------------------------------------------------


def default_workspace() -> Path:
    """``Documents/greekbook`` (or ``~/greekbook`` if there is no Documents folder)."""
    env = os.environ.get("GREEKBOOK_HOME")
    if env:
        return Path(env)
    docs = Path.home() / "Documents"
    return (docs if docs.is_dir() else Path.home()) / "greekbook"


def _state_file() -> Path:
    if sys.platform.startswith("win"):
        base = Path(os.environ.get("APPDATA", Path.home()))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return Path(os.environ.get("GREEKBOOK_STATE", base / "greekbook" / "recent.json"))


def remember(project: Path) -> None:
    """Put a project at the top of the recent list."""
    path = _state_file()
    recent = [p for p in _read_recent() if Path(p) != project.resolve()]
    recent.insert(0, str(project.resolve()))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(recent[:20], ensure_ascii=False, indent=1), encoding="utf-8")


def _read_recent() -> list[str]:
    try:
        data = json.loads(_state_file().read_text(encoding="utf-8"))
        return [str(p) for p in data] if isinstance(data, list) else []
    except (OSError, ValueError):
        return []


@dataclass
class ProjectInfo:
    path: Path
    title: str
    author: str
    template: str
    modified: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.path.name,
            "title": self.title,
            "author": self.author,
            "template": self.template,
            "modified": self.modified,
        }


def project_info(path: Path) -> ProjectInfo | None:
    try:
        cfg = load_config(path)
    except ConfigError:
        return None
    files = [p for p in path.rglob("*") if p.suffix in {".md", ".yaml", ".bib"}]
    modified = max((p.stat().st_mtime for p in files), default=0.0)
    return ProjectInfo(path.resolve(), cfg.title, cfg.author, cfg.template, modified)


def list_projects(workspace: Path | None = None) -> list[ProjectInfo]:
    """Recent projects first, then anything else found in the workspace."""
    seen: set[Path] = set()
    found: list[ProjectInfo] = []
    candidates = [Path(p) for p in _read_recent()]
    ws = workspace or default_workspace()
    if ws.is_dir():
        candidates += sorted(p for p in ws.iterdir() if (p / "book.yaml").is_file())
    for path in candidates:
        resolved = path.resolve()
        if resolved in seen or not (path / "book.yaml").is_file():
            continue
        seen.add(resolved)
        info = project_info(path)
        if info:
            found.append(info)
    return found


# ---------------------------------------------------------------------------
# creating projects
# ---------------------------------------------------------------------------


def unique_folder(parent: Path, title: str) -> Path:
    base = slugify(title)
    candidate = parent / base
    n = 2
    while candidate.exists() and any(candidate.iterdir()):
        candidate = parent / f"{base}-{n}"
        n += 1
    return candidate


_BLANK = {
    "thesis": {
        "front/abstract.md": (
            "# Περίληψη\n\n"
            "Γράψε εδώ την περίληψη της εργασίας σου: το πρόβλημα, τι έκανες και τι βρήκες, "
            "σε 150 έως 300 λέξεις.\n\n**Λέξεις-κλειδιά:** λέξη, λέξη, λέξη\n"
        ),
        "front/abstract-en.md": (
            "# Abstract\n\nThe abstract in English goes here.\n\n**Keywords:** word, word\n"
        ),
        "chapters/01-eisagogi.md": (
            "# Εισαγωγή\n\n"
            "Ξεκίνα να γράφεις εδώ. Κάθε κενή γραμμή αρχίζει νέα παράγραφο.\n\n"
            "Για *πλάγια* γράψε τη λέξη ανάμεσα σε αστεράκια, για **έντονα** σε διπλά. "
            'Τα "εισαγωγικά" γίνονται αυτόματα «ελληνικά».\n\n'
            "## Στόχοι της εργασίας\n\n"
            "Οι δύο δίεσες πάνω από αυτή την παράγραφο φτιάχνουν ενότητα. "
            "Τα κουμπιά πάνω από το κείμενο κάνουν όλα τα υπόλοιπα για σένα: εικόνες, "
            "πίνακες, υποσημειώσεις, παραπομπές.\n"
        ),
        "chapters/02-symperasmata.md": "# Συμπεράσματα\n\nΤα συμπεράσματα της εργασίας.\n",
        "references.bib": (
            "% Οι πηγές σου. Μπορείς να τις εξαγάγεις από Zotero ή Mendeley (BibTeX)\n"
            "% ή να τις γράψεις όπως το παράδειγμα. Στο κείμενο γράφεις [@knuth1984].\n\n"
            "@book{knuth1984,\n  author    = {Knuth, Donald E.},\n"
            "  title     = {The TeXbook},\n  publisher = {Addison-Wesley},\n"
            "  year      = {1984}\n}\n"
        ),
    },
    "book": {
        "chapters/01-kefalaio.md": (
            "# Κεφάλαιο πρώτο\n\n"
            "Η ιστορία σου ξεκινά εδώ. Κάθε κενή γραμμή αρχίζει νέα παράγραφο.\n\n"
            '"Οι διάλογοι μπαίνουν σε εισαγωγικά," είπε, "και γίνονται αυτόματα «ελληνικά»."\n\n'
            "---\n\n"
            "Οι τρεις παύλες πάνω από αυτή την παράγραφο κάνουν αλλαγή σκηνής.\n"
        ),
    },
    "notes": {
        "chapters/01-eisagogi.md": (
            "# Εισαγωγή\n\nΞεκίνα να γράφεις εδώ.\n\n## Πρώτη ενότητα\n\nΚείμενο.\n"
        ),
    },
}


def _book_yaml(config: dict[str, Any]) -> str:
    header = (
        "# Ρυθμίσεις της εργασίας. Μπορείς να τις αλλάξεις και από το κουμπί\n"
        "# «Ρυθμίσεις» της εφαρμογής (greekbook app).\n"
    )
    return header + yaml.safe_dump(config, allow_unicode=True, sort_keys=False)


def create_project(
    target: Path,
    kind: str,
    title: str,
    author: str,
    *,
    example: bool = False,
    thesis: dict[str, Any] | None = None,
) -> Path:
    """Create a project folder. ``example=True`` copies a full worked example."""
    if kind not in KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    if target.exists() and any(target.iterdir()):
        raise FileExistsError(f"Ο φάκελος {target} υπάρχει ήδη και δεν είναι άδειος.")
    title = title.strip() or "Χωρίς τίτλο"
    author = author.strip() or "Συγγραφέας"
    template = _KIND_TEMPLATE[kind]

    if example:
        shutil.copytree(STARTERS / _KIND_STARTER[kind], target, dirs_exist_ok=True)
        config = yaml.safe_load((target / "book.yaml").read_text(encoding="utf-8")) or {}
    else:
        target.mkdir(parents=True, exist_ok=True)
        for rel, text in _BLANK[kind].items():
            path = target / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")
        (target / "figures").mkdir(exist_ok=True)
        config = {}
        if kind == "thesis":
            config = {
                "front_matter": ["front/abstract.md", "front/abstract-en.md"],
                "bibliography": "references.bib",
                "citation_style": "apa",
                "list_of_figures": True,
                "list_of_tables": True,
            }

    config.update({"title": title, "author": author, "template": template})
    if kind == "thesis":
        fields = dict(config.get("thesis") or {})
        fields.update({k: v for k, v in (thesis or {}).items() if v not in (None, "")})
        fields.setdefault("type", "Πτυχιακή Εργασία")
        fields.setdefault("date", time.strftime("%Y"))
        config["thesis"] = fields
    config["output"] = f"{slugify(title)}.pdf"
    ordered = {k: config[k] for k in ("title", "subtitle", "author", "template") if k in config}
    ordered.update({k: v for k, v in config.items() if k not in ordered})
    (target / "book.yaml").write_text(_book_yaml(ordered), encoding="utf-8")
    load_config(target)  # fail early if something is off
    remember(target)
    return target
