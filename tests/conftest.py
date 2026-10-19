from __future__ import annotations

import shutil
from pathlib import Path

import pytest

STARTERS = Path(__file__).parents[1] / "src" / "greekbook" / "starters"


@pytest.fixture
def thesis(tmp_path: Path) -> Path:
    return Path(shutil.copytree(STARTERS / "thesis", tmp_path / "thesis"))


@pytest.fixture
def novel(tmp_path: Path) -> Path:
    return Path(shutil.copytree(STARTERS / "novel", tmp_path / "novel"))


@pytest.fixture(autouse=True)
def _isolated_state(
    tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Never touch the real recent-projects list or Documents/greekbook."""
    base = tmp_path_factory.mktemp("state")
    monkeypatch.setenv("GREEKBOOK_STATE", str(base / "recent.json"))
    monkeypatch.setenv("GREEKBOOK_HOME", str(base / "workspace"))


def make_project(root: Path, yaml: str, chapters: dict[str, str]) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "book.yaml").write_text(yaml, encoding="utf-8")
    for name, text in chapters.items():
        p = root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    return root
