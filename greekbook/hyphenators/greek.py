# -*- coding: utf-8 -*-
"""
Lightweight rule-based Greek syllabifier, exposing the same .iterate(word)
interface as pyphen.Pyphen, for use as a ReportLab style.hyphenationLang
callable. Not linguistically perfect, but covers the standard Modern Greek
syllable-division rules well enough to noticeably reduce justify gaps.

Rules implemented (standard Greek syllabification):
- A single consonant between two vowels goes with the FOLLOWING vowel.
- Consonant clusters that form valid Greek onsets (e.g. στ, σκ, πλ, τρ, γν,
  μπ, ντ, γκ, μν, etc.) stay together and go with the following vowel.
  Clusters that are not valid onsets split between the two consonants.
- Digraphs/diphthong-ish vowel pairs (αι, ει, οι, ου, αυ, ευ, ηυ, υι) are
  treated as a single nucleus and not split internally.
- Double consonants (e.g. λλ, σσ, ββ) split between the two letters.
- We never propose a break that would leave a 1-letter fragment at either
  end, since ReportLab/typography conventions avoid that.
"""

VOWELS = set("αεηιουωάέήίόύώϊϋΐΰ")
DIPHTHONGS = {"αι", "ει", "οι", "ου", "αυ", "ευ", "ηυ", "υι",
              "αί", "εί", "οί", "ού", "αύ", "εύ", "ηύ", "υί"}

# Consonant clusters that are valid syllable onsets in Greek and therefore
# stay together with the following vowel (i.e. we do not split inside them).
VALID_ONSET_CLUSTERS = {
    "βρ", "γλ", "γρ", "δρ", "θρ", "κλ", "κρ", "κτ", "μν", "πλ", "πρ", "πτ",
    "σβ", "σγ", "σδ", "σθ", "σκ", "σπ", "στ", "σφ", "σχ", "τρ", "φλ", "φρ",
    "χλ", "χρ", "μπ", "ντ", "γκ", "τσ", "τζ",
    "σκλ", "σπλ", "σπρ", "στρ", "σφρ", "σκρ",
}


def _is_vowel(ch):
    return ch in VOWELS


def syllabify(word):
    """Return list of syllables for a lowercase Greek word (no punctuation)."""
    n = len(word)
    if n < 2:
        return [word]

    # Find vowel-nucleus spans (merging diphthongs into one nucleus)
    i = 0
    nuclei = []  # list of (start, end) indices of vowel nuclei
    while i < n:
        if _is_vowel(word[i]):
            start = i
            end = i + 1
            if end < n and (word[i:i + 2].lower() in DIPHTHONGS):
                end += 1
            nuclei.append((start, end))
            i = end
        else:
            i += 1

    if len(nuclei) <= 1:
        return [word]

    syllables = []
    prev_end = 0
    for idx in range(len(nuclei) - 1):
        _, n1_end = nuclei[idx]
        n2_start, _ = nuclei[idx + 1]
        consonants = word[n1_end:n2_start]

        if len(consonants) == 0:
            split_at = n1_end
        elif len(consonants) == 1:
            split_at = n1_end
        elif len(consonants) == 2:
            if consonants.lower() in VALID_ONSET_CLUSTERS or consonants[0] == consonants[1]:
                if consonants[0] == consonants[1]:
                    split_at = n1_end + 1
                else:
                    split_at = n1_end
            else:
                split_at = n1_end + 1
        else:
            last_two = consonants[-2:].lower()
            if last_two in VALID_ONSET_CLUSTERS:
                split_at = n1_end + (len(consonants) - 2)
            else:
                split_at = n1_end + (len(consonants) - 1)

        syllables.append(word[prev_end:split_at])
        prev_end = split_at

    syllables.append(word[prev_end:])
    return [s for s in syllables if s]


class GreekHyphenator:
    """Mimics pyphen.Pyphen's .iterate(word) interface for ReportLab."""

    def __init__(self, min_word_length=7, min_fragment=2):
        self.min_word_length = min_word_length
        self.min_fragment = min_fragment

    def iterate(self, word):
        if len(word) < self.min_word_length:
            return
        # Strip leading/trailing punctuation that may be glued to the word
        prefix = ""
        suffix = ""
        core = word
        while core and not core[0].isalpha():
            prefix += core[0]
            core = core[1:]
        while core and not core[-1].isalpha():
            suffix = core[-1] + suffix
            core = core[:-1]
        if len(core) < self.min_word_length:
            return

        lower_core = core.lower()
        syllables = syllabify(lower_core)
        if len(syllables) < 2:
            return

        # Rebuild candidate split points (in terms of character offsets in core),
        # preserving original case from `core`.
        offsets = []
        pos = 0
        for syl in syllables[:-1]:
            pos += len(syl)
            offsets.append(pos)

        results = []
        for off in offsets:
            head = core[:off]
            tail = core[off:]
            if len(head) < self.min_fragment or len(tail) < self.min_fragment:
                continue
            results.append((prefix + head, tail + suffix))
        # ReportLab expects them in an order it can use; reverse so longer
        # head-fragments (later breaks) are tried first, matching pyphen's
        # typical iterate() behaviour (rightmost break first).
        for pair in reversed(results):
            yield pair
