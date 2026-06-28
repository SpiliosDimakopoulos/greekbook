#!/bin/sh
set -e

BOOK_DIR="/data/book"
EXAMPLES_DIR="/data/examples"

# First-run: initialise book and copy examples to persistent volume
if [ ! -f "$BOOK_DIR/book.yaml" ]; then
  echo "greekbook: πρώτη εκκίνηση — αρχικοποίηση…"
  mkdir -p "$BOOK_DIR/parts"
  cat > "$BOOK_DIR/book.yaml" << 'YAML'
title: ''
author: ''
subtitle: ''
language: el
theme: sepia
page_size: A5
parts_dir: parts
output: book.pdf
YAML
fi

# Copy bundled examples to volume (only if not already there)
if [ ! -d "$EXAMPLES_DIR" ]; then
  echo "greekbook: αντιγραφή παραδειγμάτων…"
  cp -r /app/examples "$EXAMPLES_DIR"
fi

echo "greekbook: εκκίνηση server στο port 8080…"
exec python run.py serve "$BOOK_DIR" --port 8080 --no-browser
