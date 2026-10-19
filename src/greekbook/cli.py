"""Command-line interface: ``greekbook new | build | watch | validate | doctor``."""

from __future__ import annotations

import argparse
import io
import os
import shutil
import subprocess
import sys
import time
from collections.abc import Sequence
from pathlib import Path

from . import __version__
from .build import BuildError, build, generate_typst
from .config import TEMPLATES, ConfigError, load_config

STARTERS = Path(__file__).parent / "starters"

_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def ok(msg: str) -> None:
    print(_c("32", "✓ ") + msg)


def warn(msg: str) -> None:
    print(_c("33", "! ") + msg)


def fail(msg: str) -> None:
    print(_c("31", "✗ ") + msg, file=sys.stderr)


def _project(path: str) -> Path:
    p = Path(path)
    return p.parent if p.name == "book.yaml" else p


# ---------------------------------------------------------------------------
# commands
# ---------------------------------------------------------------------------


def cmd_new(args: argparse.Namespace) -> int:
    target = Path(args.directory)
    if target.exists() and any(target.iterdir()):
        fail(f"Ο φάκελος {target} υπάρχει ήδη και δεν είναι άδειος.")
        return 1
    starter = STARTERS / args.template
    shutil.copytree(starter, target, dirs_exist_ok=True)
    ok(f"Δημιουργήθηκε νέο project ({args.template}) στο {target}")
    print(f"\n  cd {target}\n  greekbook build\n")
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    try:
        cfg = load_config(_project(args.project))
        if args.pdfa:
            cfg.pdf_standard = "a-2b"
        if args.typst_only:
            source, diagnostics = generate_typst(cfg)
            out = Path(args.output) if args.output else cfg.output_path.with_suffix(".typ")
            out.write_text(source, encoding="utf-8")
            for d in diagnostics:
                warn(str(d))
            ok(f"Typst: {out}")
            return 0
        result = build(cfg, Path(args.output) if args.output else None, keep_typst=args.keep_typst)
        for d in result.diagnostics:
            warn(str(d))
        assert result.output is not None
        ok(f"PDF: {result.output}  ({result.seconds:.1f}s)")
        if args.epub:
            from .epub import build_epub

            ok(f"EPUB: {build_epub(cfg, result.output)}")
        if args.open:
            _open(result.output)
    except (ConfigError, BuildError) as exc:
        fail(str(exc))
        return 1
    return 0


def _sources(root: Path) -> dict[Path, float]:
    mtimes: dict[Path, float] = {}
    for p in root.rglob("*"):
        if p.is_file() and p.suffix.lower() in {
            ".md", ".yaml", ".yml", ".bib", ".csl", ".png", ".jpg", ".jpeg", ".svg",
        }:  # fmt: skip
            mtimes[p] = p.stat().st_mtime
    return mtimes


def cmd_watch(args: argparse.Namespace) -> int:
    root = _project(args.project)
    print(f"Παρακολουθώ το {root.resolve()} — Ctrl+C για έξοδο.")
    seen: dict[Path, float] = {}
    try:
        while True:
            current = _sources(root)
            if current != seen:
                seen = current
                try:
                    cfg = load_config(root)
                    result = build(cfg)
                    ok(f"{time.strftime('%H:%M:%S')}  {result.output}  ({result.seconds:.1f}s)")
                    for d in result.diagnostics:
                        warn(str(d))
                except (ConfigError, BuildError) as exc:
                    fail(f"{time.strftime('%H:%M:%S')}  {exc}")
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print()
        return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from .lint import lint_project

    try:
        cfg = load_config(_project(args.project))
    except ConfigError as exc:
        fail(str(exc))
        return 1
    issues = lint_project(cfg)
    for issue in issues:
        (fail if issue.level == "error" else warn)(str(issue))
    errors = sum(i.level == "error" for i in issues)
    if not issues:
        ok("Δεν βρέθηκαν προβλήματα.")
    else:
        print(f"\n{errors} σφάλματα, {len(issues) - errors} προειδοποιήσεις.")
    return 1 if errors or (args.strict and issues) else 0


def cmd_doctor(_args: argparse.Namespace) -> int:
    import typst

    from .build import FONTS_DIR, compile_typst

    status = 0
    ok(f"greekbook {__version__}, Python {sys.version.split()[0]}")
    families = set(typst.Fonts(include_system_fonts=False, font_paths=[str(FONTS_DIR)]).families())
    for family in ("Libertinus Serif", "New Computer Modern", "Liberation Serif",
                   "Liberation Sans", "DejaVu Sans Mono"):  # fmt: skip
        if family in families:
            ok(f"γραμματοσειρά {family}")
        else:
            fail(f"λείπει η γραμματοσειρά {family}")
            status = 1
    try:
        compile_typst(
            '#import "@local/greekbook:0.2.0": *\n#el-upper[Δοκιμή] #mi("x^2")', Path.cwd()
        )
        ok("Typst, πρότυπα και μαθηματικά (LaTeX) λειτουργούν")
    except BuildError as exc:
        fail(f"αποτυχία Typst: {exc}")
        status = 1
    return status


def cmd_templates(_args: argparse.Namespace) -> int:
    descriptions = {
        "novel": "Λογοτεχνία: Libertinus, κεφάλαια Α΄ Β΄, κεφαλίδες με τίτλο κεφαλαίου",
        "classic": "Λογοτεχνία: Computer Modern, «Κεφάλαιο Πρώτο», κεφάλαια σε μονή σελίδα",
        "sepia": "Λογοτεχνία σε κρεμ χαρτί για οθόνη",
        "clean": "Μοντέρνο sans-serif για οδηγούς, εγχειρίδια, τεκμηρίωση",
        "academic": "Άρθρα και σημειώσεις: Computer Modern, αρίθμηση 1.1",
        "thesis": "Πτυχιακή/διπλωματική: εξώφυλλο, δήλωση, περιλήψεις, κατάλογοι",
    }
    for name in TEMPLATES:
        print(f"  {_c('1', name.ljust(9))} {descriptions[name]}")
    return 0


def _open(path: Path) -> None:
    if sys.platform.startswith("win"):
        os.startfile(path)
    else:
        subprocess.run(["open" if sys.platform == "darwin" else "xdg-open", str(path)], check=False)


# ---------------------------------------------------------------------------
# argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="greekbook",
        description="Markdown → καλαίσθητα ελληνικά βιβλία και πτυχιακές (PDF, PDF/A, EPUB).",
    )
    parser.add_argument("--version", action="version", version=f"greekbook {__version__}")
    sub = parser.add_subparsers(dest="command", required=True, metavar="ΕΝΤΟΛΗ")

    p = sub.add_parser("new", help="δημιουργία νέου project από πρότυπο")
    p.add_argument("directory", help="φάκελος του νέου project")
    p.add_argument(
        "-t",
        "--template",
        choices=sorted(p.name for p in STARTERS.iterdir() if p.is_dir()),
        default="thesis",
    )
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("build", help="δημιουργία PDF (και EPUB)")
    p.add_argument("project", nargs="?", default=".", help="φάκελος ή book.yaml (προεπιλογή: .)")
    p.add_argument("-o", "--output", help="αρχείο εξόδου")
    p.add_argument("--epub", action="store_true", help="δημιουργία και EPUB")
    p.add_argument("--pdfa", action="store_true", help="PDF/A-2b για ιδρυματικά αποθετήρια")
    p.add_argument("--keep-typst", action="store_true", help="κράτα και το παραγόμενο .typ")
    p.add_argument("--typst-only", action="store_true", help="μόνο το .typ, χωρίς PDF")
    p.add_argument("--open", action="store_true", help="άνοιξε το PDF στο τέλος")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("watch", help="αυτόματο build σε κάθε αλλαγή")
    p.add_argument("project", nargs="?", default=".")
    p.add_argument("--interval", type=float, default=0.7, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("validate", help="έλεγχος κειμένου, παραπομπών και εικόνων")
    p.add_argument("project", nargs="?", default=".")
    p.add_argument("--strict", action="store_true", help="αποτυχία και στις προειδοποιήσεις")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("doctor", help="έλεγχος εγκατάστασης")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("templates", help="λίστα διαθέσιμων προτύπων")
    p.set_defaults(func=cmd_templates)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    args = build_parser().parse_args(argv)
    code: int = args.func(args)
    return code


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
