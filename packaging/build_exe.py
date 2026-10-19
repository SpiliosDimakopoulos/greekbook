"""Build the standalone greekbook app with PyInstaller.

    pip install pyinstaller && python packaging/build_exe.py

Produces dist/greekbook(.exe): one file, no Python needed. Double-clicked, it
opens the greekbook app in the browser; from a terminal it is the normal CLI.
"""

from __future__ import annotations

import sys
from pathlib import Path

import PyInstaller.__main__

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent


def main() -> None:
    icon = HERE / ("icon.ico" if sys.platform.startswith("win") else "icon.png")
    PyInstaller.__main__.run(
        [
            str(HERE / "launcher.py"),
            "--name=greekbook",
            "--onefile",
            "--console",
            "--noconfirm",
            "--clean",
            f"--icon={icon}",
            "--collect-data=greekbook",
            "--collect-all=typst",
            "--collect-data=docx",
            "--collect-submodules=mdit_py_plugins",
            f"--distpath={ROOT / 'dist'}",
            f"--workpath={ROOT / 'build' / 'pyinstaller'}",
            f"--specpath={ROOT / 'build'}",
        ]
    )


if __name__ == "__main__":
    main()
