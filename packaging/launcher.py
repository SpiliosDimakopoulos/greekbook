"""Entry point of the standalone greekbook app (PyInstaller).

Double-clicking the executable runs it without arguments, which opens the
greekbook app in the browser; with arguments it is the normal CLI.
"""

from greekbook.cli import main

raise SystemExit(main())
