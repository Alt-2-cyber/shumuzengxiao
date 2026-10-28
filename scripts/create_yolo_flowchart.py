# -*- coding: utf-8 -*-
from pathlib import Path
import math
import textwrap

from PIL import Image, ImageDraw, ImageFont, ImageFilter


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "flowcharts"
PNG_OUT = OUT_DIR / "边缘视觉识别-YOLO模型路线流程图.png"
SVG_OUT = OUT_DIR / "边缘视觉识别-YOLO模型路线流程图.svg"

W, H = 1920, 1080

C = {
    "bg0": "#072C25",
    "bg1": "#0A4A3D",
    "panel": "#0B7F62",
    "panel2": "#0D6D61",
    "card": "#F7FFF8",
    "card2": "#EAF8EF",
    "ink": "#07352D",
    "white": "#FFFFFF",
    "muted": "#4E6B61",
    "gold": "#FFE16A",
    "green": "#43E58F",
    "teal": "#45F7D1",
    "blue": "#A7E8FF",
    "orange": "#FFB45C",
    "line": "#66FFD1",
}


def font(path: str, size: int):
    return ImageFont.truetype(path, size)


FONT_REG = r"C:\Windows\Fonts\msyh.ttc"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"
F_TITLE = font(FONT_BOLD, 52)
F_SUB = font(FONT_BOLD, 28)
F_H = font(FONT_BOLD, 31)
F_CARD_H = font(FONT_BOLD, 29)
F_BODY = font(FONT_REG, 24)
F_SMALL = font(FONT_REG, 21)
F_TAG = font(FONT_BOLD, 22)
F_NUM = font(FONT_BOLD, 35)


def rounded(draw, xy, r, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=width)


def center_text(draw, xy, text, fnt, fill, anchor="mm"):
    draw.text(xy, text, font=fnt, fill=fill, anchor=anchor)


def wrap_text(draw, text, fnt, max_w):
    lines = []
    for para in text.split("\n"):
        current = ""
        for ch in para:
            test = current + ch
            if draw.textlength(test, font=fnt) <= max_w:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    return lines


def multiline(draw, x, y, text, fnt, fill, max_w, line_h, align="left"):
    lines = wrap_text(draw, text, fnt, max_w)
    for i, ln in enumerate(lines):
        if align == "center":
            tx = x + max_w / 2
            anchor = "ma"
        else:
            tx = x
            anchor = "la"
        draw.text((tx, y + i * line_h), ln, font=fnt, fill=fill, anchor=anchor)
    return len(lines) * line_h


def arrow(draw, x1, y1, x2, y2, color, width=6):
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    ang = math.atan2(y2 - y1, x2 - x1)
    size = 20
    p1 = (x2, y2)
    p2 = (x2 - size * math.cos(ang - 0.45), y2 - size * math.sin(ang - 0.45))
    p3 = (x2 - size * math.cos(ang + 0.45), y2 - size * math.sin(ang + 0.45))
    draw.polygon([p1, p2, p3], fill=color)


def step_card(draw, x, y, w, h, num, title, body, accent):
    shadow = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    rounded(sd, (x + 8, y + 10, x + w + 8, y + h + 10), 24, (0, 0, 0, 70))
    shadow = shadow.filter(ImageFilter.GaussianBlur(8))
    img.alpha_composite(shadow)

    rounded(draw, (x, y, x + w, y + h), 26, C["card"], "#B7E4C6", 2)
    draw.rectangle((x, y, x + w, y + 18), fill=accent)
    draw.ellipse((x + 28, y + 34, x + 98, y + 104), fill=accent, outline=C["white"], width=4)
    center_text(draw, (x + 63, y + 69), str(num), F_NUM, C["white"])
    draw.text((x + 108, y + 40), title, font=F_CARD_H, fill=C["ink"], anchor="la")
    multiline(draw, x + 42, y + 118, body, F_BODY, C["muted"], w - 84, 34)


def svg_escape(text):
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def add_svg_text(parts, x, y, text, size, weight="400", fill="#FFFFFF", anchor="start"):
    parts.append(
        f'<text x="{x}" y="{y}" font-family="Microsoft YaHei, SimHei, sans-serif" '
        f'font-size="{size}" font-weight="{weight}" fill="{fill}" text-anchor="{anchor}">{svg_escape(text)}</text>'
    )


OUT_DIR.mkdir(parents=True, exist_ok=True)
img = Image.new("RGBA", (W, H), C["bg0"])
draw = ImageDraw.Draw(img)

# Background gradient and subtle waves.
for yy in range(H):
    t = yy / H
    r0, g0, b0 = (7, 44, 37)
    r1, g1, b1 = (8, 83, 64)
    col = (
        int(r0 + (r1 - r0) * t),
        int(g0 + (g1 - g0) * t),
        int(b0 + (b1 - b0) * t),
        255,
    )
    draw.line((0, yy, W, yy), fill=col)

for i in range(9):
    y = 190 + i * 78
    pts = []
    for x in range(-100, W + 120, 40):
        pts.append((x, y + int(math.sin((x + i * 95) / 160) * 18)))
    draw.line(pts, fill=(83, 255, 201, 28), width=2)

draw.rectangle((0, 0, W, 118), fill=(3, 39, 33, 210))
draw.rectangle((0, 118, W, 134), fill=C["green"])
draw.rectangle((0, 130, W, 134), fill=(255, 255, 255, 70))

# Title block.
draw.text((90, 38), "项目创新", font=F_TITLE, fill=C["white"], anchor="la")
rounded(draw, (405, 32, 1080, 82), 25, "#13875F", "#B8FF9C", 2)
center_text(draw, (742, 57), "核心技术2：边缘视觉识别与 YOLO 模型路线", F_SUB, C["white"])
center_text(
    draw,
    (960, 146),
    "以数据结构化传输降本，以本地联动告警增效，确保响应实时性",
    F_SUB,
    C["gold"],
)

# Stage tags.
tags = [
    (156, "硬件采集"),
    (460, "边缘预处理"),
    (764, "轻量推理"),
    (1068, "任务识别"),
    (1372, "结构化输出"),
    (1676, "告警复核"),
]
for x, label in tags:
    rounded(draw, (x - 84, 198, x + 84, 238), 20, (10, 116, 92, 210), "#39FFB9", 2)
    center_text(draw, (x, 218), label, F_TAG, C["white"])

# Flow arrows behind cards.
for x1, x2 in [(300, 390), (604, 694), (908, 998), (1212, 1302), (1516, 1606)]:
    arrow(draw, x1, 500, x2, 500, C["line"], 6)

cards = [
    (
        52,
        280,
        250,
        440,
        1,
        "数据采集",
        "MaixCam 边缘视觉节点接入牛舍视频，同时联动声音、环境与主控数据，形成多源输入。",
        C["green"],
    ),
    (
        356,
        280,
        250,
        440,
        2,
        "本地预处理",
        "在端侧完成抽帧、缩放、目标区域截取和降噪，减少无效视频上传，降低网络与算力压力。",
        C["teal"],
    ),
    (
        660,
        280,
        250,
        440,
        3,
        "YOLO 推理",
        "轻量化 YOLO 在低功耗硬件上完成实时目标检测与初步判断。",
        C["blue"],
    ),
    (
        964,
        280,
        250,
        440,
        4,
        "任务识别",
        "识别体况、站立/躺卧、采食异常、区域越界和局部皮肤/肢体异常等风险信号。",
        C["orange"],
    ),
    (
        1268,
        280,
        250,
        440,
        5,
        "事件输出",
        "输出时间、点位、类别、置信度、截图和短视频片段，让大屏与后台可追溯、可复核。",
        "#8AE66F",
    ),
    (
        1572,
        280,
        250,
        440,
        6,
        "告警闭环",
        "通过 UART/网络联动 ESP32-S3、APP/小程序和大屏，完成告警、确认、处置和记录。",
        "#FFCE55",
    ),
]

for card in cards:
    step_card(draw, *card)

# Bottom outcome panels.
rounded(draw, (92, 790, 880, 970), 28, (9, 125, 95, 224), "#35FFC0", 2)
rounded(draw, (1040, 790, 1828, 970), 28, (9, 125, 95, 224), "#35FFC0", 2)
draw.text((134, 835), "核心优势：降本实时与互证", font=F_H, fill=C["gold"], anchor="la")
multiline(
    draw,
    134,
    890,
    "结构化数据代替全量视频上传，降低传输与存储成本；本地告警缩短响应链路，多模态互证减少误报干扰。",
    F_BODY,
    C["white"],
    680,
    36,
)
draw.text((1082, 835), "应用边界：辅助决策而非替代诊断", font=F_H, fill=C["gold"], anchor="la")
multiline(
    draw,
    1082,
    890,
    "系统输出异常候选与优先级，最终由养殖人员或兽医复核处置；平台沉淀记录，辅助后续优化规则。",
    F_BODY,
    C["white"],
    680,
    36,
)

draw.text((96, 1030), "数牧增效智能牛舍监测平台｜边缘视觉识别流程图", font=F_SMALL, fill=(220, 245, 230, 220), anchor="la")
draw.text((1824, 1030), "MaixCam + YOLO + 本地联动告警", font=F_SMALL, fill=(220, 245, 230, 220), anchor="ra")

img.convert("RGB").save(PNG_OUT, quality=96)

# A lightweight editable SVG source matching the information structure.
svg = [
    f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
    "<defs>",
    '<linearGradient id="bg" x1="0" y1="0" x2="0" y2="1">',
    f'<stop offset="0" stop-color="{C["bg0"]}"/><stop offset="1" stop-color="{C["bg1"]}"/>',
    "</linearGradient>",
    '<filter id="shadow" x="-20%" y="-20%" width="140%" height="140%"><feDropShadow dx="8" dy="10" stdDeviation="6" flood-opacity=".35"/></filter>',
    "</defs>",
    '<rect width="1920" height="1080" fill="url(#bg)"/>',
    f'<rect y="0" width="1920" height="100" fill="#032721" opacity=".92"/><rect y="100" width="1920" height="16" fill="{C["green"]}"/>',
]
add_svg_text(svg, 90, 70, "项目创新", 58, "700", C["white"])
svg.append(f'<rect x="405" y="32" width="675" height="50" rx="25" fill="#13875F" stroke="#B8FF9C" stroke-width="2"/>')
add_svg_text(svg, 742, 66, "核心技术2：边缘视觉识别与 YOLO 模型路线", 28, "700", C["white"], "middle")
add_svg_text(svg, 960, 154, "以数据结构化传输降本，以本地联动告警增效，确保响应实时性", 28, "700", C["gold"], "middle")
for x1, x2 in [(300, 390), (604, 694), (908, 998), (1212, 1302), (1516, 1606)]:
    svg.append(f'<line x1="{x1}" y1="500" x2="{x2}" y2="500" stroke="{C["line"]}" stroke-width="6" stroke-linecap="round"/>')
    svg.append(f'<polygon points="{x2},500 {x2-20},488 {x2-20},512" fill="{C["line"]}"/>')
for x, label in tags:
    svg.append(f'<rect x="{x-84}" y="198" width="168" height="40" rx="20" fill="#0A745C" stroke="#39FFB9" stroke-width="2"/>')
    add_svg_text(svg, x, 226, label, 22, "700", C["white"], "middle")
for x, y, w, h, num, title, body, accent in cards:
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="26" fill="{C["card"]}" stroke="#B7E4C6" stroke-width="2" filter="url(#shadow)"/>')
    svg.append(f'<rect x="{x}" y="{y}" width="{w}" height="18" fill="{accent}"/>')
    svg.append(f'<circle cx="{x+63}" cy="{y+69}" r="35" fill="{accent}" stroke="#fff" stroke-width="4"/>')
    add_svg_text(svg, x + 63, y + 81, str(num), 35, "700", C["white"], "middle")
    add_svg_text(svg, x + 118, y + 69, title, 31, "700", C["ink"])
    wrapped = textwrap.wrap(body, width=13)
    for i, ln in enumerate(wrapped[:6]):
        add_svg_text(svg, x + 42, y + 150 + i * 34, ln, 24, "400", C["muted"])
svg.append(f'<rect x="92" y="790" width="788" height="180" rx="28" fill="#097D5F" stroke="#35FFC0" stroke-width="2"/>')
svg.append(f'<rect x="1040" y="790" width="788" height="180" rx="28" fill="#097D5F" stroke="#35FFC0" stroke-width="2"/>')
add_svg_text(svg, 134, 865, "核心优势：降本实时与互证", 31, "700", C["gold"])
add_svg_text(svg, 1082, 865, "应用边界：辅助决策而非替代诊断", 31, "700", C["gold"])
for i, ln in enumerate(textwrap.wrap("结构化数据代替全量视频上传，降低传输与存储成本；本地告警缩短响应链路，多模态互证减少误报干扰。", width=26)):
    add_svg_text(svg, 134, 920 + i * 36, ln, 24, "400", C["white"])
for i, ln in enumerate(textwrap.wrap("系统输出异常候选与优先级，最终由养殖人员或兽医复核处置；平台沉淀记录，辅助后续优化规则。", width=26)):
    add_svg_text(svg, 1082, 920 + i * 36, ln, 24, "400", C["white"])
add_svg_text(svg, 96, 1038, "数牧增效智能牛舍监测平台｜边缘视觉识别流程图", 21, "400", "#DCF5E6")
add_svg_text(svg, 1824, 1038, "MaixCam + YOLO + 本地联动告警", 21, "400", "#DCF5E6", "end")
svg.append("</svg>")
SVG_OUT.write_text("\n".join(svg), encoding="utf-8")

print(PNG_OUT)
print(SVG_OUT)
