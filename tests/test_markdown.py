import pytest

from greekbook.markdown import Code, escape, markdown_to_typst, value


def md(text: str, **kw: object) -> str:
    out, _ = markdown_to_typst(text, **kw)  # type: ignore[arg-type]
    return out.strip()


def test_escape_special_characters() -> None:
    assert escape("#*_`$<>@[]~\\") == r"\#\*\_\`\$\<\>\@\[\]\~\\"
    assert escape("http://x") == r"http:\//x"
    assert escape("a--b") == r"a\--b"
    assert escape("= heading", line_start=True) == r"\= heading"
    assert escape("2024. year", line_start=True) == r"2024\. year"


def test_value_serialization() -> None:
    assert value({"a": [1, "x"], "b": None, "c": True}) == '("a": (1, "x", ), "b": none, "c": true)'
    assert value(Code("rgb(1,2,3)")) == "rgb(1,2,3)"
    assert value({}) == "(:)"
    with pytest.raises(TypeError):
        value(object())


def test_paragraph_typography_and_inline_markup() -> None:
    assert md('Είπε "*ναι*" -- και **έφυγε**.') == "Είπε «#emph[ναι]» – και #strong[έφυγε]."


def test_snake_case_is_not_emphasis() -> None:
    assert "emph" not in md("η μεταβλητή my_long_name")


def test_headings_labels_and_classes() -> None:
    assert md("# Εισαγωγή {#sec:intro}") == "= Εισαγωγή <sec:intro>"
    assert md("## Χωρίς αριθμό {-}") == "#heading(level: 2, numbering: none)[Χωρίς αριθμό]"
    assert md("# Μέρος Α {.part}") == "#gb-part[Μέρος Α]"
    assert md("# Περίληψη", unnumbered=True) == "#heading(level: 1, numbering: none)[Περίληψη]"


def test_lists() -> None:
    assert md("- α\n- β") == "#list(\n  [α],\n  [β],\n)"
    assert md("3. γ\n4. δ").startswith("#enum(start: 3, ")


def test_scene_break_and_pagebreak() -> None:
    assert md("α\n\n---\n\nβ") == "α\n\n#gb-scene-break()\n\nβ"
    assert md(r"\newpage") == "#pagebreak()"


def test_blockquote_and_code() -> None:
    assert md("> παράθεμα") == "#quote(block: true)[\nπαράθεμα\n]"
    assert md("```python\nx = 1\n```") == "```python\nx = 1\n```"
    assert md("```\na ``` b\n```") == "````\na ``` b\n````"
    assert md("`x_1`") == '#raw("x_1")'


def test_footnotes() -> None:
    out = md("Κείμενο[^1] και^[ενσωματωμένη].\n\n[^1]: Σημείωση *α*.")
    assert "#footnote[Σημείωση #emph[α].]" in out
    assert "#footnote[ενσωματωμένη]" in out


def test_math_latex_and_typst() -> None:
    assert md("$x^2$") == '#mi("x^2")'
    assert md(r"$$\frac{a}{b}$$ (eq:f)") == r'#mitex("\\frac{a}{b}") <eq:f>'
    assert md("$x^2$", math="typst") == "$x^2$"


def test_citations() -> None:
    assert md("[@knuth1984]") == "#cite(<knuth1984>)"
    assert md("[@knuth1984, σ. 12]") == "#cite(<knuth1984>, supplement: [σ. 12])"
    assert md("[@a; @b]") == "#cite(<a>)#cite(<b>)"
    assert md("[-@a]") == '#cite(<a>, form: "year")'
    assert md("όπως ο @knuth1984 έδειξε") == 'όπως ο #cite(<knuth1984>, form: "prose") έδειξε'
    assert "cite" not in md("γράψε στο info@example.com")


def test_cross_references() -> None:
    assert md("Δες το @fig:map.") == "Δες το #ref(<fig:map>)."
    assert md("στον Πίνακα [-@tbl:x]") == "στον Πίνακα #ref(<tbl:x>, supplement: none)"


def test_figures() -> None:
    out = md("![Χάρτης](img/map.png){#fig:map width=60%}", base="/ch")
    assert out == (
        '#figure(\n  image("/ch/img/map.png", width: 60%, alt: "Χάρτης"),\n'
        "  caption: [Χάρτης],\n) <fig:map>"
    )
    out, diags = markdown_to_typst("![x](https://example.com/a.png)")
    assert out.strip() == "" and "διαδίκτυο" in diags[0].message


def test_table_with_caption() -> None:
    out = md("| a | b |\n|:--|--:|\n| 1 | 2 |\n\nTable: Λεζάντα {#tbl:t}")
    assert "table.header([a], [b])" in out
    assert "align: (left, right,)" in out
    assert "caption: [Λεζάντα]" in out and out.endswith("<tbl:t>")


def test_html_is_reported() -> None:
    out, diags = markdown_to_typst("<div>x</div>", source="a.md")
    assert out.strip() == ""
    assert str(diags[0]).startswith("a.md:1:")


def test_inline_elements() -> None:
    assert md("~~όχι~~") == "#strike[όχι]"
    assert md("[σελίδα](https://x.gr)") == '#link("https://x.gr")[σελίδα]'
    assert md("[πίσω](#sec:intro)") == "#link(<sec:intro>)[πίσω]"
    assert md("α  \nβ") == "α#linebreak()β"
    assert md("α<br>β") == "α#linebreak()β"
    assert md("α <span>β</span>") == "α β"
    assert md("![](a.png)") == '#figure(image("/a.png"))'
    assert md("κείμενο ![](a.png)") == 'κείμενο #box(image("/a.png"))'
    assert md("$$x$$") == '#mitex("x")'


def test_indented_code_and_comments() -> None:
    assert md("    code") == "```\ncode\n```"
    assert md("<!-- σχόλιο -->") == ""
    assert md("<!-- pagebreak -->") == "#pagebreak()"


def test_bad_image_width_is_reported() -> None:
    _, diags = markdown_to_typst("![x](a.png){width=huge}")
    assert "πλάτος" in diags[0].message
