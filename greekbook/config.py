# -*- coding: utf-8 -*-
"""
Parses a book.yaml project file into a BookConfig, and auto-discovers the
markdown files inside its parts/ directory.
"""
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple

import yaml
from reportlab.lib.pagesizes import A4, A5, A6, B5, LETTER
from reportlab.lib.units import mm, inch

from .themes import available_themes

PAGE_SIZE_PRESETS = {
    "A4": A4,
    "A5": A5,
    "A6": A6,
    "B5": B5,
    "LETTER": LETTER,
    "6X9IN": (6 * inch, 9 * inch),
    "5.5X8.5IN": (5.5 * inch, 8.5 * inch),
}

_CUSTOM_SIZE_RE = re.compile(
    r"^\s*([\d.]+)\s*[xX]\s*([\d.]+)\s*(mm|cm|in)?\s*$"
)


class ConfigError(Exception):
    """Raised for any problem in book.yaml or the project layout."""


def parse_page_size(value: str) -> Tuple[float, float]:
    """Accepts a preset name ("A5", "6x9in") or a custom "WIDTHxHEIGHTunit"
    string (e.g. "148x210mm", "6x9in") and returns (width_pt, height_pt)."""
    key = value.strip().upper().replace(" ", "")
    if key in PAGE_SIZE_PRESETS:
        return PAGE_SIZE_PRESETS[key]

    m = _CUSTOM_SIZE_RE.match(value)
    if not m:
        presets = ", ".join(sorted(PAGE_SIZE_PRESETS))
        raise ConfigError(
            f"Μη έγκυρο page_size: '{value}'. Χρησιμοποίησε ένα από: {presets}, "
            f"ή προσαρμοσμένο μέγεθος όπως '148x210mm' ή '6x9in'."
        )
    w, h, unit = m.groups()
    unit = (unit or "mm").lower()
    factor = {"mm": mm, "cm": mm * 10, "in": inch}[unit]
    return float(w) * factor, float(h) * factor


@dataclass
class PartSource:
    """One discovered part: its source markdown file, and the label/body
    split out of it (label comes from the file's leading '# Heading'
    line, if present)."""
    path: Path
    label: Optional[str]
    body: str


@dataclass
class BookConfig:
    title: str
    author: str
    base_dir: Path
    subtitle: Optional[str] = None
    language: str = "el"
    theme: str = "sepia"
    page_size: str = "A5"
    parts_dir: str = "parts"
    output: str = "book.pdf"
    cover_image: Optional[str] = None  # relative path to cover image

    @property
    def page_size_pt(self) -> Tuple[float, float]:
        return parse_page_size(self.page_size)

    @property
    def parts_path(self) -> Path:
        return self.base_dir / self.parts_dir

    @property
    def output_path(self) -> Path:
        out = Path(self.output)
        return out if out.is_absolute() else self.base_dir / out

    def discover_parts(self) -> List[PartSource]:
        """Scan parts_dir for .md files, sorted by filename, and split each
        into (label, body). A part's label is taken from a leading
        '# Heading' line in the file; if absent, label is left as None and
        the caller is responsible for generating a fallback."""
        if not self.parts_path.is_dir():
            raise ConfigError(
                f"Ο φάκελος μερών δεν υπάρχει: {self.parts_path}"
            )
        md_files = sorted(self.parts_path.glob("*.md"))
        if not md_files:
            raise ConfigError(
                f"Δεν βρέθηκαν αρχεία .md μέσα στο {self.parts_path}"
            )
        parts = []
        for path in md_files:
            try:
                text = path.read_text(encoding="utf-8")
            except UnicodeDecodeError:
                raise ConfigError(
                    f"Το αρχείο '{path.name}' δεν είναι κωδικοποιημένο σε UTF-8. "
                    f"Άνοιξέ το στον editor σου και αποθήκευσέ το ξανά με κωδικοποίηση UTF-8."
                )
            if not text.strip():
                import warnings
                warnings.warn(
                    f"Το αρχείο '{path.name}' είναι άδειο και παραλείπεται.",
                    stacklevel=2,
                )
                continue
            label, body = _split_heading(text)
            parts.append(PartSource(path=path, label=label, body=body))
        if not parts:
            raise ConfigError(
                f"Δεν βρέθηκε κανένα αρχείο .md με περιεχόμενο μέσα στο {self.parts_path}"
            )
        return parts


def _split_heading(text: str) -> Tuple[Optional[str], str]:
    lines = text.split("\n")
    if lines and lines[0].strip().startswith("#"):
        label = lines[0].strip().lstrip("#").strip()
        rest = "\n".join(lines[1:])
        # drop a single leading blank line after the heading, if present
        if rest.startswith("\n"):
            rest = rest[1:]
        return label, rest
    return None, text


def load_config(path: str) -> BookConfig:
    p = Path(path).resolve()
    if not p.is_file():
        raise ConfigError(f"Δεν βρέθηκε το αρχείο config: {p}")
    with p.open("r", encoding="utf-8") as f:
        try:
            raw = yaml.safe_load(f) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(
                f"Σφάλμα ανάλυσης YAML στο {p.name}: {exc}"
            ) from exc

    required = ["title", "author"]
    missing = [k for k in required if not raw.get(k)]
    if missing:
        raise ConfigError(
            f"Λείπουν υποχρεωτικά πεδία στο {p.name}: {', '.join(missing)}"
        )

    known_fields = {
        "title", "author", "subtitle", "language", "theme",
        "page_size", "parts_dir", "output", "cover_image",
    }
    unknown = set(raw) - known_fields
    if unknown:
        raise ConfigError(
            f"Άγνωστα πεδία στο {p.name}: {', '.join(sorted(unknown))}. "
            f"Έγκυρα πεδία: {', '.join(sorted(known_fields))}"
        )

    theme = raw.get("theme", "sepia")
    supported_themes = available_themes()
    if theme not in supported_themes:
        raise ConfigError(
            f"Άγνωστο theme '{theme}' στο {p.name}. "
            f"Διαθέσιμα themes: {', '.join(supported_themes)}"
        )

    cfg = BookConfig(
        title=raw["title"],
        author=raw["author"],
        base_dir=p.parent,
        subtitle=raw.get("subtitle"),
        language=raw.get("language", "el"),
        theme=theme,
        page_size=raw.get("page_size", "A5"),
        parts_dir=raw.get("parts_dir", "parts"),
        output=raw.get("output", "book.pdf"),
        cover_image=raw.get("cover_image"),
    )
    return cfg
