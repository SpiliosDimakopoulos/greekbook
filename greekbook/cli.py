# -*- coding: utf-8 -*-
"""
Command-line interface for greekbook.

Entry point (defined in pyproject.toml):
    greekbook = "greekbook.cli:main"

Subcommands:
    greekbook build <book_dir>      Build a PDF from a book.yaml project
    greekbook themes                List all available themes
    greekbook init [<book_dir>]     Scaffold a new book project (book.yaml + parts/)
    greekbook validate <book_dir>   Check project for errors without building
    greekbook doctor                Check installation health
    greekbook serve [<book_dir>]    Open local web UI in browser
"""
import argparse
import sys
import textwrap
from pathlib import Path

from . import __version__
from .config import ConfigError, load_config
from .themes import available_themes, get_theme


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _die(msg: str) -> None:
    print(f"greekbook error: {msg}", file=sys.stderr)
    sys.exit(1)


BOOK_YAML_TEMPLATE = """\
# greekbook — book.yaml
# Αλλαξε τα παρακάτω πεδία για το βιβλίο σου.

title: Τίτλος Βιβλίου
author: Όνομα Συγγραφέα
# subtitle: Προαιρετικός Υπότιτλος  # αφαίρεσε το # για να ενεργοποιήσεις

language: el        # el = ελληνικά, en = αγγλικά
theme: {default_theme}        # {theme_choices}
page_size: A5       # A4 | A5 | A6 | B5 | LETTER | 6x9in | 148x210mm ...

parts_dir: parts    # φάκελος με τα .md αρχεία των μερών
output: book.pdf    # όνομα αρχείου εξόδου
""".format(default_theme="sepia", theme_choices=" | ".join(available_themes()))

def _make_part_stub(part_title: str) -> str:
    return (
        f"# {part_title}\n\n"
        "Γράψε εδώ το κείμενο.\n\n"
        "Μπορείς να χρησιμοποιήσεις *πλάγια* και **έντονα**, "
        "ελληνικά εισαγωγικά «αυτόματα»,\n"
        "και διαχωριστικό σκηνής με μια γραμμή που περιέχει μόνο ---.\n\n"
        "---\n\n"
        "Η επόμενη σκηνή ξεκινά εδώ.\n"
    )


def _make_book_yaml(title: str, author: str, subtitle: str,
                    language: str, theme: str, page_size: str) -> str:
    lines = [
        "# greekbook — book.yaml",
        "",
        f"title: {title}",
        f"author: {author}",
    ]
    if subtitle:
        lines.append(f"subtitle: {subtitle}")
    else:
        lines.append("# subtitle: Προαιρετικός Υπότιτλος")
    lines += [
        "",
        f"language: {language}    # el = ελληνικά, en = αγγλικά",
        f"theme: {theme}        # {' | '.join(available_themes())}",
        f"page_size: {page_size}      # A4 | A5 | A6 | B5 | LETTER | 6x9in | 148x210mm ...",
        "",
        "parts_dir: parts    # φάκελος με τα .md αρχεία των μερών",
        "output: book.pdf    # όνομα αρχείου εξόδου",
        "",
    ]
    return "\n".join(lines)


def _ask(prompt: str, default: str = "") -> str:
    """Prompt the user for input, showing the default in brackets."""
    display = f"{prompt} [{default}]: " if default else f"{prompt}: "
    try:
        value = input(display).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        sys.exit(0)
    return value if value else default


def _choose(prompt: str, options: list, default: str) -> str:
    """Prompt the user to choose from a list of options."""
    opts_str = " / ".join(f"[{o}]" if o == default else o for o in options)
    while True:
        value = _ask(f"{prompt} ({opts_str})", default)
        if value in options:
            return value
        print(f"  Παρακαλώ επέλεξε ένα από: {', '.join(options)}")


def _open_pdf(path: Path) -> None:
    """Open a PDF with the system default viewer, cross-platform."""
    import subprocess
    import platform
    system = platform.system()
    try:
        if system == "Darwin":
            subprocess.run(["open", str(path)], check=True)
        elif system == "Windows":
            # os.startfile is Windows-only; use subprocess for consistency
            subprocess.run(["start", "", str(path)], shell=True, check=True)
        else:
            # Linux / BSD — try xdg-open, fall back gracefully
            result = subprocess.run(
                ["xdg-open", str(path)],
                stderr=subprocess.DEVNULL,
            )
            if result.returncode != 0:
                print(f"  (δεν ήταν δυνατό το άνοιγμα αυτόματα — άνοιξε χειροκίνητα: {path})")
    except FileNotFoundError:
        print(f"  (δεν βρέθηκε πρόγραμμα για το άνοιγμα PDF — άνοιξε χειροκίνητα: {path})")
    except Exception:
        pass  # silent — the build succeeded; the open is a bonus


# ---------------------------------------------------------------------------
# Subcommand: build
# ---------------------------------------------------------------------------

def cmd_build(args: argparse.Namespace) -> None:
    book_dir = Path(args.book_dir).resolve()
    yaml_path = book_dir / "book.yaml"
    if not yaml_path.is_file():
        _die(
            f"Δεν βρέθηκε το book.yaml στο '{book_dir}'.\n"
            f"  Τρέξε:  greekbook init \"{book_dir}\"  για να δημιουργήσεις σκελετό."
        )

    try:
        config = load_config(str(yaml_path))
    except ConfigError as e:
        _die(str(e))

    try:
        # Import here so startup is fast even if reportlab is slow to import
        from .builder import build_book
        output = build_book(config, quiet=args.quiet)
        if not args.quiet:
            print(f"✓ PDF: {output}")
        if args.open:
            _open_pdf(output)
    except ConfigError as e:
        _die(str(e))
    except Exception as e:
        _die(f"Αποτυχία build: {e}")


# ---------------------------------------------------------------------------
# Subcommand: themes
# ---------------------------------------------------------------------------

def cmd_themes(_args: argparse.Namespace) -> None:
    print("Διαθέσιμα themes:")
    for name in available_themes():
        description = getattr(get_theme(name), "description", "")
        if description:
            print(f"  {name} — {description}")
        else:
            print(f"  {name}")


# ---------------------------------------------------------------------------
# Subcommand: init
# ---------------------------------------------------------------------------

def cmd_init(args: argparse.Namespace) -> None:
    book_dir = Path(args.book_dir).resolve()

    # ── Guard: existing project ──────────────────────────────────────────────
    yaml_path = book_dir / "book.yaml"
    if yaml_path.exists() and not args.force:
        print(f"  Το project υπάρχει ήδη στο '{book_dir}'.")
        print(f"  Χρησιμοποίησε --force για να αντικατασταθούν τα αρχεία.")
        return

    # ── Interactive wizard (only when attached to a real terminal) ───────────
    interactive = sys.stdin.isatty() and sys.stdout.isatty()

    if interactive:
        print()
        print("━━  greekbook init  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print("Απάντησε στις ερωτήσεις (Enter = προεπιλογή σε [αγκύλες]).")
        print()

        # Basic metadata
        title    = _ask("Τίτλος βιβλίου", "Ο Τίτλος μου")
        author   = _ask("Συγγραφέας",     "Το Όνομά μου")
        subtitle = _ask("Υπότιτλος (αφήσε κενό αν δεν θες)", "")

        print()
        # Language
        language = _choose("Γλώσσα", ["el", "en"], "el")

        # Theme — show a brief description next to each option
        themes = available_themes()
        print()
        print("Διαθέσιμα themes:")
        for t in themes:
            desc = getattr(get_theme(t), "description", "")
            tag  = " ← προεπιλογή" if t == "sepia" else ""
            print(f"  {t:10s} — {desc}{tag}")
        theme = _choose("Theme", themes, "sepia")

        # Page size
        print()
        page_size = _choose(
            "Μέγεθος σελίδας",
            ["A5", "A4", "A6", "B5", "LETTER", "6x9in"],
            "A5",
        )

        # Number of parts
        print()
        while True:
            raw = _ask("Πόσα Μέρη έχει το βιβλίο;", "1")
            try:
                n_parts = int(raw)
                if 1 <= n_parts <= 99:
                    break
            except ValueError:
                pass
            print("  Δώσε έναν αριθμό από 1 έως 99.")

        # Part titles
        part_titles = []
        if n_parts == 1:
            part_titles.append(_ask("Τίτλος Μέρους 1", "Μέρος Πρώτο"))
        else:
            print()
            print(f"Δώσε τίτλο για κάθε Μέρος (Enter = αυτόματος τίτλος):")
            greek_ordinals = [
                "Πρώτο", "Δεύτερο", "Τρίτο", "Τέταρτο", "Πέμπτο",
                "Έκτο", "Έβδομο", "Όγδοο", "Ένατο", "Δέκατο",
            ]
            for i in range(n_parts):
                default_title = (
                    f"Μέρος {greek_ordinals[i]}"
                    if i < len(greek_ordinals)
                    else f"Μέρος {i + 1}"
                )
                part_titles.append(_ask(f"  Τίτλος Μέρους {i + 1}", default_title))

        print()
        print("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
        print()

    else:
        # Non-interactive fallback (scripts, CI): use sensible defaults silently
        title      = "Τίτλος Βιβλίου"
        author     = "Όνομα Συγγραφέα"
        subtitle   = ""
        language   = "el"
        theme      = "sepia"
        page_size  = "A5"
        n_parts    = 1
        part_titles = ["Μέρος Πρώτο"]

    # ── Write files ──────────────────────────────────────────────────────────
    parts_dir = book_dir / "parts"
    parts_dir.mkdir(parents=True, exist_ok=True)

    yaml_content = _make_book_yaml(title, author, subtitle, language, theme, page_size)
    yaml_path.write_text(yaml_content, encoding="utf-8")
    print(f"  δημιουργήθηκε: {yaml_path}")

    greek_caps = "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"
    for i, part_title in enumerate(part_titles):
        prefix = f"{i + 1:02d}"
        # Build a safe ASCII slug from the title for the filename
        slug = _slugify(part_title) or f"meros-{greek_caps[i] if i < len(greek_caps) else i + 1}"
        part_path = parts_dir / f"{prefix}-{slug}.md"
        part_path.write_text(_make_part_stub(part_title), encoding="utf-8")
        print(f"  δημιουργήθηκε: {part_path}")

    print()
    print("Έτοιμο! Επόμενα βήματα:")
    print(f"  1. Γράψε το κείμενό σου στα αρχεία μέσα στο {parts_dir}/")
    print(f"  2. greekbook validate \"{book_dir}\"   # προαιρετικός έλεγχος")
    print(f"  3. greekbook build \"{book_dir}\"")


def _slugify(text: str) -> str:
    """Convert a Greek/Latin title to a safe ASCII filename fragment."""
    import re
    import unicodedata

    # Normalise: decompose accented chars so e.g. 'ό' → 'ο' + combining accent
    text = unicodedata.normalize("NFD", text.lower())
    # Drop combining accent marks (keep base letters)
    text = "".join(ch for ch in text if unicodedata.category(ch) != "Mn")

    _GREEK_LATIN = {
        "α": "a", "β": "v", "γ": "g", "δ": "d", "ε": "e", "ζ": "z",
        "η": "i", "θ": "th", "ι": "i", "κ": "k", "λ": "l", "μ": "m",
        "ν": "n", "ξ": "x", "ο": "o", "π": "p", "ρ": "r", "σ": "s",
        "ς": "s", "τ": "t", "υ": "y", "φ": "f", "χ": "ch", "ψ": "ps",
        "ω": "o",
    }
    result = []
    for ch in text:
        if ch in _GREEK_LATIN:
            result.append(_GREEK_LATIN[ch])
        elif ch.isascii() and (ch.isalnum() or ch in "-_ "):
            result.append(ch)
        # else: drop non-ASCII, non-mappable characters

    slug = "-".join("".join(result).split())   # spaces → single hyphens
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    return slug[:40]  # cap length for sane filenames


# ---------------------------------------------------------------------------
# Subcommand: validate
# ---------------------------------------------------------------------------

def cmd_validate(args: argparse.Namespace) -> None:
    book_dir = Path(args.book_dir).resolve()
    errors: list[str] = []
    warnings: list[str] = []
    ok_items: list[str] = []

    # ── 1. Φάκελος βιβλίου ──────────────────────────────────────────────────
    if not book_dir.exists():
        errors.append(
            f"Ο φάκελος '{book_dir}' δεν υπάρχει.\n"
            f"  → Τρέξε:  greekbook init \"{book_dir}\""
        )
        _print_validate_report(ok_items, warnings, errors, book_dir=book_dir)
        return
    ok_items.append(f"Φάκελος βιβλίου βρέθηκε: {book_dir}")

    # ── 2. book.yaml υπαρξη ─────────────────────────────────────────────────
    yaml_path = book_dir / "book.yaml"
    if not yaml_path.is_file():
        errors.append(
            f"Δεν βρέθηκε το book.yaml μέσα στο '{book_dir}'.\n"
            f"  → Τρέξε:  greekbook init \"{book_dir}\""
        )
        _print_validate_report(ok_items, warnings, errors, book_dir=book_dir)
        return
    ok_items.append("book.yaml βρέθηκε")

    # ── 3. Ανάλυση book.yaml ────────────────────────────────────────────────
    try:
        config = load_config(str(yaml_path))
        ok_items.append(
            f"book.yaml έγκυρο  (τίτλος: \"{config.title}\", "
            f"συγγραφέας: \"{config.author}\")"
        )
    except ConfigError as e:
        errors.append(
            f"Σφάλμα στο book.yaml: {e}\n"
            f"  → Άνοιξε το book.yaml και διόρθωσε το πεδίο που αναφέρεται παραπάνω."
        )
        _print_validate_report(ok_items, warnings, errors, book_dir=book_dir)
        return

    # ── 4. Φάκελος parts ────────────────────────────────────────────────────
    parts_path = config.parts_path
    if not parts_path.is_dir():
        errors.append(
            f"Ο φάκελος μερών δεν υπάρχει: {parts_path}\n"
            f"  → Δημιούργησέ τον:  mkdir -p \"{parts_path}\"\n"
            f"  → Και πρόσθεσε τουλάχιστον ένα αρχείο .md μέσα."
        )
        _print_validate_report(ok_items, warnings, errors, book_dir=book_dir)
        return

    md_files = sorted(parts_path.glob("*.md"))
    if not md_files:
        errors.append(
            f"Δεν βρέθηκαν αρχεία .md μέσα στο {parts_path}.\n"
            f"  → Δημιούργησε ένα αρχείο, π.χ. {parts_path / '01-meros-proto.md'}"
        )
        _print_validate_report(ok_items, warnings, errors, book_dir=book_dir)
        return

    ok_items.append(f"Φάκελος μερών βρέθηκε: {parts_path}")

    # ── 5. Έλεγχος κάθε .md αρχείου ────────────────────────────────────────
    valid_parts = 0
    for md in md_files:
        try:
            text = md.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            errors.append(
                f"Το αρχείο '{md.name}' δεν είναι UTF-8.\n"
                f"  → Άνοιξέ το στον editor σου (π.χ. VS Code) και επέλεξε\n"
                f"     «Save with Encoding → UTF-8» πριν αποθηκεύσεις."
            )
            continue

        if not text.strip():
            warnings.append(
                f"Το αρχείο '{md.name}' είναι εντελώς άδειο και θα παραλειφθεί.\n"
                f"  → Πρόσθεσε περιεχόμενο ή διέγραψέ το αν δεν το χρειάζεσαι."
            )
            continue

        lines = text.split("\n")
        if not lines[0].strip().startswith("#"):
            warnings.append(
                f"Το αρχείο '{md.name}' δεν ξεκινά με τίτλο Μέρους (# Τίτλος).\n"
                f"  → Πρόσθεσε στην πρώτη γραμμή κάτι σαν:  # Μέρος Πρώτο\n"
                f"  → Χωρίς τίτλο το Μέρος θα πάρει αυτόματο όνομα (ΜΕΡΟΣ Α κ.λπ.)."
            )

        valid_parts += 1
        ok_items.append(f"  {md.name} — ΟΚ ({len(text.split())} λέξεις)")

    if valid_parts == 0:
        errors.append(
            "Δεν βρέθηκε κανένα έγκυρο αρχείο .md με περιεχόμενο.\n"
            "  → Πρόσθεσε τουλάχιστον ένα αρχείο .md με κείμενο στον φάκελο parts/."
        )

    # ── 6. Έλεγχος page_size ────────────────────────────────────────────────
    from .config import parse_page_size
    try:
        parse_page_size(config.page_size)
        ok_items.append(f"page_size: {config.page_size} — έγκυρο")
    except ConfigError as e:
        errors.append(str(e) + "\n  → Διόρθωσε το πεδίο page_size στο book.yaml.")

    # ── 7. Έλεγχος output path ──────────────────────────────────────────────
    output_parent = config.output_path.parent
    if not output_parent.exists():
        warnings.append(
            f"Ο φάκελος εξόδου δεν υπάρχει ακόμα: {output_parent}\n"
            f"  → Θα δημιουργηθεί αυτόματα κατά το build — δεν χρειάζεται ενέργεια."
        )
    else:
        ok_items.append(f"Φάκελος εξόδου: {output_parent} — υπάρχει")

    _print_validate_report(ok_items, warnings, errors, book_dir=book_dir)


def _print_validate_report(
    ok_items: list[str],
    warnings: list[str],
    errors: list[str],
    book_dir: "Path | None" = None,
) -> None:
    """Print a structured validate report and exit with appropriate code."""
    print()
    if ok_items:
        print("✓ Εντάξει:")
        for item in ok_items:
            print(f"  {item}")

    if warnings:
        print()
        print("⚠ Προειδοποιήσεις:")
        for w in warnings:
            for i, line in enumerate(w.splitlines()):
                print(f"  {'⚠' if i == 0 else ' '} {line}")

    if errors:
        print()
        print("✗ Σφάλματα:")
        for e in errors:
            for i, line in enumerate(e.splitlines()):
                print(f"  {'✗' if i == 0 else ' '} {line}")
        print()
        print("Το build δεν θα ολοκληρωθεί μέχρι να διορθωθούν τα παραπάνω σφάλματα.")
        sys.exit(1)
    else:
        print()
        build_path = f'"{book_dir}"' if book_dir else "."
        if warnings:
            print("Το project είναι έτοιμο για build (με τις προειδοποιήσεις παραπάνω).")
        else:
            print("✓ Όλα εντάξει! Το project είναι έτοιμο:")
        print(f"  greekbook build {build_path}")
        print()


# ---------------------------------------------------------------------------
# Subcommand: doctor
# ---------------------------------------------------------------------------

def cmd_doctor(_args: argparse.Namespace) -> None:
    import importlib.util
    import shutil

    print("greekbook doctor — έλεγχος εγκατάστασης\n")
    problems = 0

    # Python version
    if sys.version_info >= (3, 9):
        print(f"  ✓ Python {sys.version.split()[0]}")
    else:
        print(f"  ✗ Python {sys.version.split()[0]} — απαιτείται 3.9+")
        problems += 1

    # Required packages
    for pkg, pip_name in [
        ("reportlab", "reportlab"), ("pdfplumber", "pdfplumber"),
        ("yaml", "pyyaml"), ("pyphen", "pyphen"),
    ]:
        if importlib.util.find_spec(pkg) is not None:
            print(f"  ✓ {pip_name} εγκατεστημένο")
        else:
            print(f"  ✗ {pip_name} ΛΕΙΠΕΙ → pip install {pip_name}")
            problems += 1

    # Bundled fonts present
    fonts_dir = Path(__file__).parent / "fonts"
    missing_fonts = []
    for theme_name in available_themes():
        for fname in get_theme(theme_name).font_files.values():
            if not (fonts_dir / fname).exists():
                missing_fonts.append(fname)
    if missing_fonts:
        print(f"  ✗ Λείπουν fonts: {', '.join(sorted(set(missing_fonts)))}")
        problems += 1
    else:
        print(f"  ✓ Όλες οι γραμματοσειρές των themes βρέθηκαν")

    # PDF viewer (used by --open, not fatal)
    import platform
    system = platform.system()
    if system == "Windows":
        # Windows ανοίγει PDF μέσω του "start" του cmd.exe (πάντα διαθέσιμο), όχι ως αναζητούμενο πρόγραμμα.
        print("  ✓ PDF viewer: το --open θα χρησιμοποιήσει το προεπιλεγμένο πρόγραμμα Windows")
    elif system == "Darwin":
        print("  ✓ PDF viewer: το --open θα χρησιμοποιήσει την εντολή 'open' (macOS)")
    else:
        viewer = shutil.which("xdg-open")
        if viewer:
            print(f"  ✓ PDF viewer βρέθηκε ({viewer}) — το --open θα δουλέψει")
        else:
            print("  ⚠ Δεν βρέθηκε xdg-open — το --open δεν θα ανοίξει αυτόματα το PDF (μη κρίσιμο)")

    print()
    if problems:
        print(f"✗ Βρέθηκαν {problems} πρόβλημα/τα. Διόρθωσέ τα και ξανατρέξε `greekbook doctor`.")
        sys.exit(1)
    else:
        print("✓ Όλα εντάξει! Το greekbook είναι έτοιμο για χρήση.")


# ---------------------------------------------------------------------------
# Subcommand: serve
# ---------------------------------------------------------------------------

def cmd_serve(args: argparse.Namespace) -> None:
    from .server import run_server
    book_dir = Path(args.book_dir).resolve()

    # Auto-init silently if no book.yaml exists yet.
    # Force non-interactive so it never prompts the user for input.
    if not (book_dir / "book.yaml").exists():
        book_dir.mkdir(parents=True, exist_ok=True)
        parts_dir = book_dir / "parts"
        parts_dir.mkdir(exist_ok=True)
        yaml_content = (
            "title: Τίτλος Βιβλίου\n"
            "author: Όνομα Συγγραφέα\n"
            "language: el\n"
            "theme: sepia\n"
            "page_size: A5\n"
            "parts_dir: parts\n"
            "output: book.pdf\n"
        )
        (book_dir / "book.yaml").write_text(yaml_content, encoding="utf-8")

    run_server(book_dir, port=args.port, open_browser=not args.no_browser)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        prog="greekbook",
        description="Τυπογραφικό εργαλείο PDF για ελληνική (και αγγλική) πεζογραφία.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Παραδείγματα:
              greekbook init my_novel/           # δημιουργία σκελετού
              greekbook validate my_novel/       # έλεγχος πριν το build
              greekbook build my_novel/          # χτίσε το PDF
              greekbook build my_novel/ --open   # χτίσε και άνοιξε αμέσως
              greekbook themes                   # λίστα θεμάτων
              greekbook doctor                    # έλεγχος εγκατάστασης
              greekbook serve my_novel/           # άνοιγμα web UI
        """),
    )
    parser.add_argument(
        "--version", action="version", version=f"greekbook {__version__}"
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<εντολή>")
    subparsers.required = True

    # --- build ---
    p_build = subparsers.add_parser(
        "build",
        help="Χτίσε το PDF από ένα φάκελο book.yaml",
    )
    p_build.add_argument(
        "book_dir",
        metavar="<book_dir>",
        help="Φάκελος που περιέχει book.yaml και parts/",
    )
    p_build.add_argument(
        "-q", "--quiet",
        action="store_true",
        help="Χωρίς output στη stdout (μόνο errors)",
    )
    p_build.add_argument(
        "-o", "--open",
        action="store_true",
        help="Άνοιγμα του PDF αυτόματα μετά το build",
    )
    p_build.set_defaults(func=cmd_build)

    # --- themes ---
    p_themes = subparsers.add_parser(
        "themes",
        help="Λίστα διαθέσιμων themes",
    )
    p_themes.set_defaults(func=cmd_themes)

    # --- init ---
    p_init = subparsers.add_parser(
        "init",
        help="Δημιουργία σκελετού νέου βιβλίου",
    )
    p_init.add_argument(
        "book_dir",
        metavar="<book_dir>",
        nargs="?",
        default=".",
        help="Φάκελος όπου θα δημιουργηθεί το σκελετό (default: .)",
    )
    p_init.add_argument(
        "--force",
        action="store_true",
        help="Αντικατάσταση υπαρχόντων αρχείων",
    )
    p_init.set_defaults(func=cmd_init)

    # --- validate ---
    p_validate = subparsers.add_parser(
        "validate",
        help="Έλεγχος project χωρίς build — εντοπίζει σφάλματα και προειδοποιήσεις",
    )
    p_validate.add_argument(
        "book_dir",
        metavar="<book_dir>",
        help="Φάκελος που περιέχει book.yaml και parts/",
    )
    p_validate.set_defaults(func=cmd_validate)

    # --- doctor ---
    p_doctor = subparsers.add_parser(
        "doctor",
        help="Έλεγχος εγκατάστασης (dependencies, fonts, PDF viewer)",
    )
    p_doctor.set_defaults(func=cmd_doctor)

    # --- serve ---
    p_serve = subparsers.add_parser(
        "serve",
        help="Άνοιγμα τοπικού web UI (browser) για το project",
    )
    p_serve.add_argument(
        "book_dir", metavar="<book_dir>", nargs="?", default=".",
        help="Φάκελος που περιέχει book.yaml (default: .)",
    )
    p_serve.add_argument("--port", type=int, default=8420, help="TCP port (default: 8420)")
    p_serve.add_argument("--no-browser", action="store_true", help="Μην ανοίξεις browser αυτόματα")
    p_serve.set_defaults(func=cmd_serve)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
