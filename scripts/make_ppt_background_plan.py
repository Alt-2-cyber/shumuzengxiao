#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Create a background-only PPT plan so image generation can use Images API.

The relay used for this project supports /v1/images/generations but does not
return images from /v1/chat/completions. The gpt-image2-ppt script switches to
chat whenever a reference or external-image skeleton is present, so this helper
removes those image elements only for the background generation pass.
"""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "slides_plan.json"
OUTPUT = ROOT / "slides_plan_background.json"

IMAGE_TYPES = {
    "external_image",
    "external_image_placeholder",
    "image_overlay",
    "image_reference",
    "visual_reference",
    "reference_image",
    "style_reference_image",
}


def main() -> None:
    data = json.loads(INPUT.read_text(encoding="utf-8"))
    background = deepcopy(data)
    background["notes"] = (
        "Background-only generation plan. Real screenshots/diagrams are "
        "overlaid later from slides_plan.json metadata."
    )

    for slide in background.get("slides", []):
        spec = slide.get("slide_spec") or {}
        elements = spec.get("elements") or {}
        for key in list(elements):
            elem = elements.get(key)
            if isinstance(elem, dict) and str(elem.get("type", "")).lower() in IMAGE_TYPES:
                elements.pop(key, None)
        layout = spec.get("layout") or ""
        spec["layout"] = (
            f"{layout} 生成阶段不使用参考图或真实截图；请只生成背景、标题、短文本、"
            "抽象线条、图标、数据块和为真实图片预留的干净空间。"
        )

    OUTPUT.write_text(json.dumps(background, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"[OK] wrote {OUTPUT}")


if __name__ == "__main__":
    main()
