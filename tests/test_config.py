from pathlib import Path

import pytest

from greekbook.config import ConfigError, load_config, parse_page_size

from .conftest import make_project


def test_page_sizes() -> None:
    assert parse_page_size("A5") == ("148mm", "210mm")
    assert parse_page_size("6x9in") == ("6in", "9in")
    assert parse_page_size("150 x 220") == ("150mm", "220mm")
    with pytest.raises(ConfigError):
        parse_page_size("huge")


def test_defaults(tmp_path: Path) -> None:
    make_project(tmp_path, "title: T\nauthor: A\n", {"chapters/01.md": "# x"})
    cfg = load_config(tmp_path / "book.yaml")
    assert (cfg.template, cfg.page_size, cfg.language, cfg.show_toc) == ("novel", "A5", "el", False)
    assert [p.name for p in cfg.chapter_files()] == ["01.md"]


def test_thesis_defaults_to_a4_and_toc(tmp_path: Path) -> None:
    make_project(tmp_path, "title: T\nauthor: A\ntemplate: thesis\n", {"chapters/a.md": "x"})
    cfg = load_config(tmp_path)
    assert cfg.page_size == "A4" and cfg.show_toc


def test_legacy_projects_still_load(tmp_path: Path) -> None:
    make_project(tmp_path, "title: T\nauthor: A\ntheme: clean\nparts_dir: parts\n",
                 {"parts/01.md": "x"})  # fmt: skip
    cfg = load_config(tmp_path)
    assert cfg.template == "clean" and cfg.chapter_files()[0].name == "01.md"


@pytest.mark.parametrize(
    ("yaml", "message"),
    [
        ("title: T\n", "author"),
        ("title: T\nauthor: A\ncolour: red\n", "Άγνωστα πεδία"),
        ("title: T\nauthor: A\ntemplate: fancy\n", "Άγνωστο template"),
        ("title: T\nauthor: A\ncitation_style: weird\n", "citation_style"),
        ("title: T\nauthor: A\nmath: mathml\n", "math"),
        ("title: T\nauthor: A\nthesis: {supervisor_name: x}\n", "thesis"),
        ("title: T\nauthor: A\nchapters: [missing.md]\n", "missing.md"),
        ("- just\n- a list\n", "key: value"),
        ("title: [unclosed\n", "YAML"),
    ],
)
def test_errors(tmp_path: Path, yaml: str, message: str) -> None:
    make_project(tmp_path, yaml, {})
    with pytest.raises(ConfigError, match=message):
        load_config(tmp_path).chapter_files()


def test_no_chapters(tmp_path: Path) -> None:
    make_project(tmp_path, "title: T\nauthor: A\n", {"chapters/empty.md": "  \n"})
    with pytest.raises(ConfigError, match="Δεν βρέθηκαν κεφάλαια"):
        load_config(tmp_path).chapter_files()


def test_missing_file() -> None:
    with pytest.raises(ConfigError):
        load_config("does/not/exist")
