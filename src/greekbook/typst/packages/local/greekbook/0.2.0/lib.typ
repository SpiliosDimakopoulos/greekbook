// greekbook — Typst templates and Greek typography helpers.
//
// The greekbook CLI generates a main file that looks like
//
//   #import "@local/greekbook:0.2.0": *
//   #show: book.with(template: "thesis", title: "…", …)
//   … front matter …
//   #show: mainmatter
//   … chapters …
//   #show: appendices
//   … appendices …
//
// but the library can also be used by hand from any Typst document.

#import "@preview/mitex:0.2.7": mi, mitex

// ===========================================================================
// Greek helpers
// ===========================================================================

#let _tonos = (
  "ά": "α", "έ": "ε", "ή": "η", "ί": "ι", "ό": "ο", "ύ": "υ", "ώ": "ω",
  "Ά": "Α", "Έ": "Ε", "Ή": "Η", "Ί": "Ι", "Ό": "Ο", "Ύ": "Υ", "Ώ": "Ω",
  "ΐ": "ϊ", "ΰ": "ϋ",
)

/// Plain text of simple content (strings, text, sequences, styled text),
/// or none when the content has non-text parts.
#let _plain(c) = {
  if type(c) == str { return c }
  if type(c) != content { return none }
  if c.has("text") and type(c.text) == str { return c.text }
  if c.func() == [ ].func() { return " " }
  if c.has("children") {
    let parts = c.children.map(_plain)
    return if parts.all(x => x != none) { parts.join() } else { none }
  }
  if c.has("child") { return _plain(c.child) }
  if c.has("body") { return _plain(c.body) }
  none
}

#let _upper-str(s) = upper(
  s.replace(regex("[άέόΆΈΌ][ιυ]"), m => {
    let cs = m.text.clusters()
    _tonos.at(cs.first(), default: cs.first()) + (if cs.last() == "ι" { "ϊ" } else { "ϋ" })
  }).replace(regex("[άέήίόύώΆΈΉΊΌΎΏΐΰ]"), m => _tonos.at(m.text, default: m.text))
)

/// Greek all-caps: drops accents, and turns an accent that kept two vowels
/// apart into a diaeresis (τσάι → ΤΣΑΪ, ρολόι → ΡΟΛΟΪ, άυλος → ΑΫΛΟΣ).
#let el-upper(body) = {
  let s = _plain(body)
  if s != none { return _upper-str(s) }
  show regex("[άέήίόύώΆΈΉΊΌΎΏΐΰ]"): it => _tonos.at(it.text, default: it.text)
  show regex("[άέόΆΈΌ][ιυ]"): it => {
    let cs = it.text.clusters()
    _tonos.at(cs.first(), default: cs.first()) + (if cs.last() == "ι" { "ϊ" } else { "ϋ" })
  }
  upper(body)
}

#let _units = ("", "Α", "Β", "Γ", "Δ", "Ε", "ΣΤ", "Ζ", "Η", "Θ")
#let _tens = ("", "Ι", "Κ", "Λ", "Μ", "Ν", "Ξ", "Ο", "Π", "Ϙ")
#let _hundreds = ("", "Ρ", "Σ", "Τ", "Υ", "Φ", "Χ", "Ψ", "Ω", "Ϡ")

/// Greek alphabetic numeral: 1 → Α΄, 11 → ΙΑ΄, 2024 → ͵ΒΚΔ΄.
#let el-numeral(n) = {
  let thousands = calc.quo(n, 1000)
  let rest = calc.rem(n, 1000)
  let body = _hundreds.at(calc.quo(rest, 100)) + _tens.at(calc.quo(calc.rem(rest, 100), 10)) + _units.at(calc.rem(rest, 10))
  (if thousands > 0 { "͵" + _units.at(thousands) } else { "" }) + body + (if body != "" { "΄" } else { "" })
}

#let _ordinals-el = (
  "Πρώτο", "Δεύτερο", "Τρίτο", "Τέταρτο", "Πέμπτο", "Έκτο", "Έβδομο", "Όγδοο", "Ένατο", "Δέκατο",
  "Ενδέκατο", "Δωδέκατο", "Δέκατο τρίτο", "Δέκατο τέταρτο", "Δέκατο πέμπτο", "Δέκατο έκτο",
  "Δέκατο έβδομο", "Δέκατο όγδοο", "Δέκατο ένατο", "Εικοστό",
)
#let _ordinals-en = (
  "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten", "Eleven",
  "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen", "Twenty",
)

#let _strings = (
  el: (
    chapter: "Κεφάλαιο", part: "Μέρος", appendix: "Παράρτημα",
    contents: "Περιεχόμενα", figures: "Κατάλογος σχημάτων", tables: "Κατάλογος πινάκων",
    bibliography: "Βιβλιογραφία", figure: "Σχήμα", table: "Πίνακας", equation: "Εξίσωση",
    listing: "Κώδικας", supervisor: "Επιβλέπων/ουσα", committee: "Εξεταστική επιτροπή",
    student-id: "Αριθμός μητρώου", declaration: "Δήλωση πρωτοτυπίας", signature: "Υπογραφή",
    declaration-text: [
      Δηλώνω υπεύθυνα ότι η παρούσα εργασία είναι αποκλειστικά προϊόν δικής μου
      προσωπικής εργασίας, ότι δεν αποτελεί προϊόν αντιγραφής ή λογοκλοπής, και ότι
      κάθε πηγή που χρησιμοποιήθηκε για τη συγγραφή της, είτε αυτούσια είτε
      παραφρασμένη, αναφέρεται ρητά στο κείμενο και στη βιβλιογραφία. Γνωρίζω ότι
      η λογοκλοπή αποτελεί σοβαρό παράπτωμα και επισύρει κυρώσεις.
    ],
  ),
  en: (
    chapter: "Chapter", part: "Part", appendix: "Appendix",
    contents: "Contents", figures: "List of Figures", tables: "List of Tables",
    bibliography: "References", figure: "Figure", table: "Table", equation: "Equation",
    listing: "Listing", supervisor: "Supervisor", committee: "Examination committee",
    student-id: "Student ID", declaration: "Declaration of originality", signature: "Signature",
    declaration-text: [
      I hereby declare that this thesis is entirely my own work, that it has not been
      copied or plagiarised, and that every source used, whether quoted or paraphrased,
      is explicitly acknowledged in the text and in the references.
    ],
  ),
)

#let _lang-key(lang) = if lang.starts-with("el") or lang.starts-with("gr") { "el" } else { "en" }

// Active settings, readable from helpers called inside the document.
#let _gb = state("greekbook", (lang: "el", accent: black, chapter-numbering: "arabic", template: "novel"))

#let _t(key) = context _strings.at(_lang-key(_gb.get().lang)).at(key)

/// Number formatter for chapters according to the chosen style.
#let _chapter-number(style, lang, n) = {
  if style == "greek" { el-numeral(n) }
  else if style == "roman" { numbering("I", n) }
  else if style == "words" {
    let words = if _lang-key(lang) == "el" { _ordinals-el } else { _ordinals-en }
    if n <= words.len() { words.at(n - 1) } else { str(n) }
  }
  else { str(n) }
}

// ===========================================================================
// Template presets
// ===========================================================================

#let _presets = (
  novel: (
    font: ("Libertinus Serif",), heading-font: none, size: 10.5pt,
    leading: 0.62em, indent: 1.3em, spacing: 0.62em,
    ink: rgb("#1b1b1b"), accent: rgb("#1b1b1b"), paper: none,
    margin: (inside: 19mm, outside: 15mm, top: 17mm, bottom: 21mm),
    numbering: "greek", chapter-style: "literary", running-heads: true, recto: false,
    figure-per-chapter: false,
  ),
  classic: (
    font: ("New Computer Modern",), heading-font: none, size: 10.5pt,
    leading: 0.6em, indent: 1.4em, spacing: 0.6em,
    ink: black, accent: black, paper: none,
    margin: (inside: 20mm, outside: 16mm, top: 18mm, bottom: 22mm),
    numbering: "words", chapter-style: "literary", running-heads: true, recto: true,
    figure-per-chapter: false,
  ),
  sepia: (
    font: ("Libertinus Serif",), heading-font: none, size: 10.5pt,
    leading: 0.64em, indent: 1.3em, spacing: 0.64em,
    ink: rgb("#2b2117"), accent: rgb("#7c4a2d"), paper: rgb("#f4ecdd"),
    margin: (inside: 19mm, outside: 15mm, top: 17mm, bottom: 21mm),
    numbering: "greek", chapter-style: "literary", running-heads: true, recto: false,
    figure-per-chapter: false,
  ),
  clean: (
    font: ("Liberation Sans",), heading-font: ("Liberation Sans",), size: 10pt,
    leading: 0.7em, indent: 0em, spacing: 1.1em,
    ink: rgb("#1f2328"), accent: rgb("#0b6e75"), paper: none,
    margin: (inside: 18mm, outside: 16mm, top: 18mm, bottom: 20mm),
    numbering: "arabic", chapter-style: "modern", running-heads: true, recto: false,
    figure-per-chapter: true,
  ),
  academic: (
    font: ("New Computer Modern",), heading-font: none, size: 11pt,
    leading: 0.65em, indent: 1.5em, spacing: 0.65em,
    ink: black, accent: rgb("#1d3a6e"), paper: none,
    margin: (inside: 30mm, outside: 25mm, top: 28mm, bottom: 30mm),
    numbering: "arabic", chapter-style: "academic", running-heads: true, recto: false,
    figure-per-chapter: true,
  ),
  thesis: (
    font: ("Liberation Serif",), heading-font: none, size: 12pt,
    leading: 1.0em, indent: 1.25em, spacing: 1.0em,
    ink: black, accent: rgb("#1d3a6e"), paper: none,
    margin: (inside: 35mm, outside: 25mm, top: 30mm, bottom: 30mm),
    numbering: "arabic", chapter-style: "academic", running-heads: true, recto: false,
    figure-per-chapter: true,
  ),
)

#let _fallback-fonts = ("Libertinus Serif", "DejaVu Serif", "New Computer Modern")

// ===========================================================================
// Building blocks used by generated documents
// ===========================================================================

/// Scene break (`---` between paragraphs in Markdown).
#let gb-scene-break() = context {
  let accent = _gb.get().accent
  block(above: 1.3em, below: 1.3em, width: 100%, align(center, text(fill: accent, size: 1.1em, "⁂")))
}

/// A part divider page ("ΜΕΡΟΣ ΠΡΩΤΟ").
#let _part-counter = counter("gb-part")
#let gb-part(title) = {
  pagebreak(weak: true)
  _part-counter.step()
  set page(header: none, footer: none)
  [#metadata("part") <gb-part-page>]
  context {
    let s = _gb.get()
    v(1fr)
    align(center, {
      text(size: 0.9em, tracking: 0.25em, fill: s.accent, el-upper[
        #_t("part") #_chapter-number(if s.chapter-numbering == "greek" { "words" } else { s.chapter-numbering }, s.lang, _part-counter.get().first())
      ])
      v(1em)
      text(size: 2em, title)
    })
    v(2fr)
  }
  pagebreak(weak: true)
}

/// Switch to the main matter: arabic page numbers restart at 1, chapter
/// counters restart. Use as `#show: mainmatter`.
#let mainmatter(body) = {
  pagebreak(weak: true)
  counter(page).update(1)
  counter(heading).update(0)
  _gb.update(s => s + (matter: "main"))
  set page(numbering: "1")
  body
}

/// Switch to the appendices: chapters are lettered (Α, Β, … / A, B, …).
#let appendices(body) = {
  pagebreak(weak: true)
  counter(heading).update(0)
  _gb.update(s => s + (matter: "appendix"))
  set heading(numbering: (..n) => {
    let nums = n.pos()
    context {
      let el = _lang-key(_gb.get().lang) == "el"
      let first = numbering(if el { "Α" } else { "A" }, nums.first())
      if nums.len() == 1 { first } else { first + "." + nums.slice(1).map(str).join(".") }
    }
  }, supplement: _t("appendix"))
  body
}

// ===========================================================================
// Front pages
// ===========================================================================

#let _title-page(title, subtitle, author, publisher, year) = page(header: none, footer: none, context {
  let s = _gb.get()
  set par(first-line-indent: 0em, justify: false)
  set text(hyphenate: false)
  set align(center)
  v(12%)
  text(size: 1.05em, tracking: 0.18em, el-upper(author))
  v(1fr)
  text(size: 2.3em, weight: "regular", title)
  if subtitle != "" {
    v(0.8em)
    text(size: 1.15em, style: "italic", fill: s.ink.lighten(25%), subtitle)
  }
  v(1.4em)
  text(fill: s.accent, "⁂")
  v(2fr)
  if publisher != "" { text(size: 0.9em, tracking: 0.12em, el-upper(publisher)); linebreak() }
  if year != "" { text(size: 0.9em, year) }
  v(6%)
})

#let _copyright-page(copyright, publisher, year) = page(header: none, footer: none, {
  set par(first-line-indent: 0em, justify: false)
  set text(size: 0.8em)
  v(1fr)
  if copyright != "" { copyright; parbreak() }
  [Στοιχειοθετήθηκε με #link("https://github.com/SpiliosDimakopoulos/greekbook")[greekbook] και Typst.]
})

#let _centered-page(body, style: "italic") = page(header: none, footer: none, {
  set par(first-line-indent: 0em, justify: false)
  v(30%)
  align(center, text(style: style, body))
})

#let _thesis-cover(title, subtitle, author, thesis, logo) = page(header: none, footer: none, numbering: none, context {
  let s = _gb.get()
  set par(first-line-indent: 0em, justify: false, leading: 0.6em, spacing: 0.6em)
  set text(hyphenate: false)
  set align(center)
  if logo != none { block(height: 2.6cm, logo); v(0.6em) }
  for (key, size) in (("institution", 1.15em), ("school", 1em), ("department", 1em), ("program", 0.95em)) {
    let v = thesis.at(key, default: "")
    if v != "" { text(size: size, weight: if key == "institution" { "bold" } else { "regular" }, el-upper(v)); parbreak() }
  }
  v(1fr)
  text(size: 1.05em, tracking: 0.15em, fill: s.accent, el-upper(thesis.at("type", default: "")))
  v(1.2em)
  line(length: 35%, stroke: 0.6pt + s.accent)
  v(0.8em)
  text(size: 1.7em, weight: "bold", title)
  if subtitle != "" { v(0.4em); text(size: 1.2em, subtitle) }
  v(0.8em)
  line(length: 35%, stroke: 0.6pt + s.accent)
  v(1.6em)
  text(size: 1.2em, author)
  if thesis.at("student_id", default: "") != "" {
    linebreak(); text(size: 0.9em, [#_t("student-id"): #thesis.student_id])
  }
  v(1fr)
  set align(left)
  if thesis.at("supervisor", default: "") != "" {
    [*#_t("supervisor"):* #thesis.supervisor]
    parbreak()
  }
  let committee = thesis.at("committee", default: ())
  if committee.len() > 0 {
    [*#_t("committee"):*]
    list(..committee)
  }
  v(1.2em)
  set align(center)
  let when = (thesis.at("place", default: ""), thesis.at("date", default: "")).filter(x => x != "")
  text(when.join(", "))
})

#let _declaration-page(author) = {
  pagebreak(weak: true)
  heading(level: 1, numbering: none, outlined: false, _t("declaration"))
  _t("declaration-text")
  v(3em)
  align(right, block(width: 45%, {
    set par(first-line-indent: 0em)
    set align(center)
    line(length: 100%, stroke: 0.5pt)
    author
  }))
}

/// "3" for a location in chapter 3, "Α" in appendix A (needs context).
#let _chapter-prefix(loc) = {
  let ch = counter(heading).at(loc)
  let first = if ch.len() > 0 { ch.first() } else { 0 }
  let s = _gb.at(loc)
  if s.at("matter", default: "main") == "appendix" {
    numbering(if _lang-key(s.lang) == "el" { "Α" } else { "A" }, calc.max(first, 1))
  } else { str(first) }
}

/// Per-chapter number ("3.2") of a figure or equation, evaluated at the
/// element itself so references and outlines elsewhere show the right chapter.
#let _element-number(el) = {
  let loc = el.location()
  let n = if el.func() == figure { el.counter.at(loc).first() } else { counter(math.equation).at(loc).first() }
  _chapter-prefix(loc) + "." + str(n)
}

// ===========================================================================
// Headings
// ===========================================================================

#let _chapter-heading(it, p) = context {
  let s = _gb.get()
  let numbered = it.numbering != none
  let num = if numbered { counter(heading).display(it.numbering) } else { none }
  set par(first-line-indent: 0em, justify: false)
  set text(hyphenate: false)
  if p.chapter-style == "literary" {
    v(18%)
    align(center, {
      if numbered {
        text(size: 0.85em, tracking: 0.25em, fill: s.accent, el-upper[#it.supplement #num])
        v(0.9em)
      }
      text(size: 1.75em, weight: "regular", it.body)
      v(0.7em)
      text(fill: s.accent, size: 0.9em, "⁂")
    })
    v(2.4em)
  } else if p.chapter-style == "modern" {
    v(10%)
    if numbered { text(size: 3.2em, weight: "bold", fill: s.accent, num); v(0.2em) }
    text(size: 1.9em, weight: "bold", it.body)
    v(0.4em)
    line(length: 100%, stroke: 0.8pt + s.accent)
    v(1.6em)
  } else {
    v(8%)
    if numbered {
      text(size: 1.15em, fill: s.accent, [#it.supplement #num])
      v(0.5em)
    }
    text(size: 1.75em, weight: "bold", it.body)
    v(2.2em)
  }
}

// ===========================================================================
// The template
// ===========================================================================

#let book(
  template: "novel",
  title: "",
  subtitle: "",
  author: "",
  lang: "el",
  page-size: ("148mm", "210mm"),
  font: none,
  font-size: none,
  paper: none,
  chapter-numbering: "auto",
  toc: false,
  list-of-figures: false,
  list-of-tables: false,
  front-matter: false,
  dedication: "",
  epigraph: "",
  copyright: "",
  publisher: "",
  year: "",
  keywords: (),
  thesis: none,
  logo: none,
  body,
) = {
  let p = _presets.at(template)
  if font != none { p.font = if type(font) == str { (font,) } else { font } }
  if font-size != none { p.size = font-size }
  if paper != none { p.paper = if paper == "none" { none } else { rgb(paper) } }
  let numbering-style = if chapter-numbering == "auto" {
    if p.numbering == "greek" and _lang-key(lang) != "el" { "roman" } else { p.numbering }
  } else { chapter-numbering }
  let el = _lang-key(lang) == "el"
  let tr = _strings.at(_lang-key(lang))

  _gb.update((
    lang: lang, accent: p.accent, ink: p.ink, chapter-numbering: numbering-style,
    template: template, matter: if front-matter { "front" } else { "main" },
  ))

  set document(title: title, author: author, keywords: keywords)
  set text(lang: lang, font: p.font + _fallback-fonts, size: p.size, fill: p.ink, hyphenate: true)
  set par(justify: true, leading: p.leading, spacing: p.spacing, first-line-indent: p.indent)

  let (width, height) = page-size
  set page(
    width: eval(width), height: eval(height),
    margin: p.margin, fill: p.paper,
    numbering: if front-matter { "i" } else { "1" },
    header: if p.running-heads { context {
      let page-no = here().page()
      let starts = query(heading.where(level: 1)).filter(h => h.location().page() == page-no)
      let parts = query(<gb-part-page>).filter(h => h.location().page() == page-no)
      if starts.len() > 0 or parts.len() > 0 { return }
      let before = query(heading.where(level: 1).before(here()))
      let chapter = if before.len() > 0 { before.last().body } else { title }
      set text(size: 0.78em, fill: p.ink.lighten(30%))
      let even = calc.even(counter(page).get().first())
      let content = if even { el-upper(if author != "" and template in ("novel", "classic", "sepia") { author } else { title }) } else { el-upper(chapter) }
      align(if template in ("thesis", "academic", "clean") { if even { left } else { right } } else { center }, text(tracking: 0.12em, content))
    } } else { none },
    footer: context {
      if counter(page).get().first() == 0 { return }
      set text(size: 0.85em)
      align(center, counter(page).display())
    },
  )

  // ---- headings ---------------------------------------------------------
  set heading(
    numbering: if numbering-style == "none" { none } else if p.figure-per-chapter { "1.1" } else {
      (..n) => if n.pos().len() == 1 { _chapter-number(numbering-style, lang, n.pos().first()) }
    },
    supplement: tr.chapter,
  )
  show heading.where(level: 1): it => {
    pagebreak(weak: true, to: if p.recto { "odd" } else { none })
    if p.figure-per-chapter {
      counter(figure.where(kind: image)).update(0)
      counter(figure.where(kind: table)).update(0)
      counter(figure.where(kind: raw)).update(0)
      counter(math.equation).update(0)
    }
    _chapter-heading(it, p)
  }
  show heading: set text(hyphenate: false)
  show heading.where(level: 2): it => {
    set par(first-line-indent: 0em, justify: false)
    set text(font: p.heading-font) if p.heading-font != none
    block(above: 1.8em, below: 1em, sticky: true, {
      if it.numbering != none and p.figure-per-chapter { counter(heading).display(it.numbering); h(0.7em) }
      text(size: 1.2em, weight: "bold", it.body)
    })
  }
  show heading.where(level: 3): it => {
    set par(first-line-indent: 0em, justify: false)
    block(above: 1.5em, below: 0.8em, sticky: true, {
      if it.numbering != none and p.figure-per-chapter { counter(heading).display(it.numbering); h(0.6em) }
      text(size: 1.05em, weight: "bold", style: if template in ("novel", "sepia", "classic") { "italic" } else { "normal" }, it.body)
    })
  }
  show heading.where(level: 4): it => block(above: 1.3em, below: 0.6em, sticky: true, text(style: "italic", it.body))
  show heading.where(level: 2): set heading(numbering: none) if not p.figure-per-chapter
  show heading.where(level: 3): set heading(numbering: none) if not p.figure-per-chapter

  // ---- figures, tables, equations ----------------------------------------
  let per-chapter(..n) = context _chapter-prefix(here()) + "." + str(n.pos().first())
  set figure(numbering: if p.figure-per-chapter { per-chapter } else { "1" })
  show figure.where(kind: image): set figure(supplement: tr.figure)
  show figure.where(kind: table): set figure(supplement: tr.table)
  show figure.where(kind: raw): set figure(supplement: tr.listing)
  show figure.where(kind: table): set figure.caption(position: top)
  show figure.caption: it => {
    set text(size: 0.9em)
    set par(justify: false, first-line-indent: 0em)
    [*#it.supplement #context it.counter.display(it.numbering)#it.separator*#it.body]
  }
  show figure: set block(spacing: 1.6em)
  show ref: it => {
    let el = it.element
    if not p.figure-per-chapter or el == none or el.func() not in (figure, math.equation) { return it }
    let num = _element-number(el)
    if el.func() == math.equation { num = "(" + num + ")" }
    let sup = if it.supplement == auto { el.supplement } else { it.supplement }
    link(el.location(), if sup in (none, []) { num } else { [#sup~#num] })
  }
  show outline.entry: it => {
    let el = it.element
    if not p.figure-per-chapter or el.func() != figure { return it }
    link(el.location(), it.indented([#el.supplement #_element-number(el)], it.inner()))
  }
  set math.equation(
    numbering: if p.figure-per-chapter { (..n) => "(" + per-chapter(..n) + ")" } else { "(1)" },
    supplement: tr.equation,
  )
  set table(stroke: (x, y) => (
    top: if y == 0 { 1pt } else if y == 1 { 0.5pt } else { 0pt },
    bottom: 1pt,
  ), inset: (x: 0.6em, y: 0.45em))
  show table.cell.where(y: 0): set text(weight: "bold")

  // ---- other elements ----------------------------------------------------
  show quote.where(block: true): it => pad(left: 1.6em, right: 1.6em, {
    set text(size: 0.94em)
    set par(first-line-indent: 0em)
    it.body
    if it.attribution != none { align(right, [— #it.attribution]) }
  })
  show raw: set text(font: ("DejaVu Sans Mono",), size: 0.88em)
  show raw.where(block: true): it => block(
    width: 100%, inset: 0.8em, radius: 3pt, fill: luma(245), stroke: 0.5pt + luma(220),
    { set par(justify: false); it },
  )
  show link: it => if type(it.dest) == str { text(fill: p.accent, it) } else { it }
  set list(indent: 0.6em, marker: ([•], [–]))
  set enum(indent: 0.6em)
  show list: set par(first-line-indent: 0em)
  show enum: set par(first-line-indent: 0em)
  set footnote.entry(separator: line(length: 25%, stroke: 0.5pt))
  set outline(indent: auto)
  set bibliography(title: tr.bibliography)

  // ---- front pages -------------------------------------------------------
  if template == "thesis" {
    _thesis-cover(title, subtitle, author, if thesis == none { (:) } else { thesis }, logo)
    if thesis != none and thesis.at("declaration", default: true) { _declaration-page(author) }
  } else {
    _title-page(title, subtitle, author, publisher, year)
    if copyright != "" or publisher != "" { _copyright-page(copyright, publisher, year) }
    if dedication != "" { _centered-page(dedication) }
    if epigraph != "" { _centered-page(epigraph, style: "normal") }
  }
  if template == "thesis" { counter(page).update(1) }

  body
}

/// Table of contents and the optional lists of figures/tables.
#let gb-outlines(toc: true, figures: false, tables: false) = {
  if toc {
    pagebreak(weak: true)
    outline(title: _t("contents"), depth: 3)
  }
  if figures {
    pagebreak(weak: true)
    outline(title: _t("figures"), target: figure.where(kind: image))
  }
  if tables {
    pagebreak(weak: true)
    outline(title: _t("tables"), target: figure.where(kind: table))
  }
}
