"""Loading and validating ``book.yaml``.

A project is a directory with a ``book.yaml`` and Markdown files. The
smallest valid project is::

    title: Η Φόνισσα
    author: Αλέξανδρος Παπαδιαμάντης

which typesets every ``*.md`` file in ``chapters/`` (or the legacy
``parts/``) in filename order. Everything else has a sensible default.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

TEMPLATES = ("novel", "classic", "sepia", "clean", "academic", "thesis")

# Templates of greekbook 0.x, which were called "themes".
_LEGACY_THEMES = {"sepia": "sepia", "clean": "clean", "academic": "academic"}

PAGE_SIZES = {
    "A4": ("210mm", "297mm"),
    "A5": ("148mm", "210mm"),
    "A6": ("105mm", "148mm"),
    "B5": ("176mm", "250mm"),
    "LETTER": ("8.5in", "11in"),
    "6X9IN": ("6in", "9in"),
    "5.5X8.5IN": ("5.5in", "8.5in"),
}
_CUSTOM_SIZE_RE = re.compile(r"^\s*([\d.]+)\s*[xX×]\s*([\d.]+)\s*(mm|cm|in)?\s*$")

CITATION_STYLES = {
    "apa": "apa",
    "ieee": "ieee",
    "harvard": "harvard-cite-them-right",
    "chicago": "chicago-author-date",
    "chicago-notes": "chicago-notes",
    "mla": "modern-language-association",
    "vancouver": "vancouver",
}

PDF_STANDARDS = ("1.7", "a-2b", "a-3b", "ua-1")

CHAPTER_NUMBERING = ("auto", "greek", "arabic", "roman", "words", "none")


class ConfigError(Exception):
    """Raised for any problem in book.yaml or the project layout."""


def parse_page_size(value: str) -> tuple[str, str]:
    """``"A5"`` / ``"6x9in"`` / ``"148x210mm"`` → Typst lengths (width, height)."""
    key = value.strip().upper().replace(" ", "")
    if key in PAGE_SIZES:
        return PAGE_SIZES[key]
    m = _CUSTOM_SIZE_RE.match(value)
    if not m:
        presets = ", ".join(sorted(PAGE_SIZES))
        raise ConfigError(
            f"Μη έγκυρο page_size: '{value}'. Διάλεξε ένα από {presets} "
            "ή γράψε μέγεθος όπως '148x210mm' ή '6x9in'."
        )
    w, h, unit = m.groups()
    unit = unit or "mm"
    return f"{w}{unit}", f"{h}{unit}"


@dataclass
class Thesis:
    """Cover-page metadata for the ``thesis`` template."""

    type: str = "Πτυχιακή Εργασία"
    institution: str = ""
    school: str = ""
    department: str = ""
    program: str = ""
    student_id: str = ""
    supervisor: str = ""
    committee: list[str] = field(default_factory=list)
    place: str = ""
    date: str = ""
    logo: str | None = None
    declaration: bool = True


@dataclass
class BookConfig:
    title: str
    author: str
    base_dir: Path
    subtitle: str = ""
    language: str = "el"
    template: str = "novel"
    page_size: str = "A5"
    chapters: list[str] = field(default_factory=list)
    chapters_dir: str = "chapters"
    front_matter: list[str] = field(default_factory=list)
    appendices: list[str] = field(default_factory=list)
    output: str = "book.pdf"
    bibliography: list[str] = field(default_factory=list)
    citation_style: str = "apa"
    toc: bool | None = None
    list_of_figures: bool = False
    list_of_tables: bool = False
    chapter_numbering: str = "auto"
    math: str = "latex"
    pdf_standard: str = "1.7"
    font: str | None = None
    font_size: str | None = None
    paper_color: str | None = None
    dedication: str = ""
    epigraph: str = ""
    copyright: str = ""
    publisher: str = ""
    year: str = ""
    keywords: list[str] = field(default_factory=list)
    thesis: Thesis = field(default_factory=Thesis)

    # ------------------------------------------------------------------
    @property
    def page_dimensions(self) -> tuple[str, str]:
        return parse_page_size(self.page_size)

    @property
    def output_path(self) -> Path:
        out = Path(self.output)
        return out if out.is_absolute() else self.base_dir / out

    @property
    def show_toc(self) -> bool:
        return self.template in ("thesis", "academic") if self.toc is None else self.toc

    def _resolve(self, names: list[str], what: str) -> list[Path]:
        paths = []
        for name in names:
            p = (self.base_dir / name).resolve()
            if not p.is_file():
                raise ConfigError(f"Δεν βρέθηκε το αρχείο {what}: {name}")
            paths.append(p)
        return paths

    def chapter_files(self) -> list[Path]:
        """Explicit ``chapters:`` list, else every ``*.md`` in the chapters
        directory (``chapters/``, or ``parts/`` for 0.x projects)."""
        if self.chapters:
            return self._resolve(self.chapters, "κεφαλαίου")
        for dirname in (self.chapters_dir, "parts"):
            directory = self.base_dir / dirname
            if directory.is_dir():
                files = sorted(p for p in directory.glob("*.md") if p.read_text("utf-8").strip())
                if files:
                    return files
        raise ConfigError(
            f"Δεν βρέθηκαν κεφάλαια: πρόσθεσε αρχεία .md στον φάκελο "
            f"'{self.chapters_dir}/' ή όρισε 'chapters:' στο book.yaml."
        )

    def front_matter_files(self) -> list[Path]:
        return self._resolve(self.front_matter, "front matter")

    def appendix_files(self) -> list[Path]:
        return self._resolve(self.appendices, "παραρτήματος")

    def bibliography_files(self) -> list[Path]:
        return self._resolve(self.bibliography, "βιβλιογραφίας")


_FIELDS = {
    "title", "author", "subtitle", "language", "template", "theme", "page_size",
    "chapters", "chapters_dir", "parts_dir", "front_matter", "appendices", "output",
    "bibliography", "citation_style", "toc", "list_of_figures", "list_of_tables",
    "chapter_numbering", "math", "pdf_standard", "font", "font_size", "paper_color",
    "dedication", "epigraph", "copyright", "publisher", "year", "keywords", "thesis",
    "cover_image",
}  # fmt: skip
_LEGACY_FIELDS = {"theme", "parts_dir", "cover_image"}


def _as_list(value: Any, name: str) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return value
    raise ConfigError(f"Το πεδίο '{name}' πρέπει να είναι κείμενο ή λίστα από κείμενα.")


def _choice(raw: dict[str, Any], key: str, default: str, options: tuple[str, ...]) -> str:
    value = str(raw.get(key, default))
    if value not in options:
        raise ConfigError(
            f"Μη έγκυρη τιμή '{value}' για το '{key}'. Επιτρεπτές: {', '.join(options)}"
        )
    return value


def config_from_dict(raw: dict[str, Any], base_dir: Path, source: str = "book.yaml") -> BookConfig:
    unknown = set(raw) - _FIELDS
    if unknown:
        raise ConfigError(
            f"Άγνωστα πεδία στο {source}: {', '.join(sorted(unknown))}. "
            f"Έγκυρα: {', '.join(sorted(_FIELDS - _LEGACY_FIELDS))}"
        )
    missing = [k for k in ("title", "author") if not raw.get(k)]
    if missing:
        raise ConfigError(f"Λείπουν υποχρεωτικά πεδία στο {source}: {', '.join(missing)}")

    template = raw.get("template") or _LEGACY_THEMES.get(str(raw.get("theme", "")), "novel")
    if template not in TEMPLATES:
        raise ConfigError(f"Άγνωστο template '{template}'. Διαθέσιμα: {', '.join(TEMPLATES)}")
    style = str(raw.get("citation_style", "apa"))
    if style not in CITATION_STYLES and not style.endswith(".csl"):
        raise ConfigError(
            f"Άγνωστο citation_style '{style}'. Διαθέσιμα: {', '.join(CITATION_STYLES)} "
            "ή διαδρομή προς αρχείο .csl"
        )

    thesis_raw = raw.get("thesis") or {}
    if not isinstance(thesis_raw, dict):
        raise ConfigError("Το πεδίο 'thesis' πρέπει να είναι λεξικό (key: value).")
    thesis_unknown = set(thesis_raw) - set(Thesis.__dataclass_fields__)
    if thesis_unknown:
        raise ConfigError(f"Άγνωστα πεδία στο thesis: {', '.join(sorted(thesis_unknown))}")
    thesis = Thesis(**{k: v for k, v in thesis_raw.items() if k != "committee"})
    thesis.committee = _as_list(thesis_raw.get("committee"), "thesis.committee")

    default_size = "A4" if template in ("thesis", "academic") else "A5"
    cfg = BookConfig(
        title=str(raw["title"]),
        author=str(raw["author"]),
        base_dir=base_dir,
        subtitle=str(raw.get("subtitle") or ""),
        language=str(raw.get("language", "el")),
        template=template,
        page_size=str(raw.get("page_size", default_size)),
        chapters=_as_list(raw.get("chapters"), "chapters"),
        chapters_dir=str(raw.get("chapters_dir") or raw.get("parts_dir") or "chapters"),
        front_matter=_as_list(raw.get("front_matter"), "front_matter"),
        appendices=_as_list(raw.get("appendices"), "appendices"),
        output=str(raw.get("output", "book.pdf")),
        bibliography=_as_list(raw.get("bibliography"), "bibliography"),
        citation_style=style,
        toc=raw.get("toc"),
        list_of_figures=bool(raw.get("list_of_figures", False)),
        list_of_tables=bool(raw.get("list_of_tables", False)),
        chapter_numbering=_choice(raw, "chapter_numbering", "auto", CHAPTER_NUMBERING),
        math=_choice(raw, "math", "latex", ("latex", "typst")),
        pdf_standard=_choice(raw, "pdf_standard", "1.7", PDF_STANDARDS),
        font=raw.get("font"),
        font_size=None if raw.get("font_size") is None else str(raw["font_size"]),
        paper_color=raw.get("paper_color"),
        dedication=str(raw.get("dedication") or ""),
        epigraph=str(raw.get("epigraph") or ""),
        copyright=str(raw.get("copyright") or ""),
        publisher=str(raw.get("publisher") or ""),
        year=str(raw.get("year") or ""),
        keywords=_as_list(raw.get("keywords"), "keywords"),
        thesis=thesis,
    )
    parse_page_size(cfg.page_size)  # validate early
    return cfg


def load_config(path: str | Path) -> BookConfig:
    """Load ``book.yaml`` (or a directory containing one)."""
    p = Path(path).resolve()
    if p.is_dir():
        p = p / "book.yaml"
    if not p.is_file():
        raise ConfigError(f"Δεν βρέθηκε το αρχείο ρυθμίσεων: {p}")
    try:
        raw = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
    except yaml.YAMLError as exc:
        raise ConfigError(f"Σφάλμα YAML στο {p.name}: {exc}") from exc
    if not isinstance(raw, dict):
        raise ConfigError(f"Το {p.name} πρέπει να περιέχει ζεύγη key: value.")
    return config_from_dict(raw, p.parent, p.name)
