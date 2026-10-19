"""Greek (and English) micro-typography for plain text runs.

Everything here is pure string manipulation with no dependency on the
output format, so the same rules feed the Typst/PDF writer and the EPUB
writer.

Rules:

* Straight double quotes become language-appropriate curly quotes, with
  nesting: Greek uses «…» for the outer level and “…” inside it, English
  uses “…” and ‘…’. Quotes the author already typed (« » “ ”) count
  toward the nesting depth.
* ``---`` becomes an em dash (—), ``--`` an en dash (–), ``...`` an
  ellipsis (…).
* Apostrophes become ’ (Greek elision: σ’ αγαπώ).
* A no-break space ties common Greek reference abbreviations to the
  number that follows (σ. 12, κεφ. 3, εικ. 2).

:func:`upper_el` implements Greek all-caps the way Greek typesetters do
it: accents are dropped, and an accent on the first vowel of what would
otherwise read as a digraph turns into a diaeresis on the second
(τσάι → ΤΣΑΪ, ρολόι → ΡΟΛΟΪ).
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

NBSP = " "

_QUOTE_LEVELS = {
    "el": (("«", "»"), ("“", "”"), ("‘", "’")),
    "en": (("“", "”"), ("‘", "’")),
}

# Characters after which a straight quote is an *opening* quote.
_OPENERS_BEFORE = set(" \t\n ([{«“‘—–-/") | {""}

_ABBREVIATIONS = ("σσ.", "σ.", "κεφ.", "εικ.", "πίν.", "αρ.", "παρ.", "τόμ.", "στ.", "υποσ.")
_ABBR_RE = re.compile(r"(?<![\w.])(" + "|".join(re.escape(a) for a in _ABBREVIATIONS) + r") (?=\d)")


def _lang_key(lang: str) -> str:
    return "el" if lang.lower().startswith(("el", "gr")) else "en"


@dataclass
class QuoteState:
    """Running state for one block of text that may be split into many runs
    (e.g. ``"text *emphasis* text"`` arrives as three runs)."""

    lang: str = "el"
    depth: int = 0
    prev_char: str = ""

    @property
    def levels(self) -> tuple[tuple[str, str], ...]:
        return _QUOTE_LEVELS[_lang_key(self.lang)]

    def _pair(self, depth: int) -> tuple[str, str]:
        levels = self.levels
        return levels[min(depth, len(levels) - 1)]


def smart_quotes(text: str, state: QuoteState) -> str:
    """Replace straight double quotes in ``text``, updating ``state``."""
    levels = state.levels
    openers = {pair[0] for pair in levels}
    closers = {pair[1] for pair in levels} - openers
    out: list[str] = []
    for ch in text:
        if ch == '"':
            if state.prev_char in _OPENERS_BEFORE:
                out.append(state._pair(state.depth)[0])
                state.depth += 1
            else:
                state.depth = max(state.depth - 1, 0)
                out.append(state._pair(state.depth)[1])
        else:
            if ch in openers and ch != "’":
                state.depth += 1
            elif ch in closers and ch != "’":
                state.depth = max(state.depth - 1, 0)
            out.append(ch)
        state.prev_char = ch
    return "".join(out)


def _apostrophes(text: str, lang: str) -> str:
    if _lang_key(lang) == "el":
        return text.replace("'", "’")
    # English: opening single quote after whitespace/start, else apostrophe.
    return re.sub(r"(^|[\s(\[{“])'", r"\1‘", text).replace("'", "’")


def typeset(text: str, state: QuoteState) -> str:
    """Apply every rule to one run of plain text."""
    text = text.replace("---", "—").replace("--", "–").replace("...", "…")
    text = smart_quotes(text, state)
    text = _apostrophes(text, state.lang)
    if _lang_key(state.lang) == "el":
        text = _ABBR_RE.sub(lambda m: m.group(1) + NBSP, text)
    return text


# ---------------------------------------------------------------------------
# Greek all-caps
# ---------------------------------------------------------------------------

_ACCENTED_DIGRAPH_RE = re.compile(r"([άέόΆΈΌ])([ιυ])")
_DIAERESIS = {"ι": "ϊ", "υ": "ϋ"}


def _strip_tonos(ch: str) -> str:
    decomposed = unicodedata.normalize("NFD", ch)
    kept = "".join(c for c in decomposed if c not in ("́", "΄"))
    return unicodedata.normalize("NFC", kept)


def upper_el(text: str) -> str:
    """Greek-aware uppercase: no accents, diaeresis where the accent kept
    two vowels apart (τσάι → ΤΣΑΪ). Non-Greek text is upper-cased normally."""
    text = unicodedata.normalize("NFC", text)
    text = _ACCENTED_DIGRAPH_RE.sub(lambda m: m.group(1) + _DIAERESIS[m.group(2)], text)
    return "".join(_strip_tonos(c) for c in text).upper()


# ---------------------------------------------------------------------------
# Greek numerals (Α΄, Β΄, … ΙΑ΄, … ͵Β)
# ---------------------------------------------------------------------------

_UNITS = ["", "Α", "Β", "Γ", "Δ", "Ε", "ΣΤ", "Ζ", "Η", "Θ"]
_TENS = ["", "Ι", "Κ", "Λ", "Μ", "Ν", "Ξ", "Ο", "Π", "Ϙ"]
_HUNDREDS = ["", "Ρ", "Σ", "Τ", "Υ", "Φ", "Χ", "Ψ", "Ω", "Ϡ"]


def greek_numeral(n: int, lower: bool = False) -> str:
    """Return the Greek alphabetic numeral for 1 ≤ n ≤ 9999 (e.g. 11 → ΙΑ΄)."""
    if not 1 <= n <= 9999:
        raise ValueError(f"Greek numerals are defined for 1..9999, got {n}")
    thousands, rest = divmod(n, 1000)
    hundreds, rest = divmod(rest, 100)
    tens, units = divmod(rest, 10)
    prefix = "͵" + _UNITS[thousands] if thousands else ""
    body = _HUNDREDS[hundreds] + _TENS[tens] + _UNITS[units]
    result = prefix + body + ("΄" if body else "")
    return result.lower() if lower else result
