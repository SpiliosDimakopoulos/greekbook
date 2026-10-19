from pathlib import Path

import pytest
from pypdf import PdfReader

from greekbook.build import BuildError, build, compile_typst, generate_typst
from greekbook.config import load_config

from .conftest import make_project


def pdf_text(path: Path) -> str:
    """All text of a PDF with whitespace removed: letter-spaced capitals
    extract as "Π Τ Υ Χ", so assertions compare squashed strings."""
    text = "".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return "".join(text.split())


def has(text: str, expected: str) -> bool:
    return "".join(expected.split()) in text


def test_thesis_end_to_end(thesis: Path) -> None:
    cfg = load_config(thesis)
    result = build(cfg)
    assert result.output is not None and result.output.is_file()
    assert result.diagnostics == []
    reader = PdfReader(result.output)
    assert reader.metadata is not None and reader.metadata.title == cfg.title
    text = pdf_text(result.output)
    # cover, declaration, outlines, chapters, bibliography, appendix
    for expected in (
        "ΠΤΥΧΙΑΚΗ ΕΡΓΑΣΙΑ",
        "Δήλωση πρωτοτυπίας",
        "Περιεχόμενα",
        "Κατάλογος σχημάτων",
        "Κεφάλαιο 1",
        "Βιβλιογραφία",
        "Παράρτημα Α",
    ):
        assert has(text, expected), expected
    # per-chapter numbering is right even when referenced from another chapter
    assert has(text, "Σχήμα 2.1") and has(text, "Πίνακας 3.1")
    assert has(text, "στον Πίνακα 3.1")
    # citations resolved through the .bib file (APA)
    assert has(text, "Dantzig & Ramser (1959)")
    # Greek typography
    assert has(text, "«ένα πρόβλημα") and has(text, "“αδύνατο”")


def test_novel_end_to_end(novel: Path) -> None:
    result = build(load_config(novel), keep_typst=True)
    assert result.output is not None
    text = pdf_text(result.output)
    assert has(text, "ΚΕΦΑΛΑΙΟ Α΄") and has(text, "ΚΕΦΑΛΑΙΟ Β΄")
    assert has(text, "ΣΠΗΛΙΟΣ ΔΗΜΑΚΟΠΟΥΛΟΣ")  # el-upper on the title page
    assert result.output.with_suffix(".typ").is_file()


@pytest.mark.parametrize("template", ["novel", "classic", "sepia", "clean", "academic", "thesis"])
def test_every_template_compiles(tmp_path: Path, template: str) -> None:
    project = make_project(
        tmp_path,
        f"title: Δοκιμή\nauthor: Συγγραφέας\ntemplate: {template}\ntoc: true\n",
        {
            "chapters/01.md": '# Πρώτο\n\nΚείμενο "με" εισαγωγικά.\n\n## Ενότητα\n\n'
            "| α | β |\n|---|---|\n| 1 | 2 |\n\nTable: Πίνακας {#tbl:a}\n\nΔες [-@tbl:a].",
            "chapters/02.md": "# Δεύτερο\n\n$$x^2$$ (eq:x)\n\nΗ @eq:x.\n\n---\n\nΤέλος.",
        },
    )
    result = build(load_config(project))
    assert result.output is not None and len(PdfReader(result.output).pages) >= 3


def test_pdfa(thesis: Path) -> None:
    cfg = load_config(thesis)
    cfg.pdf_standard = "a-2b"
    result = build(cfg)
    assert result.output is not None
    assert b"pdfaid" in result.output.read_bytes()


def test_parts_and_custom_options(tmp_path: Path) -> None:
    project = make_project(
        tmp_path,
        "title: T\nauthor: A\nfont: DejaVu Serif\nfont_size: 11pt\npaper_color: '#fafafa'\n"
        "chapter_numbering: words\npage_size: 6x9in\nlanguage: en\n",
        {"chapters/01.md": "# Part one {.part}\n\n# Chapter\n\nText."},
    )
    text = pdf_text(build(load_config(project)).output)  # type: ignore[arg-type]
    assert has(text, "PART ONE") and has(text, "CHAPTER ONE")


def test_generated_source_is_deterministic(thesis: Path) -> None:
    cfg = load_config(thesis)
    assert generate_typst(cfg)[0] == generate_typst(cfg)[0]


def test_typst_errors_are_reported() -> None:
    with pytest.raises(BuildError, match="unknown variable"):
        compile_typst("#nonexistent", Path.cwd())
