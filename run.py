#!/usr/bin/env python3
"""
Εκκίνηση του greekbook editor.
Χρήση:  python run.py [book_dir] [--port 8420]
"""
import sys
import argparse
from pathlib import Path

# Make the package importable from this directory
sys.path.insert(0, str(Path(__file__).parent))

from greekbook.cli import main

if __name__ == "__main__":
    main()
