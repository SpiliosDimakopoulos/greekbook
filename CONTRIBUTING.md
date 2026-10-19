# Contributing

Thank you for helping! Issues and pull requests are welcome in Greek or English.

## Setup

```console
$ pip install -e ".[dev]"
$ pytest
$ ruff check src tests && ruff format src tests && mypy
```

## Where help is most useful

- **University cover pages.** If your department requires a specific cover or
  declaration, open an issue with the official guidelines (PDF or link).
- **Typographic rules.** Anything a Greek typesetter would notice: spacing,
  abbreviations, numbering, quotes. Please include a reference
  (grammar, style guide, a printed book).
- **Syllabification.** Words the syllabifier gets wrong: add them to the gold
  list in `tests/test_hyphenation.py` with a source for the correct division.

## Layout

| Path | What |
|---|---|
| `src/greekbook/markdown.py` | Markdown → Typst markup |
| `src/greekbook/typography.py` | Quotes, dashes, capitals, numerals |
| `src/greekbook/typst/packages/local/greekbook/*/lib.typ` | Typst templates |
| `src/greekbook/build.py` | Project → Typst document → PDF |
| `src/greekbook/lint.py` | `greekbook validate` |
| `src/greekbook/starters/` | Projects created by `greekbook new` |

Every behaviour change needs a test, and user-visible changes need a line in
`CHANGELOG.md`.
