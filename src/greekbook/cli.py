"""Command-line interface.

``greekbook`` on its own opens a numbered menu (or, when double-clicked, the app
in the browser), so nobody needs to learn commands. Everything else is for
people who like terminals: ``new``, ``build``, ``watch``, ``validate``, …
"""

from __future__ import annotations

import argparse
import difflib
import io
import itertools
import os
import re
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Sequence
from pathlib import Path
from typing import Any, NoReturn

from . import __version__
from .build import BuildError, build, generate_typst
from .config import TEMPLATES, ConfigError, load_config
from .projects import remember

STARTERS = Path(__file__).parent / "starters"

CR = chr(13)  # carriage return: redraw the spinner line in place
_USE_COLOR = sys.stdout.isatty() and os.environ.get("NO_COLOR") is None


def _c(code: str, text: str) -> str:
    return f"\033[{code}m{text}\033[0m" if _USE_COLOR else text


def ok(msg: str) -> None:
    print(_c("32", "✓ ") + msg)


def warn(msg: str) -> None:
    print(_c("33", "! ") + msg)


def fail(msg: str) -> None:
    print(_c("31", "✗ ") + msg, file=sys.stderr)


class Spinner:
    """«⠋ Στοιχειοθεσία…» while something slow runs (only in a real terminal)."""

    def __init__(self, text: str) -> None:
        self.text = text
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def __enter__(self) -> Spinner:
        if sys.stdout.isatty():
            self._thread = threading.Thread(target=self._spin, daemon=True)
            self._thread.start()
        return self

    def _spin(self) -> None:
        for frame in itertools.cycle("⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"):
            print(f"{CR}{_c('36', frame)} {self.text}", end="", flush=True)
            if self._stop.wait(0.08):
                break
        print(CR + " " * (len(self.text) + 4) + CR, end="", flush=True)

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join()


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
    ok(f"Δημιουργήθηκε νέα εργασία ({args.template}) στο {target}")
    remember(target)
    _next_steps(target)
    return 0


def _next_steps(target: Path) -> None:
    print("\n  Επόμενα βήματα:")
    print(f"    greekbook app {target}     ← γράψε με ζωντανή προεπισκόπηση")
    print(f"    greekbook build {target}   ← φτιάξε το PDF\n")


def cmd_import(args: argparse.Namespace) -> int:
    from .docx_import import ImportError_, import_docx

    target = Path(args.directory) if args.directory else Path(Path(args.docx).stem)
    try:
        warnings = import_docx(Path(args.docx), target, args.template)
    except ImportError_ as exc:
        fail(str(exc))
        return 1
    for w in warnings:
        warn(w)
    ok(f"Εισαγωγή του {args.docx} στο {target}")
    remember(target)
    _next_steps(target)
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
        with Spinner("Στοιχειοθεσία…"):
            result = build(
                cfg, Path(args.output) if args.output else None, keep_typst=args.keep_typst
            )
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


def cmd_serve(args: argparse.Namespace) -> int:
    from .server import serve

    root = _project(args.project)
    try:
        load_config(root)
    except ConfigError as exc:
        fail(str(exc))
        return 1
    try:
        serve(root, args.port, open_browser=not args.no_browser)
    except OSError as exc:
        fail(f"Δεν ξεκίνησε ο server στη θύρα {args.port}: {exc}")
        return 1
    return 0


def cmd_app(args: argparse.Namespace) -> int:
    from .server import run_app

    project = None
    if args.project:
        project = _project(args.project)
        try:
            load_config(project)
        except ConfigError as exc:
            fail(str(exc))
            return 1
    run_app(project, args.port, open_browser=not args.no_browser)
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
# the menu (`greekbook` with no arguments)
# ---------------------------------------------------------------------------


def _ask(question: str, default: str = "") -> str:
    hint = f" [{default}]" if default else ""
    try:
        answer = input(f"  {question}{hint}: ").strip()
    except EOFError:
        answer = ""
    return answer or default


def _yes(question: str, default: bool = True) -> bool:
    answer = _ask(question + (" (Ν/ο)" if default else " (ν/Ο)")).lower()
    if not answer:
        return default
    return answer[0] in "νny"


def _menu_create(kind: str) -> Path | None:
    from .projects import create_project, default_workspace, unique_folder

    print()
    title = _ask("Τίτλος")
    if not title:
        warn("Χρειάζεται τίτλος· μπορείς να τον αλλάξεις αργότερα.")
        return None
    author = _ask("Το όνομά σου")
    thesis: dict[str, str] = {}
    if kind == "thesis":
        thesis["institution"] = _ask("Πανεπιστήμιο")
        thesis["department"] = _ask("Τμήμα")
        thesis["supervisor"] = _ask("Επιβλέπων/ουσα (Enter για παράλειψη)")
    example = _yes("Να ξεκινήσει με πλήρες παράδειγμα (εικόνες, πίνακες, παραπομπές);", False)
    workspace = default_workspace()
    workspace.mkdir(parents=True, exist_ok=True)
    target = unique_folder(workspace, title)
    with Spinner("Δημιουργία…"):
        create_project(target, kind, title, author, example=example, thesis=thesis)
    ok(f"Η εργασία δημιουργήθηκε στο {target}")
    return target


def _menu_import() -> Path | None:
    from .docx_import import ImportError_, import_docx
    from .projects import default_workspace, unique_folder

    print("\n  Σύρε το αρχείο Word μέσα σε αυτό το παράθυρο (ή γράψε τη διαδρομή του)")
    print("  και πάτα Enter.")
    raw = _ask("Αρχείο .docx").strip().strip('"').strip("'").strip()
    if not raw:
        return None
    source = Path(raw).expanduser()
    if not source.is_file():
        fail(f"Δεν βρέθηκε το αρχείο {source}")
        return None
    target = unique_folder(default_workspace(), source.stem)
    try:
        with Spinner("Εισαγωγή…"):
            warnings = import_docx(source, target)
    except ImportError_ as exc:
        fail(str(exc))
        return None
    for w in warnings:
        warn(w)
    ok(f"Το έγγραφο έγινε εργασία στο {target}")
    remember(target)
    return target


def interactive_menu() -> int:
    """Numbered menu for people who don't know (or want) any commands."""
    from .server import run_app

    print()
    print(f"  {_c('1', 'greekbook')} · ελληνικά βιβλία και πτυχιακές, χωρίς Word και χωρίς LaTeX")
    print()
    print("  Τι θέλεις να κάνεις;")
    print()
    options = [
        ("1", "Άνοιγμα της εφαρμογής στον browser", "προτείνεται"),
        ("2", "Νέα πτυχιακή ή διπλωματική", ""),
        ("3", "Νέο βιβλίο", ""),
        ("4", "Νέες σημειώσεις ή άρθρο", ""),
        ("5", "Εισαγωγή από Word (.docx)", ""),
        ("6", "Όλες οι εντολές (για προχωρημένους)", ""),
        ("0", "Έξοδος", ""),
    ]
    for key, label, note in options:
        extra = f"  {_c('2', '(' + note + ')')}" if note else ""
        print(f"    {_c('36', key)}  {label}{extra}")
    print()
    choice = _ask("Επιλογή", "1")
    project: Path | None = None
    if choice == "0":
        return 0
    if choice == "6":
        build_parser().print_help()
        return 0
    if choice in ("2", "3", "4"):
        project = _menu_create({"2": "thesis", "3": "book", "4": "notes"}[choice])
        if project is None:
            return 1
    elif choice == "5":
        project = _menu_import()
        if project is None:
            return 1
    elif choice != "1":
        fail(f"Δεν υπάρχει η επιλογή «{choice}». Γράψε έναν αριθμό από 0 έως 6.")
        return 1
    run_app(project)
    return 0


# ---------------------------------------------------------------------------
# argument parsing (in Greek)
# ---------------------------------------------------------------------------

_ARGPARSE_GREEK = [
    (re.compile(r"invalid choice: '([^']*)' \(choose from (.*)\)"), "invalid"),
    (re.compile(r"the following arguments are required: (.*)"), "Λείπει το όρισμα: {0}"),
    (re.compile(r"unrecognized arguments: (.*)"), "Δεν αναγνωρίζω: {0}"),
    (re.compile(r"argument (\S+): expected one argument"), "Το {0} θέλει μια τιμή μετά."),
    (
        re.compile(r"argument (\S+): invalid (\w+) value: '([^']*)'"),
        "Μη έγκυρη τιμή «{2}» για το {0}.",
    ),
]


class _GreekFormatter(argparse.RawDescriptionHelpFormatter):
    def add_usage(self, usage: str | None, actions: Any, groups: Any, prefix: str | None = None
                  ) -> None:  # fmt: skip
        super().add_usage(usage, actions, groups, prefix="Χρήση: " if prefix is None else prefix)


class GreekParser(argparse.ArgumentParser):
    """argparse with Greek messages and «μήπως εννοείς…;» suggestions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("formatter_class", _GreekFormatter)
        kwargs.setdefault("add_help", False)
        super().__init__(*args, **kwargs)
        self._positionals.title = "ορίσματα"
        self._optionals.title = "επιλογές"
        self.add_argument("-h", "--help", action="help", help="εμφάνιση αυτής της βοήθειας")

    def error(self, message: str) -> NoReturn:
        text = message
        for pattern, template in _ARGPARSE_GREEK:
            m = pattern.search(message)
            if not m:
                continue
            if template == "invalid":
                wrong = m.group(1)
                choices = [c.strip(" '") for c in m.group(2).split(",")]
                close = difflib.get_close_matches(wrong, choices, n=1, cutoff=0.5)
                text = f"Άγνωστη επιλογή «{wrong}»."
                if close:
                    text += f" Μήπως εννοείς «{close[0]}»;"
                else:
                    text += f" Διαθέσιμες: {', '.join(choices)}."
            else:
                text = template.format(*m.groups())
            break
        fail(text)
        print(f"  Βοήθεια: {self.prog} --help", file=sys.stderr)
        raise SystemExit(2)


EPILOG = """\
Παραδείγματα:
  greekbook                          μενού με επιλογές (για όλους)
  greekbook app                      η εφαρμογή στον browser
  greekbook new ptyxiaki -t thesis   νέα πτυχιακή στον φάκελο «ptyxiaki»
  greekbook build ptyxiaki --pdfa    PDF/A για το αποθετήριο
  greekbook import ergasia.docx      μετατροπή εγγράφου Word

Τεκμηρίωση: https://spiliosdimakopoulos.github.io/greekbook/
"""


def build_parser() -> argparse.ArgumentParser:
    parser = GreekParser(
        prog="greekbook",
        description="Markdown → καλαίσθητα ελληνικά βιβλία και πτυχιακές (PDF, PDF/A, EPUB).",
        epilog=EPILOG,
    )
    parser.add_argument(
        "--version", action="version", version=f"greekbook {__version__}", help="η έκδοση"
    )
    parser.add_argument("--debug", action="store_true", help="τεχνικές λεπτομέρειες στα σφάλματα")
    sub = parser.add_subparsers(
        dest="command", metavar="ΕΝΤΟΛΗ", title="εντολές", parser_class=GreekParser
    )

    p = sub.add_parser("app", help="η εφαρμογή στον browser (αρχική οθόνη ή μια εργασία)")
    p.add_argument("project", nargs="?", help="φάκελος εργασίας (προαιρετικό)")
    p.add_argument("--port", type=int, default=8420, help=argparse.SUPPRESS)
    p.add_argument("--no-browser", action="store_true", help="μην ανοίξεις browser")
    p.set_defaults(func=cmd_app)

    p = sub.add_parser("new", help="νέα εργασία από έτοιμο παράδειγμα")
    p.add_argument("directory", help="φάκελος της νέας εργασίας")
    p.add_argument(
        "-t",
        "--template",
        choices=sorted(p.name for p in STARTERS.iterdir() if p.is_dir()),
        default="thesis",
        help="thesis (πτυχιακή) ή novel (βιβλίο)",
    )
    p.set_defaults(func=cmd_new)

    p = sub.add_parser("import", help="εισαγωγή εγγράφου Word (.docx)")
    p.add_argument("docx", help="το αρχείο .docx")
    p.add_argument("directory", nargs="?", help="φάκελος της νέας εργασίας")
    p.add_argument("-t", "--template", choices=TEMPLATES, default="thesis", help="πρότυπο")
    p.set_defaults(func=cmd_import)

    p = sub.add_parser("build", help="δημιουργία PDF (και EPUB)")
    p.add_argument("project", nargs="?", default=".", help="φάκελος ή book.yaml (προεπιλογή: .)")
    p.add_argument("-o", "--output", help="αρχείο εξόδου")
    p.add_argument("--epub", action="store_true", help="δημιουργία και EPUB")
    p.add_argument("--pdfa", action="store_true", help="PDF/A-2b για ιδρυματικά αποθετήρια")
    p.add_argument("--keep-typst", action="store_true", help="κράτα και το παραγόμενο .typ")
    p.add_argument("--typst-only", action="store_true", help="μόνο το .typ, χωρίς PDF")
    p.add_argument("--open", action="store_true", help="άνοιξε το PDF στο τέλος")
    p.set_defaults(func=cmd_build)

    p = sub.add_parser("watch", help="νέο PDF σε κάθε αποθήκευση (με δικό σου editor)")
    p.add_argument("project", nargs="?", default=".", help="φάκελος εργασίας")
    p.add_argument("--interval", type=float, default=0.7, help=argparse.SUPPRESS)
    p.set_defaults(func=cmd_watch)

    p = sub.add_parser("serve", help="ο editor μιας εργασίας (ίδιο με «app ΦΑΚΕΛΟΣ»)")
    p.add_argument("project", nargs="?", default=".", help="φάκελος εργασίας")
    p.add_argument("--port", type=int, default=8420, help=argparse.SUPPRESS)
    p.add_argument("--no-browser", action="store_true", help="μην ανοίξεις browser")
    p.set_defaults(func=cmd_serve)

    p = sub.add_parser("validate", help="έλεγχος κειμένου, παραπομπών και εικόνων")
    p.add_argument("project", nargs="?", default=".", help="φάκελος εργασίας")
    p.add_argument("--strict", action="store_true", help="αποτυχία και στις προειδοποιήσεις")
    p.set_defaults(func=cmd_validate)

    p = sub.add_parser("doctor", help="έλεγχος ότι όλα είναι σωστά εγκατεστημένα")
    p.set_defaults(func=cmd_doctor)

    p = sub.add_parser("templates", help="τα διαθέσιμα πρότυπα")
    p.set_defaults(func=cmd_templates)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    args_list = list(sys.argv[1:] if argv is None else argv)
    debug = "--debug" in args_list
    try:
        if not [a for a in args_list if a != "--debug"]:
            # Double-clicked app (frozen) or a pipe: straight to the browser app.
            if getattr(sys, "frozen", False) or not sys.stdin.isatty():
                from .server import run_app

                run_app()
                return 0
            return interactive_menu()
        args = build_parser().parse_args(args_list)
        code: int = args.func(args)
        return code
    except KeyboardInterrupt:
        print()
        return 130
    except Exception as exc:  # last resort: never show a traceback to a writer
        if debug:
            raise
        fail(f"Κάτι πήγε στραβά: {exc}")
        print(
            "  Αν επαναλαμβάνεται, τρέξε ξανά με --debug και άνοιξε ένα θέμα στο\n"
            "  https://github.com/SpiliosDimakopoulos/greekbook/issues",
            file=sys.stderr,
        )
        return 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
