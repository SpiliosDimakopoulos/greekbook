"""Assemble the GitHub Pages site in ``_site/``.

* ``mkdocs build`` for the documentation (skipped with ``--no-docs``)
* ``site/demo`` plus the runtime assets the in-browser demo loads: the
  greekbook Python modules (run by Pyodide), the Typst template library and
  mitex (mapped into typst.ts), and the bundled fonts.

    python scripts/build_site.py [--no-docs] [--out _site]
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PKG = ROOT / "src" / "greekbook"
PYTHON_MODULES = ["__init__.py", "config.py", "markdown.py", "typography.py", "build.py"]
FONTS = [
    "LiberationSerif-Regular.ttf", "LiberationSerif-Bold.ttf", "LiberationSerif-Italic.ttf",
    "LiberationSerif-BoldItalic.ttf", "LiberationSans-Regular.ttf", "LiberationSans-Bold.ttf",
    "LiberationSans-Italic.ttf", "LiberationSans-BoldItalic.ttf",
]  # fmt: skip


def build_demo(out: Path) -> None:
    demo = out / "demo"
    shutil.copytree(ROOT / "site" / "demo", demo, dirs_exist_ok=True)
    assets = demo / "assets"
    (assets / "py").mkdir(parents=True, exist_ok=True)
    for name in PYTHON_MODULES:
        shutil.copy2(PKG / name, assets / "py" / name)

    typst_files: list[str] = []
    lib_dir = PKG / "typst" / "packages" / "local" / "greekbook"
    lib = next(lib_dir.iterdir()) / "lib.typ"
    patched = lib.read_text(encoding="utf-8").replace(
        '#import "@preview/mitex:0.2.7"', '#import "/mitex/lib.typ"'
    )
    (assets / "typst" / "greekbook").mkdir(parents=True, exist_ok=True)
    (assets / "typst" / "greekbook" / "lib.typ").write_text(patched, encoding="utf-8")
    typst_files.append("greekbook/lib.typ")
    mitex = PKG / "typst" / "packages" / "preview" / "mitex" / "0.2.7"
    for f in sorted(mitex.rglob("*")):
        if f.is_file() and f.suffix in {".typ", ".wasm"}:
            rel = "mitex/" + f.relative_to(mitex).as_posix()
            (assets / "typst" / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, assets / "typst" / rel)
            typst_files.append(rel)

    (assets / "fonts").mkdir(exist_ok=True)
    for font in FONTS:
        shutil.copy2(PKG / "fonts" / font, assets / "fonts" / font)

    manifest = {"python": PYTHON_MODULES, "typst": typst_files, "fonts": FONTS}
    (assets / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default=str(ROOT / "_site"))
    parser.add_argument("--no-docs", action="store_true")
    args = parser.parse_args()
    out = Path(args.out)
    if out.exists():  # empty it but keep the directory (a dev server may be serving it)
        for child in out.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    if not args.no_docs:
        subprocess.run(
            [sys.executable, "-m", "mkdocs", "build", "--strict", "--site-dir", str(out)],
            cwd=ROOT,
            check=True,
        )
    build_demo(out)
    print(f"site: {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
