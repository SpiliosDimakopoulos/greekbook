# English

greekbook turns Markdown into properly typeset Greek books and theses (PDF, PDF/A, EPUB)
using [Typst](https://typst.app), with Greek typography built in: hyphenation and
justification, nested «“…”» quotes, accentless capitals (τσάι → ΤΣΑΪ), Greek numerals,
and case-aware cross-references. English-language books work too (`language: en`).

- **Install:** `pip install git+https://github.com/SpiliosDimakopoulos/greekbook`
- **Start:** `greekbook new my-thesis --template thesis && greekbook serve my-thesis`
- **Try without installing:** the [in-browser demo](demo/) runs the same Python code in
  Pyodide and Typst as WebAssembly.

The full English overview, with the syntax table and the `book.yaml` reference, is in the
[README](https://github.com/SpiliosDimakopoulos/greekbook#readme). The rest of this site is
in Greek because that is who the tool is for.
