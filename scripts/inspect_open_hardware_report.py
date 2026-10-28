# -*- coding: utf-8 -*-
"""Render every exported report page and inspect searchable text geometry."""
from __future__ import annotations

import json
import argparse
from pathlib import Path

import fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "outputs/open_hardware_submission_20261026"
WORK = OUT / "work"
RENDER = WORK / "render"


def main():
    global OUT, WORK, RENDER
    parser = argparse.ArgumentParser()
    parser.add_argument("--directory", type=Path, default=OUT)
    args = parser.parse_args()
    OUT = args.directory
    WORK = OUT / "work"
    RENDER = WORK / "render"
    pdf_path = next(OUT.glob("*.pdf"))
    pdf = fitz.open(pdf_path)
    RENDER.mkdir(parents=True, exist_ok=True)
    pages = []
    for i, page in enumerate(pdf):
        image = page.get_pixmap(matrix=fitz.Matrix(1.65, 1.65), alpha=False)
        image.save(RENDER / f"page-{i + 1:02}.png")
        all_text = page.get_text()
        blocks = page.get_text("blocks")
        body_blocks = [b for b in blocks if b[6] == 0 and b[1] < 740]
        outside = [b[4].strip()[:50] for b in body_blocks if b[0] < 35 or b[2] > page.rect.width - 35 or b[1] < 25 or b[3] > page.rect.height - 35]
        pages.append({
            "page": i + 1,
            "chars": len(all_text.strip()),
            "first_lines": all_text.strip().splitlines()[:3],
            "body_bottom": max([b[3] for b in body_blocks], default=0),
            "outside_margin": outside,
            "replacement_glyph": "\ufffd" in all_text,
        })
    thumbs = []
    for i in range(len(pdf)):
        im = Image.open(RENDER / f"page-{i + 1:02}.png").convert("RGB")
        im.thumbnail((306, 396))
        thumbs.append(im)
    font = ImageFont.truetype("C:/Windows/Fonts/msyh.ttc", 19)
    for batch in range((len(thumbs) + 8) // 9):
        sheet = Image.new("RGB", (1020, 1320), "#DDE4DF")
        draw = ImageDraw.Draw(sheet)
        for offset, im in enumerate(thumbs[batch * 9:batch * 9 + 9]):
            xx = 17 + (offset % 3) * 340
            yy = 30 + (offset // 3) * 440
            sheet.paste(im, (xx, yy))
            draw.text((xx, yy - 25), f"第 {batch * 9 + offset + 1} 页", font=font, fill="#1F3027")
        sheet.save(WORK / f"contact-{batch + 1}.png")
    text = "\n".join(f"\n--- PAGE {i+1} ---\n" + p.get_text() for i, p in enumerate(pdf))
    (WORK / "report-text.txt").write_text(text, encoding="utf-8")
    report = {"pdf": str(pdf_path), "page_count": len(pdf), "pages": pages}
    (WORK / "layout-audit.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
