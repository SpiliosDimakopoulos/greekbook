import zipfile
from pathlib import Path

import pytest

from greekbook.cli import main
from greekbook.config import load_config
from greekbook.epub import SHY, build_epub, hyphenate_greek
from greekbook.lint import lint_project

from .conftest import make_project

BAD = """# Κεφάλαιο

Η λέξη λoγος έχει λατινικό o. Η λέξη αςτρο έχει λάθος σίγμα και η λέξη λογοσ επίσης.

Ένα "μονό εισαγωγικό εδώ.

Δες @fig:none και [@ghost] και ![x](missing.png).
"""


def test_lint_finds_greek_specific_mistakes(tmp_path: Path) -> None:
    make_project(tmp_path, "title: T\nauthor: A\n", {"chapters/01.md": BAD})
    messages = [str(i) for i in lint_project(load_config(tmp_path))]
    joined = "\n".join(messages)
    assert "λoγος" in joined and "μοιάζουν με ελληνικά" in joined
    assert "τελικό «ς» στη μέση λέξης" in joined
    assert "«σ» στο τέλος λέξης: «λογοσ»" in joined
    assert "μονός αριθμός εισαγωγικών" in joined
    assert "@fig:none" in joined and "@ghost" in joined and "missing.png" in joined
    assert all(m.startswith("chapters/01.md:") for m in messages)


def test_starters_are_clean(thesis: Path, novel: Path) -> None:
    assert lint_project(load_config(thesis)) == []
    assert lint_project(load_config(novel)) == []


def test_cli_new_build_validate(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    project = tmp_path / "my"
    assert main(["new", str(project), "--template", "novel"]) == 0
    assert main(["new", str(project)]) == 1  # not empty any more
    assert main(["validate", str(project)]) == 0
    assert main(["build", str(project), "--epub"]) == 0
    assert (project / "novel.pdf").is_file() and (project / "novel.epub").is_file()
    assert main(["build", str(project), "--typst-only"]) == 0
    assert (project / "novel.typ").is_file()
    assert main(["templates"]) == 0
    assert "thesis" in capsys.readouterr().out


def test_cli_errors(tmp_path: Path) -> None:
    assert main(["build", str(tmp_path)]) == 1
    make_project(tmp_path, "title: T\nauthor: A\n", {"chapters/01.md": BAD})
    assert main(["validate", str(tmp_path)]) == 1


def test_cli_doctor() -> None:
    assert main(["doctor"]) == 0


def test_hyphenate_greek() -> None:
    assert hyphenate_greek("ευχαριστημένους") == SHY.join(["ευ", "χα", "ρι", "στη", "μέ", "νους"])
    assert hyphenate_greek("καλός") == "καλός"  # short words untouched
    assert hyphenate_greek("hello wonderful") == "hello wonderful"


def test_epub_contents(novel: Path) -> None:
    out = build_epub(load_config(novel))
    with zipfile.ZipFile(out) as z:
        names = z.namelist()
        chapter = z.read(next(n for n in names if n.endswith("ch01.xhtml"))).decode()
    assert "mimetype" in names
    assert SHY in chapter
    assert "«Θα μείνεις" in chapter.replace(SHY, "")
    assert 'xml:lang="el"' in chapter
