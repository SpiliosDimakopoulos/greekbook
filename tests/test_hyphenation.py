"""Greek syllabification against a gold list.

The gold syllabifications follow the rules of the Modern Greek school
grammar (Γραμματική της Νέας Ελληνικής Γλώσσας): a consonant cluster goes
with the following vowel when a Greek word can begin with it (ά-στρο,
άν-θρω-πος, έκ-θε-ση), double consonants split (θά-λασ-σα), and μπ/ντ/γκ/
τσ/τζ stay together. Words with synizesis (ποιος, διαβάζω), whose division
depends on pronunciation, are deliberately left out.
"""

import pytest

from greekbook.hyphenation import syllabify

GOLD = """
α-πό έ-χω ά-στρο ελ-πί-δα άν-θρω-πος πα-ρά-θυ-ρο θά-λασ-σα εκ-κλη-σί-α
κα-λη-μέ-ρα ευ-χα-ρι-στώ ο-μι-λί-α πρό-βλη-μα έκ-θε-ση άμ-μος αρ-χι-τε-κτο-νι-κή
ε-πι-στή-μη σχο-λεί-ο ου-ρα-νός αυ-το-κί-νη-το γράμ-μα πράγ-μα δρό-μος σπί-τι
πόρ-τα άγ-γε-λος κου-μπί πέ-ντε ά-γκυ-ρα κο-ρί-τσι εκ-στρα-τεί-α ορ-θο-γρα-φί-α
Ελ-λά-δα αλ-λά κρε-βά-τι τρα-πέ-ζι παι-δί εί-ναι ου-ρα-νο-ξύ-στης ψυ-χο-λο-γί-α
ξε-νο-δο-χεί-ο θε-ω-ρί-α α-ε-ρο-πλά-νο Α-θή-να πα-τρί-δα ε-γκα-τά-στα-ση
συ-μπέ-ρα-σμα πρό-σθε-ση έ-σχα-τος κό-σμος δά-σκα-λος μά-θη-μα γνώ-ση α-γνός
ε-φτά ο-κτώ ά-πνοι-α ε-χθρός ρο-λό-ι τσά-ι α-ϋ-πνί-α κα-ϊ-κι πρω-ί
ά-σθμα φθι-νό-πω-ρο ε-λεύ-θε-ρος αυ-γό ευ-ρώ-πη πνεύ-μα συ-γκοι-νω-νί-α
α-δελ-φός ερ-γα-σί-α πα-νε-πι-στή-μι-ο δι-πλω-μα-τι-κή στοι-χει-ο-θε-σί-α
βι-βλί-ο βι-βλι-ο-θή-κη υ-πο-λο-γι-στής ε-ξε-τά-σεις μα-θη-μα-τι-κά
ο-δη-γί-ες α-ριθ-μός φι-λο-σο-φί-α εκ-δό-σεις τυ-πο-γρα-φί-α συλ-λα-βι-σμός
""".split()


def _hyphenated(word: str) -> str:
    return "-".join(syllabify(word.lower()))


@pytest.mark.parametrize("gold", GOLD)
def test_gold_syllabification(gold: str) -> None:
    assert _hyphenated(gold.replace("-", "")) == gold.lower()


def test_accuracy_report() -> None:
    correct = sum(_hyphenated(g.replace("-", "")) == g.lower() for g in GOLD)
    accuracy = correct / len(GOLD)
    print(f"\nGreek syllabification: {correct}/{len(GOLD)} = {accuracy:.1%}")
    assert accuracy == 1.0


def test_trivial_inputs() -> None:
    assert syllabify("α") == ["α"]
    assert syllabify("") == [""]
    assert syllabify("ψ") == ["ψ"]
