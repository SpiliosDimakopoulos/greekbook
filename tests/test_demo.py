"""The in-browser demo's converter (site/demo/convert.py), run in CPython."""

import runpy
from pathlib import Path
from typing import Any

import pytest

from greekbook.build import LIB_IMPORT, compile_typst

DEMO = Path(__file__).parents[1] / "site" / "demo"


@pytest.fixture
def convert(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Any:
    namespace = runpy.run_path(str(DEMO / "convert.py"))
    monkeypatch.setitem(namespace["convert"].__globals__, "ROOT", tmp_path / "project")
    return namespace["convert"]


@pytest.mark.parametrize("sample", ["novel", "thesis"])
def test_samples_convert_and_compile(convert: Any, sample: str, tmp_path: Path) -> None:
    result = convert((DEMO / "samples" / f"{sample}.md").read_text(encoding="utf-8"))
    assert "error" not in result, result.get("error")
    source = result["source"]
    assert '#import "/greekbook/lib.typ": *' in source
    # compile the way the CLI would, to prove the demo source is valid Typst
    source = source.replace('#import "/greekbook/lib.typ": *', LIB_IMPORT)
    (tmp_path / "project" / "references.bib").write_bytes(
        (DEMO / "samples" / "references.bib").read_bytes()
    )
    pdf = compile_typst(source, tmp_path / "project")
    assert isinstance(pdf, bytes) and pdf.startswith(b"%PDF")


def test_errors_are_returned(convert: Any) -> None:
    assert "YAML" in convert("---\ntitle: [\n---\nx")["error"]
    assert "key: value" in convert("---\n- a\n---\nx")["error"]
    assert "template" in convert("---\ntemplate: fancy\n---\nx")["error"]


def test_bibliography_only_for_real_citations(convert: Any) -> None:
    assert "bibliography(" not in convert("# Α\n\nΔες @fig:x.")["source"]
    assert "bibliography(" in convert("# Α\n\nΌπως [@knuth].")["source"]
