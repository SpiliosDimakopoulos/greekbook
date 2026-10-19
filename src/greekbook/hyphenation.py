"""Rule-based Modern Greek syllabification.

Typst hyphenates Greek on its own (TeX patterns) for the PDF. This module is
used where no hyphenation engine exists — soft hyphens in EPUB output — and
is benchmarked against a gold list in ``tests/test_hyphenation.py``.

Rules (standard Modern Greek syllable division):

* A single consonant between two vowels goes with the following vowel.
* Consonant clusters that can begin a Greek word (στ, σκ, πλ, τρ, μπ, ντ,
  γκ, μν, …) stay together and go with the following vowel; other clusters
  split between the two consonants.
* Digraphs (αι, ει, οι, ου, αυ, ευ, ηυ, υι) are a single nucleus.
* Double consonants (λλ, σσ, …) split between the two letters.
"""

from __future__ import annotations

VOWELS = set("αεηιουωάέήίόύώϊϋΐΰ")
DIPHTHONGS = {
    "αι",
    "ει",
    "οι",
    "ου",
    "αυ",
    "ευ",
    "ηυ",
    "υι",
    "αί",
    "εί",
    "οί",
    "ού",
    "αύ",
    "εύ",
    "ηύ",
    "υί",
}

# Consonant clusters a Greek word can begin with. Between two vowels such a
# cluster goes, whole, to the following syllable (ά-στρο, κό-σμος); any
# other cluster leaves its first consonant behind (άν-θρω-πος, εκ-στρα-τεί-α).
VALID_ONSET_CLUSTERS = {
    "βγ",
    "βδ",
    "βλ",
    "βρ",
    "γδ",
    "γκ",
    "γλ",
    "γν",
    "γρ",
    "δρ",
    "θλ",
    "θν",
    "θρ",
    "κλ",
    "κν",
    "κρ",
    "κτ",
    "μν",
    "μπ",
    "ντ",
    "πλ",
    "πν",
    "πρ",
    "πτ",
    "σβ",
    "σγ",
    "σθ",
    "σκ",
    "σλ",
    "σμ",
    "σν",
    "σπ",
    "στ",
    "σφ",
    "σχ",
    "τζ",
    "τμ",
    "τρ",
    "τσ",
    "φθ",
    "φλ",
    "φρ",
    "φτ",
    "χθ",
    "χλ",
    "χν",
    "χρ",
    "χτ",
    "σθμ",
    "σκλ",
    "σκρ",
    "σπλ",
    "σπρ",
    "στρ",
    "σφρ",
    "σχρ",
    "χθρ",
}


def _is_vowel(ch: str) -> bool:
    return ch in VOWELS


def syllabify(word: str) -> list[str]:
    """Return list of syllables for a lowercase Greek word (no punctuation)."""
    n = len(word)
    if n < 2:
        return [word]

    # Find vowel-nucleus spans (merging diphthongs into one nucleus)
    i = 0
    nuclei: list[tuple[int, int]] = []  # list of (start, end) indices of vowel nuclei
    while i < n:
        if _is_vowel(word[i]):
            start = i
            end = i + 1
            if end < n and (word[i : i + 2].lower() in DIPHTHONGS):
                end += 1
            nuclei.append((start, end))
            i = end
        else:
            i += 1

    if len(nuclei) <= 1:
        return [word]

    syllables: list[str] = []
    prev_end = 0
    for idx in range(len(nuclei) - 1):
        _, n1_end = nuclei[idx]
        n2_start, _ = nuclei[idx + 1]
        consonants = word[n1_end:n2_start]

        if len(consonants) <= 1 or consonants.lower() in VALID_ONSET_CLUSTERS:
            split_at = n1_end
        else:
            split_at = n1_end + 1

        syllables.append(word[prev_end:split_at])
        prev_end = split_at

    syllables.append(word[prev_end:])
    return [s for s in syllables if s]
