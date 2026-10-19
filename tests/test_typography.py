from hypothesis import given
from hypothesis import strategies as st

from greekbook.typography import NBSP, QuoteState, greek_numeral, typeset, upper_el


def t(text: str, lang: str = "el") -> str:
    return typeset(text, QuoteState(lang))


def test_greek_quotes_and_nesting() -> None:
    assert t('Είπε "γεια".') == "Είπε «γεια»."
    assert t('"Ο πατέρας έλεγε "ναι" πάντα"') == "«Ο πατέρας έλεγε “ναι” πάντα»"


def test_english_quotes() -> None:
    assert t("He said \"hi\" and 'bye'", "en") == "He said “hi” and ‘bye’"


def test_typed_guillemets_count_for_nesting() -> None:
    assert t('«Λέει "όχι" ο ίδιος»') == "«Λέει “όχι” ο ίδιος»"


def test_quote_state_spans_runs() -> None:
    state = QuoteState("el")
    assert typeset('Είπε "να ', state) + typeset('έρθεις"', state) == "Είπε «να έρθεις»"


def test_dashes_ellipsis_apostrophe() -> None:
    assert t("α---β, 12--14, και...") == "α—β, 12–14, και…"
    assert t("σ' αγαπώ") == "σ’ αγαπώ"


def test_nbsp_after_reference_abbreviations() -> None:
    assert t("βλ. σ. 12 και κεφ. 3") == f"βλ. σ.{NBSP}12 και κεφ.{NBSP}3"
    assert t("τις σσ. 4") == f"τις σσ.{NBSP}4"


def test_upper_el() -> None:
    assert upper_el("Κεφάλαιο πρώτο") == "ΚΕΦΑΛΑΙΟ ΠΡΩΤΟ"
    assert upper_el("τσάι, ρολόι, άυλος, κέικ") == "ΤΣΑΪ, ΡΟΛΟΪ, ΑΫΛΟΣ, ΚΕΪΚ"
    assert upper_el("αϋπνία, Ευρώπη") == "ΑΫΠΝΙΑ, ΕΥΡΩΠΗ"
    assert upper_el("ΐδιος") == "ΪΔΙΟΣ"
    assert upper_el("Hello") == "HELLO"


def test_greek_numerals() -> None:
    expected = {
        1: "Α΄",
        6: "ΣΤ΄",
        10: "Ι΄",
        11: "ΙΑ΄",
        16: "ΙΣΤ΄",
        40: "Μ΄",
        99: "ϘΘ΄",
        100: "Ρ΄",
        666: "ΧΞΣΤ΄",
        2024: "͵ΒΚΔ΄",
        1000: "͵Α",
    }
    for n, numeral in expected.items():
        assert greek_numeral(n) == numeral
    assert greek_numeral(3, lower=True) == "γ΄"


@given(st.text(alphabet='αβγ "«»', max_size=40))
def test_quotes_never_left_straight(text: str) -> None:
    assert '"' not in t(text)


@given(st.text(alphabet="άέήίόύώαειουΆΈΌτσκ ", max_size=30))
def test_upper_el_has_no_accents(text: str) -> None:
    assert not set("ΆΈΉΊΌΎΏάέήίόύώ") & set(upper_el(text))
