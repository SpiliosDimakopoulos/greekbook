# Ρυθμίσεις (book.yaml)

Υποχρεωτικά είναι μόνο τα `title` και `author`. Άγνωστα πεδία απορρίπτονται με μήνυμα
που λέει ποια υπάρχουν, για να μη σου ξεφύγει ποτέ ένα τυπογραφικό λάθος.

## Βασικά

| Πεδίο | Προεπιλογή | Τιμές |
|---|---|---|
| `title`, `subtitle`, `author` | | κείμενο |
| `template` | `novel` | `novel`, `classic`, `sepia`, `clean`, `academic`, `thesis` |
| `language` | `el` | `el`, `en` |
| `page_size` | A5 (A4 για thesis/academic) | `A4`, `A5`, `A6`, `B5`, `LETTER`, `6x9in`, `5.5x8.5in`, `148x210mm` |
| `output` | `book.pdf` | όνομα αρχείου |

## Περιεχόμενο

| Πεδίο | Προεπιλογή | Περιγραφή |
|---|---|---|
| `chapters` | όλα τα `chapters/*.md` | λίστα αρχείων, αν θες άλλη σειρά |
| `chapters_dir` | `chapters` | φάκελος κεφαλαίων |
| `front_matter` | — | αρχεία πριν τα κεφάλαια (περίληψη, πρόλογος) |
| `appendices` | — | παραρτήματα |
| `bibliography` | — | ένα ή περισσότερα αρχεία `.bib` |
| `citation_style` | `apa` | `apa`, `ieee`, `harvard`, `chicago`, `chicago-notes`, `mla`, `vancouver` ή `.csl` |
| `toc` | ναι για thesis/academic | πίνακας περιεχομένων |
| `list_of_figures`, `list_of_tables` | όχι | κατάλογοι σχημάτων/πινάκων |

## Εμφάνιση

| Πεδίο | Προεπιλογή | Περιγραφή |
|---|---|---|
| `chapter_numbering` | `auto` | `greek` (Α΄), `arabic`, `roman`, `words` (Πρώτο), `none` |
| `font` | του προτύπου | οποιαδήποτε εγκατεστημένη γραμματοσειρά |
| `font_size` | του προτύπου | π.χ. `11pt` |
| `paper_color` | — | π.χ. `"#fdfbf6"` |
| `math` | `latex` | `latex` ή `typst` |
| `pdf_standard` | `1.7` | `a-2b`, `a-3b` (αρχειοθέτηση), `ua-1` (προσβασιμότητα) |

## Βιβλία

`publisher`, `year`, `copyright` (σελίδα copyright), `dedication` (αφιέρωση),
`epigraph` (μότο), `keywords` (μεταδεδομένα PDF).

## Πτυχιακές

Κάτω από `thesis:` τα `type`, `institution`, `school`, `department`, `program`,
`student_id`, `supervisor`, `committee`, `place`, `date`, `logo`, `declaration`
(δες τον [οδηγό πτυχιακής](ptyxiaki.md)).
