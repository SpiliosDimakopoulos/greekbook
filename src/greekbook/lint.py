"""``greekbook validate``: catch the mistakes that are invisible on screen.

Most of them are specific to Greek text typed on a Greek/English keyboard:
a Latin "o" inside a Greek word looks identical but breaks search,
hyphenation and spell-checking; a medial "ς" or a final "σ" is easy to miss.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .config import BookConfig, ConfigError
from .markdown import Diagnostic, markdown_to_typst, relative_base

GREEK = "Ͱ-Ͽἀ-῿"
_WORD_RE = re.compile(rf"[A-Za-z{GREEK}]+")
_GREEK_RE = re.compile(rf"[{GREEK}]")
_LATIN_RE = re.compile(r"[A-Za-z]")
# Latin letters that look like Greek ones (A/Α, o/ο, …).
_LOOKALIKES = set("ABEHIKMNOPTXYZouvikx")
_MEDIAL_FINAL_SIGMA_RE = re.compile(rf"ς(?=[{GREEK}])")
_FINAL_SIGMA_RE = re.compile(r"(?<=[α-ωάέήίόύώϊϋΐΰ])σ\b(?![.΄'’])")
_CODE_RE = re.compile(r"`[^`]*`|\$[^$]*\$")
_FENCE_RE = re.compile(r"^(```|~~~)")
_CITE_KEY_RE = re.compile(r"(?<![\w@.\\])-?@([\w][\w:.\-/]*[\w])")
_BIB_KEY_RE = re.compile(r"@\w+\s*\{\s*([^,\s]+)\s*,")
_IMAGE_RE = re.compile(r"!\[[^\]]*\]\(([^)\s]+)")
_LABEL_RE = re.compile(r"\{#([\w:.\-]+)|\$\$\s*\(([\w:.\-]+)\)")
_REF_PREFIXES = ("fig:", "tbl:", "eq:", "sec:", "lst:", "ch:", "app:")


@dataclass
class Issue(Diagnostic):
    level: str = "warning"

    def __str__(self) -> str:
        where = f"{self.file}:{self.line}" if self.line else self.file
        return f"{where}: {self.level}: {self.message}"


def _lint_text(name: str, text: str) -> list[Issue]:
    issues: list[Issue] = []
    in_fence = False
    for lineno, line in enumerate(text.splitlines(), 1):
        if _FENCE_RE.match(line.strip()):
            in_fence = not in_fence
            continue
        if in_fence:
            continue
        prose = _CODE_RE.sub(" ", line)
        prose = re.sub(r"\]\([^)]*\)|\{[^}]*\}|https?://\S+|@[\w:.\-/]+", " ", prose)
        for m in _WORD_RE.finditer(prose):
            word = m.group(0)
            if _GREEK_RE.search(word) and _LATIN_RE.search(word):
                latin = "".join(sorted({c for c in word if _LATIN_RE.match(c)}))
                hint = " (μοιάζουν με ελληνικά)" if set(latin) <= _LOOKALIKES else ""
                issues.append(Issue(name, lineno,
                    f"η λέξη «{word}» έχει λατινικούς χαρακτήρες: {latin}{hint}"))  # fmt: skip
        for m in _MEDIAL_FINAL_SIGMA_RE.finditer(prose):
            around = next(w.group(0) for w in _WORD_RE.finditer(prose) if w.end() > m.start())
            issues.append(Issue(name, lineno, f"τελικό «ς» στη μέση λέξης («{around}»)"))
        for m in _FINAL_SIGMA_RE.finditer(prose):
            start = prose.rfind(" ", 0, m.start()) + 1
            issues.append(Issue(name, lineno, f"«σ» στο τέλος λέξης: «{prose[start : m.end()]}»"))
    paragraphs = re.split(r"\n\s*\n", text)
    para_line = 1
    for para in paragraphs:
        if not para.lstrip().startswith(("```", "~~~", "    ")):
            stripped = _CODE_RE.sub("", para)
            if stripped.count('"') % 2:
                issues.append(
                    Issue(name, para_line, 'μονός αριθμός εισαγωγικών (") στην παράγραφο')
                )
            if stripped.count("«") != stripped.count("»"):
                issues.append(Issue(name, para_line, "τα « και » δεν είναι ζευγαρωμένα"))
        para_line += para.count("\n") + 2
    return issues


def lint_project(cfg: BookConfig) -> list[Issue]:
    issues: list[Issue] = []
    try:
        files = cfg.front_matter_files() + cfg.chapter_files() + cfg.appendix_files()
        bib_files = cfg.bibliography_files()
    except ConfigError as exc:
        return [Issue("book.yaml", 0, str(exc), level="error")]

    bib_keys: set[str] = set()
    for bib in bib_files:
        bib_keys |= set(_BIB_KEY_RE.findall(bib.read_text(encoding="utf-8")))

    labels: set[str] = set()
    used: list[tuple[str, int, str]] = []
    for path in files:
        name = (
            path.relative_to(cfg.base_dir).as_posix()
            if path.is_relative_to(cfg.base_dir)
            else path.name
        )
        text = path.read_text(encoding="utf-8")
        issues.extend(_lint_text(name, text))
        _, diags = markdown_to_typst(text, cfg.language, cfg.math, name,
                                     relative_base(path, cfg.base_dir))  # fmt: skip
        issues.extend(Issue(d.file, d.line, d.message) for d in diags)
        for lineno, line in enumerate(text.splitlines(), 1):
            for m in _LABEL_RE.finditer(line):
                labels.add(m.group(1) or m.group(2))
            for m in _CITE_KEY_RE.finditer(_CODE_RE.sub(" ", line)):
                used.append((name, lineno, m.group(1)))
            for m in _IMAGE_RE.finditer(line):
                src = m.group(1)
                if not re.match(r"^[a-z]+://", src) and not (path.parent / src).is_file():
                    issues.append(Issue(name, lineno, f"δεν βρέθηκε η εικόνα {src}", "error"))

    for name, lineno, key in used:
        if key.startswith(_REF_PREFIXES):
            if key not in labels:
                issues.append(Issue(name, lineno, f"αναφορά σε άγνωστη ετικέτα @{key}", "error"))
        elif key not in bib_keys:
            what = "δεν υπάρχει στη βιβλιογραφία" if bib_files else "δεν έχει οριστεί bibliography"
            issues.append(Issue(name, lineno, f"η παραπομπή @{key} {what}", "error"))
    return issues


def lint_file(path: Path) -> list[Issue]:
    return _lint_text(path.name, path.read_text(encoding="utf-8"))
