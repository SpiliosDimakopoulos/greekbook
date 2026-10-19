# Changelog

All notable changes are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/).

## [Unreleased] — 0.2.0

A rewrite on top of [Typst](https://typst.app).

### Added
- Full Markdown: headings, lists, tables, figures, footnotes, block quotes,
  code with syntax highlighting, LaTeX math, citations from `.bib` (APA, IEEE,
  Harvard, Chicago, MLA, Vancouver, custom CSL) and cross-references.
- `thesis` template: cover page, declaration of originality, abstracts,
  outlines, per-chapter numbering, appendices, PDF/A-2b output.
- `novel`, `classic` and `academic` templates; `sepia` and `clean` reworked.
- Greek typography: nested quotes, capitals without accents (ΤΣΑΪ), Greek
  numerals, no-break spaces after abbreviations, number-only references.
- `greekbook new`, `watch`, `validate` (Greek-specific linting), `doctor`, `templates`.
- `greekbook import thesis.docx`: Word documents become projects (chapters, lists,
  tables, images, footnotes).
- `greekbook serve`: local editor with live page preview and lint panel, bound to
  127.0.0.1 with Host and token checks.
- EPUB 3 with soft hyphens from the Greek syllabifier.
- Test suite (unit, end-to-end PDF, property-based), CI on three OSes.

### Changed
- License: plain MIT (the Commons Clause, which forbade selling and made the
  project non open source, was dropped).
- `theme:` is now `template:` and `parts/` is now `chapters/`; old projects still load.
- The syllabifier follows the school-grammar rule for consonant clusters
  (82 % → 100 % on the gold list).

### Removed
- The ReportLab renderer and the public Fly.io editor, which let any visitor
  overwrite the shared book. A local editor returns in a later release.
