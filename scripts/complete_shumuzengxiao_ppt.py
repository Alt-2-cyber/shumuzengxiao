#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Complete the Shumuzengxiao PPT session after partial image2 generation.

The image relay intermittently returns upstream 404/524 for some slides. This
script creates the missing slide backgrounds in the same visual system, updates
metadata so the gpt-image2-ppt packaging code can still overlay real project
assets, and builds the final PPTX.
"""

from __future__ import annotations

import copy
import importlib.util
import json
import math
import os
import random
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "shumuzengxiao_ppt"
IMG_DIR = OUT_DIR / "images"
PLAN_PATH = ROOT / "slides_plan.json"
META_PATH = OUT_DIR / "metadata.json"
GEN_PPT = Path(r"C:\Users\q4984\.codex\skills\gpt-image2-ppt-skills\scripts\generate_ppt.py")

W, H = 1672, 941
SLIDE_IN = (13.333, 7.5)

COLORS = {
    "bg": (8, 22, 43),
    "panel": (15, 38, 65),
    "panel2": (19, 49, 78),
    "cyan": (25, 214, 226),
    "peach": (255, 171, 132),
    "pink": (245, 125, 183),
    "white": (246, 250, 255),
    "muted": (165, 187, 205),
    "line": (61, 96, 125),
    "green": (72, 215, 163),
    "yellow": (248, 210, 105),
}


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\SourceHanSansCN-Regular.otf",
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for path in candidates:
        if path and Path(path).exists():
            return ImageFont.truetype(path, size=size)
    return ImageFont.load_default()


F_TITLE = font(49, True)
F_SUB = font(27, True)
F_BODY = font(25)
F_SMALL = font(20)
F_TINY = font(17)
F_NUM = font(42, True)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def wrap_text(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    lines: list[str] = []
    for paragraph in text.split("\n"):
        current = ""
        for ch in paragraph:
            trial = current + ch
            if text_size(draw, trial, fnt)[0] <= max_w or not current:
                current = trial
            else:
                lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def draw_text(
    draw: ImageDraw.ImageDraw,
    xy: tuple[int, int],
    text: str,
    fnt: ImageFont.FreeTypeFont,
    fill: tuple[int, int, int] = COLORS["white"],
    max_w: int | None = None,
    line_gap: int = 8,
) -> int:
    x, y = xy
    if max_w is None:
        draw.text((x, y), text, font=fnt, fill=fill)
        return y + text_size(draw, text, fnt)[1]
    for line in wrap_text(draw, text, fnt, max_w):
        draw.text((x, y), line, font=fnt, fill=fill)
        y += text_size(draw, line, fnt)[1] + line_gap
    return y


def base_slide(title: str, section: str) -> tuple[Image.Image, ImageDraw.ImageDraw]:
    img = Image.new("RGB", (W, H), COLORS["bg"])
    draw = ImageDraw.Draw(img)

    rng = random.Random(hash(title) & 0xFFFF)
    for _ in range(86):
        x = rng.randint(0, W - 20)
        y = rng.randint(0, H - 20)
        s = rng.choice([7, 9, 11, 14])
        color = rng.choice([COLORS["cyan"], COLORS["peach"], COLORS["pink"], COLORS["line"]])
        if rng.random() < 0.45:
            draw.rectangle((x, y, x + s, y + s), outline=color, width=2)
        else:
            draw.rectangle((x, y, x + s, y + s), fill=color)
    for _ in range(36):
        x = rng.randint(0, W)
        y = rng.randint(0, H)
        if rng.random() < 0.55:
            draw.line((x, y, x, min(H, y + rng.randint(40, 170))), fill=COLORS["line"], width=1)
        else:
            draw.line((x, y, min(W, x + rng.randint(60, 240)), y), fill=COLORS["line"], width=1)

    draw.rectangle((0, 0, W, 76), fill=(6, 18, 36))
    draw.rectangle((64, 34, 88, 58), fill=COLORS["cyan"])
    draw.rectangle((98, 34, 116, 52), outline=COLORS["peach"], width=3)
    draw.text((132, 28), section, font=F_TINY, fill=COLORS["muted"])
    draw_text(draw, (64, 96), title, F_TITLE, COLORS["white"], max_w=1180, line_gap=6)
    return img, draw


def panel(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], accent: tuple[int, int, int] = COLORS["cyan"]) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=16, fill=COLORS["panel"], outline=(44, 78, 105), width=2)
    draw.rectangle((x1, y1, x1 + 8, y2), fill=accent)


def square_icon(draw: ImageDraw.ImageDraw, x: int, y: int, label: str, color: tuple[int, int, int]) -> None:
    draw.rectangle((x, y, x + 64, y + 64), fill=color)
    draw.text((x + 32, y + 17), label, font=F_SMALL, fill=(7, 20, 37), anchor="ma")


def arrow(draw: ImageDraw.ImageDraw, p1: tuple[int, int], p2: tuple[int, int], color: tuple[int, int, int] = COLORS["cyan"]) -> None:
    draw.line((p1[0], p1[1], p2[0], p2[1]), fill=color, width=4)
    ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    for da in (2.55, -2.55):
        x = p2[0] + 18 * math.cos(ang + da)
        y = p2[1] + 18 * math.sin(ang + da)
        draw.line((p2[0], p2[1], x, y), fill=color, width=4)


def draw_image_placeholder(draw: ImageDraw.ImageDraw, box: tuple[int, int, int, int], label: str) -> None:
    x1, y1, x2, y2 = box
    draw.rounded_rectangle(box, radius=20, fill=(10, 27, 50), outline=(88, 126, 154), width=2)
    for x in range(x1 + 24, x2, 62):
        draw.line((x, y1 + 24, x, y2 - 24), fill=(26, 55, 80), width=1)
    for y in range(y1 + 24, y2, 62):
        draw.line((x1 + 24, y, x2 - 24, y), fill=(26, 55, 80), width=1)
    draw.text(((x1 + x2) // 2, (y1 + y2) // 2 - 10), label, font=F_SMALL, fill=COLORS["muted"], anchor="mm")
    draw.text(((x1 + x2) // 2, (y1 + y2) // 2 + 26), "真实项目图将在 PPT 中后贴", font=F_TINY, fill=COLORS["cyan"], anchor="mm")


def slide_6() -> None:
    img, draw = base_slide("边缘固件与通信协议：从采集到闭环控制", "06 / 边缘固件")
    steps = ["采集", "预处理", "阈值/推理", "MQTT 上报", "后端入库", "告警策略", "命令下发", "执行回执"]
    y = 235
    xs = [92, 272, 456, 650, 846, 1040, 1230, 1412]
    for i, (x, s) in enumerate(zip(xs, steps)):
        color = [COLORS["cyan"], COLORS["peach"], COLORS["pink"], COLORS["green"]][i % 4]
        draw.rounded_rectangle((x, y, x + 132, y + 76), radius=10, fill=COLORS["panel2"], outline=color, width=2)
        draw.text((x + 66, y + 25), s, font=F_SMALL, fill=COLORS["white"], anchor="ma")
        if i < len(xs) - 1:
            arrow(draw, (x + 132, y + 38), (xs[i + 1] - 18, y + 38), color)
    panel(draw, (80, 390, 725, 745), COLORS["cyan"])
    draw_text(draw, (118, 430), "固件侧闭环", F_SUB, COLORS["cyan"], max_w=520)
    bullets = [
        "环境数据带时间戳、设备编号、异常阈值与状态标记。",
        "视觉/音频事件只上传结果、置信度与截图索引，降低带宽压力。",
        "命令按设备主题下发，执行后回传状态，避免单向控制失真。",
        "弱网场景保留心跳、重连、离线缓存和回执补偿机制。",
    ]
    yy = 485
    for b in bullets:
        draw.rectangle((118, yy + 9, 132, yy + 23), fill=COLORS["peach"])
        yy = draw_text(draw, (150, yy), b, F_BODY, COLORS["white"], max_w=505, line_gap=7) + 12
    draw_image_placeholder(draw, (810, 390, 1545, 745), "MQTT 主题图 / 时序图")
    img.save(IMG_DIR / "slide-06.png")


def slide_7() -> None:
    img, draw = base_slide("多模态 AI 算法：环境、视觉、声音、历史趋势融合", "07 / 多模态算法")
    panel(draw, (76, 205, 615, 730), COLORS["cyan"])
    draw_text(draw, (114, 245), "融合输入", F_SUB, COLORS["cyan"], max_w=420)
    nodes = [
        ("环境", COLORS["cyan"], "温湿度、氨气、光照、烟雾"),
        ("视觉", COLORS["peach"], "数量、聚集、倒卧、异常姿态"),
        ("声音", COLORS["pink"], "异常叫声、持续噪声、设备声变"),
        ("历史", COLORS["green"], "趋势变化、人工复核记录"),
        ("复核", COLORS["yellow"], "巡检确认、处置结果回写"),
    ]
    yy = 305
    for label, color, body in nodes:
        draw.rounded_rectangle((116, yy, 540, yy + 62), radius=14, fill=COLORS["panel2"], outline=color, width=2)
        draw.rectangle((136, yy + 17, 164, yy + 45), fill=color)
        draw.text((184, yy + 8), label, font=F_BODY, fill=color)
        draw_text(draw, (270, yy + 14), body, F_TINY, COLORS["white"], max_w=245, line_gap=3)
        yy += 78

    draw.rounded_rectangle((650, 220, 1562, 706), radius=20, fill=(10, 28, 52), outline=(58, 93, 124), width=2)
    draw.text((690, 250), "真实多模态数据流与风险矩阵", font=F_SUB, fill=COLORS["peach"])
    draw_text(draw, (690, 302), "右侧区域在 PPT 中贴入训练流程、风险评分矩阵等真实项目图；背景不放关键文字，避免被覆盖。", F_SMALL, COLORS["muted"], max_w=760)
    for x in range(700, 1520, 85):
        draw.line((x, 365, x, 665), fill=(25, 55, 80), width=1)
    for y in range(365, 665, 62):
        draw.line((700, y, 1520, y), fill=(25, 55, 80), width=1)
    panel(draw, (90, 760, 1510, 858), COLORS["peach"])
    draw_text(draw, (125, 790), "边界说明：系统用于辅助巡检与预警，不替代兽医诊断；模型输出必须绑定传感器数据、截图、模型版本和人工确认记录。", F_SMALL, COLORS["white"], max_w=1340)
    img.save(IMG_DIR / "slide-07.png")


def slide_9() -> None:
    img, draw = base_slide("Web 平台成果展示：一屏协同监测、分析与控制", "09 / Web 成果")
    panel(draw, (74, 210, 515, 772), COLORS["cyan"])
    draw_text(draw, (112, 250), "核心视图", F_SUB, COLORS["cyan"], max_w=350)
    items = [
        ("驾驶舱", "存栏、设备、告警、趋势、边缘 FPS"),
        ("环境监测", "温湿度、氨气、光照、烟雾、联动状态"),
        ("健康风险", "视觉事件、声音事件、风险证据链"),
        ("设备控制", "风扇、雾化、报警、抓拍命令下发"),
        ("模型管理", "模型版本、推理状态、训练迭代记录"),
    ]
    yy = 310
    for idx, (head, body) in enumerate(items, 1):
        color = [COLORS["cyan"], COLORS["peach"], COLORS["pink"], COLORS["green"], COLORS["yellow"]][idx - 1]
        draw.rectangle((112, yy + 6, 145, yy + 39), fill=color)
        draw.text((128, yy + 13), str(idx), font=F_TINY, fill=COLORS["bg"], anchor="ma")
        draw.text((165, yy), head, font=F_BODY, fill=COLORS["white"])
        draw_text(draw, (165, yy + 34), body, F_TINY, COLORS["muted"], max_w=295, line_gap=3)
        yy += 86
    draw_image_placeholder(draw, (585, 198, 1560, 792), "Web 截图拼图")
    img.save(IMG_DIR / "slide-09.png")


def slide_10() -> None:
    img, draw = base_slide("鸿蒙 APP 与微信小程序成果展示：移动端巡检与告警闭环", "10 / 移动端成果")
    panel(draw, (72, 220, 615, 820), COLORS["peach"])
    draw_text(draw, (112, 255), "现场处置闭环", F_SUB, COLORS["peach"], max_w=390)
    steps = ["接收告警", "查看证据", "确认状态", "下发处置", "闭环记录"]
    y = 318
    for i, s in enumerate(steps):
        color = [COLORS["cyan"], COLORS["peach"], COLORS["pink"], COLORS["green"], COLORS["yellow"]][i]
        draw.rounded_rectangle((120, y, 465, y + 52), radius=12, fill=COLORS["panel2"], outline=color, width=2)
        draw.text((150, y + 14), f"{i + 1:02d}", font=F_TINY, fill=color)
        draw.text((220, y + 11), s, font=F_BODY, fill=COLORS["white"])
        if i < len(steps) - 1:
            arrow(draw, (292, y + 52), (292, y + 72), color)
        y += 77
    draw_text(draw, (112, 724), "PC 负责总览分析；移动端负责即时查看、现场处置和闭环记录；小程序提供轻量协同入口。", F_TINY, COLORS["muted"], max_w=420, line_gap=4)
    draw_image_placeholder(draw, (720, 170, 1470, 830), "鸿蒙 APP 截图拼图")
    img.save(IMG_DIR / "slide-10.png")


def slide_12() -> None:
    img, draw = base_slide("应用场景、阶段成果与未来计划", "12 / 应用与计划")
    panel(draw, (70, 195, 630, 802), COLORS["cyan"])
    draw_text(draw, (110, 235), "应用场景", F_SUB, COLORS["cyan"], max_w=430)
    scenarios = ["中小牛舍日常巡检", "规模化养殖场分区监测", "环境联动控制", "疫病风险早筛", "教学实训", "示范基地数字化展示"]
    for i, s in enumerate(scenarios):
        x = 112 + (i % 2) * 245
        y = 300 + (i // 2) * 105
        color = [COLORS["cyan"], COLORS["peach"], COLORS["pink"], COLORS["green"], COLORS["yellow"], COLORS["cyan"]][i]
        draw.rounded_rectangle((x, y, x + 210, y + 68), radius=12, fill=COLORS["panel2"], outline=color, width=2)
        draw.text((x + 105, y + 22), s, font=F_TINY, fill=COLORS["white"], anchor="ma")
    panel(draw, (700, 195, 1550, 462), COLORS["peach"])
    draw_text(draw, (738, 232), "阶段成果（真实图）", F_SUB, COLORS["peach"], max_w=720)
    draw_text(draw, (738, 288), "上方区域在 PPT 中贴入部署拓扑与测试验收矩阵；背景只保留标题与网格，避免真实图遮挡正文。", F_SMALL, COLORS["muted"], max_w=720, line_gap=6)
    for x in range(760, 1480, 76):
        draw.line((x, 342, x, 430), fill=(25, 55, 80), width=1)
    for y in range(342, 430, 44):
        draw.line((760, y, 1480, y), fill=(25, 55, 80), width=1)
    panel(draw, (700, 520, 1550, 802), COLORS["pink"])
    draw_text(draw, (738, 556), "未来路线图", F_SUB, COLORS["pink"], max_w=720)
    stages = [("试点部署", "真实牛舍与传感器标定"), ("算法迭代", "样本扩充与策略验证"), ("设备量产", "OTA 与边缘推理优化"), ("平台运营", "数据安全与运维增强")]
    x = 748
    for idx, (head, body) in enumerate(stages):
        color = [COLORS["cyan"], COLORS["peach"], COLORS["pink"], COLORS["green"]][idx]
        draw.rounded_rectangle((x, 640, x + 170, 730), radius=14, fill=COLORS["panel2"], outline=color, width=2)
        draw.text((x + 85, 656), head, font=F_TINY, fill=color, anchor="ma")
        draw_text(draw, (x + 18, 690), body, F_TINY, COLORS["white"], max_w=135, line_gap=2)
        if idx < 3:
            arrow(draw, (x + 170, 685), (x + 215, 685), color)
        x += 200
    img.save(IMG_DIR / "slide-12.png")


def make_missing_slides() -> None:
    IMG_DIR.mkdir(parents=True, exist_ok=True)
    for number, fn in {6: slide_6, 7: slide_7, 9: slide_9, 10: slide_10, 12: slide_12}.items():
        target = IMG_DIR / f"slide-{number:02d}.png"
        fn()
        versioned = IMG_DIR / f"slide-{number:02d}_v0001.png"
        shutil.copy2(target, versioned)


def merge_metadata() -> dict:
    plan = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    meta = json.loads(META_PATH.read_text(encoding="utf-8"))
    plan_specs = {str(slide["slide_number"]): slide.get("slide_spec", {}) for slide in plan["slides"]}
    pages = {str(slide["slide_number"]): slide.get("page_type", "content") for slide in plan["slides"]}

    meta["title"] = plan.get("title", meta.get("title", "数牧增效智能牛舍监测平台技术汇报"))
    meta["slide_order"] = list(range(1, 14))
    slides_meta = meta.setdefault("slides", {})

    for n in range(1, 14):
        key = str(n)
        rel_img = f"images/slide-{n:02d}_v0001.png"
        if not (OUT_DIR / rel_img).exists():
            raise FileNotFoundError(f"missing slide image: {OUT_DIR / rel_img}")
        spec = copy.deepcopy(plan_specs[key])
        existing = slides_meta.get(key) or {}
        version = {
            "version": 1,
            "action": existing.get("versions", [{}])[0].get("action", "generate"),
            "spec": spec,
            "prompt_file": existing.get("versions", [{}])[0].get("prompt_file", ""),
            "image_snapshot": rel_img,
        }
        slides_meta[key] = {
            "slide_number": n,
            "page_type": pages.get(key, "content"),
            "current_version": 1,
            "image_snapshot": rel_img,
            "versions": [version],
        }

    META_PATH.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    return meta


def build_pptx(meta: dict) -> Path:
    spec = importlib.util.spec_from_file_location("gpt_image2_generate_ppt", GEN_PPT)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {GEN_PPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    path = module.generate_pptx(str(OUT_DIR), list(range(1, 14)), title=meta["title"], metadata=meta)
    if not path:
        raise RuntimeError("generate_pptx returned no path")
    return Path(path)


def main() -> None:
    make_missing_slides()
    meta = merge_metadata()
    pptx = build_pptx(meta)
    print(f"[OK] PPTX: {pptx}")


if __name__ == "__main__":
    main()
