"""Render one sample page spread per template into docs/images/templates/.

python scripts/gallery.py
"""

from __future__ import annotations

import io
import shutil
import sys
import tempfile
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from greekbook.build import compile_typst, generate_typst  # noqa: E402
from greekbook.config import TEMPLATES, load_config  # noqa: E402

STARTERS = ROOT / "src" / "greekbook" / "starters"
OUT = ROOT / "docs" / "images" / "templates"


def pages(project: Path, ppi: float) -> list[Image.Image]:
    cfg = load_config(project)
    source, _ = generate_typst(cfg)
    result = compile_typst(source, cfg.base_dir, fmt="png", ppi=ppi)
    images = []
    for data in result if isinstance(result, list) else [result]:
        im = Image.open(io.BytesIO(data)).convert("RGBA")
        bg = Image.new("RGBA", im.size, "white")
        bg.alpha_composite(im)
        images.append(bg.convert("RGB"))
    return images


def _ink(im: Image.Image) -> int:
    return sum(im.convert("L").point(lambda v: 255 if v < 128 else 0).histogram()[255:])


def spread(images: list[Image.Image], path: Path, gap: int = 18, pad: int = 18) -> None:
    height = max(i.size[1] for i in images)
    width = sum(i.size[0] for i in images) + gap * (len(images) - 1) + 2 * pad
    canvas = Image.new("RGB", (width, height + 2 * pad), "#e9e6e1")
    x = pad
    for im in images:
        canvas.paste(Image.new("RGB", im.size, "#c9c4bc"), (x + 3, pad + 3))
        canvas.paste(im, (x, pad))
        x += im.size[0] + gap
    canvas.save(path, optimize=True)


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for template in TEMPLATES:
        starter = "thesis" if template in ("thesis", "academic", "clean") else "novel"
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(shutil.copytree(STARTERS / starter, Path(tmp) / "p"))
            yaml = project / "book.yaml"
            text = yaml.read_text(encoding="utf-8").replace("template: thesis\n", "")
            text = text.replace("template: novel\n", "")
            yaml.write_text(f"template: {template}\n" + text, encoding="utf-8")
            imgs = pages(project, 70)
            # title page + the two pages with the most ink (body text, figures)
            ink = sorted(range(1, len(imgs)), key=lambda i: -_ink(imgs[i]))[:2]
            pick = [imgs[0]] + [imgs[i] for i in sorted(ink)]
            spread(pick, OUT / f"{template}.png")
            print(template, len(imgs), "pages")


if __name__ == "__main__":
    main()
