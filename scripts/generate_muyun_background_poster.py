from __future__ import annotations

import math
import textwrap
from datetime import datetime
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs"
OUT_DIR.mkdir(exist_ok=True)

W, H = 2160, 3840


def font(path: str, size: int) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(path, size=size)


FONT_REG = r"C:\Windows\Fonts\NotoSansSC-VF.ttf"
FONT_SERIF = r"C:\Windows\Fonts\NotoSerifSC-VF.ttf"
FONT_BOLD = r"C:\Windows\Fonts\msyhbd.ttc"

title_f = font(FONT_SERIF, 156)
subtitle_f = font(FONT_REG, 52)
section_f = font(FONT_BOLD, 56)
body_f = font(FONT_REG, 40)
small_f = font(FONT_REG, 32)
chip_f = font(FONT_BOLD, 34)
stage_f = font(FONT_BOLD, 34)
num_f = font(FONT_BOLD, 42)


def lerp(a: int, b: int, t: float) -> int:
    return int(a + (b - a) * t)


def gradient_bg() -> Image.Image:
    img = Image.new("RGB", (W, H))
    px = img.load()
    top = (16, 37, 40)
    mid = (232, 239, 225)
    bottom = (248, 246, 235)
    for y in range(H):
        t = y / (H - 1)
        if t < 0.45:
            q = t / 0.45
            col = tuple(lerp(top[i], mid[i], q) for i in range(3))
        else:
            q = (t - 0.45) / 0.55
            col = tuple(lerp(mid[i], bottom[i], q) for i in range(3))
        for x in range(W):
            vignette = 1 - 0.12 * ((x - W * 0.5) / (W * 0.7)) ** 2
            px[x, y] = tuple(max(0, min(255, int(c * vignette))) for c in col)
    return img


def rounded_rect(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def draw_wrapped(draw: ImageDraw.ImageDraw, text: str, xy, font_obj, fill, width_px: int, line_gap: int = 14):
    x, y = xy
    lines: list[str] = []
    for para in text.split("\n"):
        if not para:
            lines.append("")
            continue
        current = ""
        for ch in para:
            test = current + ch
            if draw.textlength(test, font=font_obj) <= width_px:
                current = test
            else:
                if current:
                    lines.append(current)
                current = ch
        if current:
            lines.append(current)
    for line in lines:
        draw.text((x, y), line, font=font_obj, fill=fill)
        bbox = draw.textbbox((x, y), line or "口", font=font_obj)
        y += bbox[3] - bbox[1] + line_gap
    return y


def add_noise(img: Image.Image, opacity: int = 14) -> Image.Image:
    import random

    noise = Image.new("L", img.size)
    data = bytearray(random.randint(0, 255) for _ in range(W * H))
    noise.frombytes(bytes(data))
    overlay = Image.new("RGBA", img.size, (255, 255, 255, opacity))
    overlay.putalpha(noise.point(lambda p: int(p / 255 * opacity)))
    return Image.alpha_composite(img.convert("RGBA"), overlay)


def draw_hero(draw: ImageDraw.ImageDraw, layer: Image.Image):
    # Curved horizon and barn floor
    draw.pieslice((-440, 560, 2600, 2720), 195, 345, fill=(205, 218, 196, 255))
    draw.polygon([(0, 1220), (2160, 1020), (2160, 1610), (0, 1810)], fill=(117, 88, 62, 255))
    draw.polygon([(0, 1325), (2160, 1145), (2160, 1335), (0, 1560)], fill=(162, 133, 91, 255))
    draw.line([(0, 1220), (2160, 1020)], fill=(231, 224, 194, 140), width=8)

    # Barn structure
    barn = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    bd = ImageDraw.Draw(barn)
    bd.polygon([(250, 1035), (690, 690), (1135, 1035), (1135, 1545), (250, 1545)], fill=(42, 68, 58, 245))
    bd.polygon([(210, 1050), (690, 640), (1185, 1050), (1135, 1105), (690, 745), (260, 1105)], fill=(18, 43, 42, 255))
    bd.rectangle((390, 1130, 610, 1545), fill=(29, 47, 42, 255))
    bd.rectangle((755, 1140, 990, 1390), fill=(71, 93, 73, 255))
    bd.line((690, 745, 690, 1545), fill=(205, 212, 180, 120), width=5)
    bd.line((295, 1100, 1090, 1100), fill=(205, 212, 180, 90), width=4)
    layer.alpha_composite(barn)

    # Cow silhouettes
    def cow(cx, cy, scale, fill):
        body = [cx - 190 * scale, cy - 75 * scale, cx + 185 * scale, cy + 80 * scale]
        draw.rounded_rectangle(body, radius=int(65 * scale), fill=fill)
        draw.ellipse((cx + 145 * scale, cy - 105 * scale, cx + 260 * scale, cy + 15 * scale), fill=fill)
        for lx in [-125, -35, 80, 145]:
            draw.rounded_rectangle((cx + lx * scale, cy + 55 * scale, cx + (lx + 32) * scale, cy + 190 * scale), radius=int(13 * scale), fill=fill)
        draw.polygon([(cx + 230 * scale, cy - 78 * scale), (cx + 290 * scale, cy - 125 * scale), (cx + 262 * scale, cy - 42 * scale)], fill=fill)
        draw.line((cx - 185 * scale, cy - 18 * scale, cx - 255 * scale, cy - 86 * scale), fill=fill, width=max(5, int(10 * scale)))

    cow(560, 1420, 0.92, (25, 33, 31, 245))
    cow(1060, 1470, 0.7, (48, 46, 38, 235))
    cow(1390, 1370, 0.5, (74, 62, 47, 215))

    # Sensor nodes and data arcs
    accent = (38, 174, 151, 255)
    amber = (222, 170, 91, 255)
    nodes = [(1215, 880), (1485, 760), (1735, 960), (1530, 1240), (1850, 1370)]
    for i, (x1, y1) in enumerate(nodes):
        for x2, y2 in nodes[i + 1 :]:
            if abs(x1 - x2) < 520:
                draw.line((x1, y1, x2, y2), fill=(38, 174, 151, 90), width=4)
    for i, (x, y) in enumerate(nodes):
        col = accent if i % 2 == 0 else amber
        draw.ellipse((x - 24, y - 24, x + 24, y + 24), fill=(255, 255, 255, 245))
        draw.ellipse((x - 13, y - 13, x + 13, y + 13), fill=col)
        draw.ellipse((x - 48, y - 48, x + 48, y + 48), outline=(*col[:3], 100), width=4)
    for r, alpha in [(430, 46), (590, 35), (760, 25)]:
        draw.arc((1260 - r, 1120 - r, 1260 + r, 1120 + r), 205, 330, fill=(38, 174, 151, alpha), width=8)


def draw_icon(draw: ImageDraw.ImageDraw, center, kind, color):
    x, y = center
    draw.ellipse((x - 34, y - 34, x + 34, y + 34), fill=color)
    white = (255, 255, 255, 240)
    if kind == "temp":
        draw.rounded_rectangle((x - 9, y - 24, x + 9, y + 14), radius=9, outline=white, width=4)
        draw.ellipse((x - 17, y + 6, x + 17, y + 40), outline=white, width=4)
        draw.line((x + 16, y - 15, x + 28, y - 15), fill=white, width=4)
    elif kind == "gas":
        for i in range(3):
            yy = y - 18 + i * 18
            draw.arc((x - 28, yy - 10, x + 28, yy + 16), 185, 355, fill=white, width=4)
    elif kind == "mic":
        draw.rounded_rectangle((x - 12, y - 26, x + 12, y + 12), radius=10, outline=white, width=4)
        draw.arc((x - 28, y - 3, x + 28, y + 35), 0, 180, fill=white, width=4)
        draw.line((x, y + 32, x, y + 45), fill=white, width=4)
    elif kind == "cloud":
        draw.arc((x - 35, y - 5, x - 5, y + 25), 180, 360, fill=white, width=4)
        draw.arc((x - 15, y - 22, x + 25, y + 22), 180, 360, fill=white, width=4)
        draw.arc((x + 10, y - 6, x + 42, y + 26), 180, 360, fill=white, width=4)
        draw.line((x - 32, y + 12, x + 42, y + 12), fill=white, width=4)
    else:
        draw.rectangle((x - 24, y - 20, x + 24, y + 20), outline=white, width=4)
        draw.line((x - 10, y + 30, x + 10, y + 30), fill=white, width=4)


def draw_panel(draw: ImageDraw.ImageDraw, box, title, body, accent):
    x1, y1, x2, y2 = box
    rounded_rect(draw, box, 34, (255, 255, 255, 225), outline=(220, 225, 211, 255), width=2)
    draw.rectangle((x1, y1, x1 + 12, y2), fill=accent)
    draw.text((x1 + 46, y1 + 36), title, font=section_f, fill=(24, 52, 48))
    draw_wrapped(draw, body, (x1 + 46, y1 + 126), body_f, (53, 70, 63), x2 - x1 - 92, 15)


def draw_stage(draw: ImageDraw.ImageDraw, x, y, num, label, desc, color):
    draw.ellipse((x - 40, y - 40, x + 40, y + 40), fill=color)
    tw = draw.textlength(str(num), font=num_f)
    draw.text((x - tw / 2, y - 31), str(num), font=num_f, fill=(255, 255, 255))
    draw.text((x - 62, y + 70), label, font=stage_f, fill=(27, 54, 50))
    draw_wrapped(draw, desc, (x - 96, y + 124), small_f, (74, 86, 78), 210, 8)


def main() -> Path:
    img = gradient_bg().convert("RGBA")
    img = add_noise(img, 10)
    draw = ImageDraw.Draw(img, "RGBA")

    # Decorative geometry
    draw.ellipse((-580, -520, 760, 840), fill=(12, 34, 37, 255))
    draw.arc((-620, -470, 920, 980), 13, 105, fill=(227, 181, 115, 140), width=8)
    draw.ellipse((1600, 3300, 2480, 4220), outline=(28, 83, 78, 50), width=5)
    draw.ellipse((1680, 3380, 2400, 4100), outline=(209, 153, 84, 55), width=4)

    hero_layer = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    hero_draw = ImageDraw.Draw(hero_layer, "RGBA")
    draw_hero(hero_draw, hero_layer)
    hero_layer = hero_layer.filter(ImageFilter.GaussianBlur(0.2))
    img.alpha_composite(hero_layer)

    # Header
    draw.text((150, 160), "牧云智舍", font=subtitle_f, fill=(211, 229, 210, 245))
    draw.text((150, 238), "肉牛养殖连续感知与数据驱动管理", font=title_f, fill=(255, 251, 235, 255))
    draw.text((158, 430), "从经验巡栏到可解释、可追溯的智能巡检辅助闭环", font=subtitle_f, fill=(205, 231, 219, 235))
    draw.rounded_rectangle((150, 535, 770, 602), radius=34, fill=(38, 174, 151, 190))
    draw.text((190, 547), "项目背景 / 低成本分阶段部署", font=small_f, fill=(255, 255, 246, 255))

    # Main content cards
    left_body = (
        "传统牛舍依赖人工观察牛只精神状态、采食情况和环境变化。"
        "巡检频次有限，夜间、恶劣天气和人员不足时更容易出现盲区。"
        "温湿度、氨气、烟雾、通风状态等环境因素，会影响牛只呼吸道健康和应激水平。"
    )
    right_body = (
        "卧倒时间、活动量、咳嗽、喘鸣、异常叫声等信号，需要与现场环境共同判断。"
        "在中小牛舍中，高成本集中式视频监控和复杂工业控制系统部署门槛高、维护难度大。"
    )
    draw_panel(draw, (120, 1850, 1020, 2380), "人工巡栏的盲区", left_body, (30, 92, 83, 255))
    draw_panel(draw, (1140, 1850, 2040, 2380), "环境与行为需融合判断", right_body, (205, 145, 73, 255))

    # Signal chips
    chips = [
        ("温湿度", "temp", (30, 118, 109, 255)),
        ("氨气", "gas", (205, 145, 73, 255)),
        ("烟雾", "gas", (108, 104, 91, 255)),
        ("通风", "cloud", (45, 130, 155, 255)),
        ("咳嗽/喘鸣", "mic", (33, 89, 82, 255)),
        ("异常叫声", "mic", (172, 107, 67, 255)),
    ]
    draw.text((120, 2500), "关键感知对象", font=section_f, fill=(24, 52, 48))
    x, y = 120, 2600
    for label, kind, col in chips:
        bw = int(draw.textlength(label, font=chip_f)) + 142
        rounded_rect(draw, (x, y, x + bw, y + 94), 47, (255, 255, 255, 220), outline=(219, 222, 207, 255), width=2)
        draw_icon(draw, (x + 56, y + 47), kind, col)
        draw.text((x + 104, y + 25), label, font=chip_f, fill=(37, 56, 50))
        x += bw + 26
        if x > 1740:
            x = 120
            y += 122

    # Closed loop
    loop_box = (120, 2915, 2040, 3465)
    rounded_rect(draw, loop_box, 42, (18, 47, 45, 238), outline=(116, 171, 147, 120), width=2)
    draw.text((170, 2970), "牧云智舍闭环路径", font=section_f, fill=(236, 248, 231))
    draw.text((170, 3048), "用可分阶段部署的低成本节点，把现场数据变成可处置、可复盘的巡检辅助能力。", font=small_f, fill=(193, 218, 203))
    stages = [
        ("1", "连续采集", "环境、声音、图像与活动数据", (38, 174, 151, 255)),
        ("2", "边缘初判", "本地筛查异常与风险片段", (82, 155, 128, 255)),
        ("3", "云端融合", "多源数据关联与趋势研判", (205, 145, 73, 255)),
        ("4", "多端处置", "手机/平板告警与任务流转", (63, 128, 162, 255)),
        ("5", "复盘迭代", "记录留痕，优化阈值和模型", (151, 115, 78, 255)),
    ]
    xs = [305, 690, 1075, 1460, 1845]
    for i in range(len(xs) - 1):
        draw.line((xs[i] + 58, 3235, xs[i + 1] - 58, 3235), fill=(151, 207, 180, 130), width=7)
        draw.polygon([(xs[i + 1] - 72, 3235), (xs[i + 1] - 100, 3218), (xs[i + 1] - 100, 3252)], fill=(151, 207, 180, 150))
    for (num, label, desc, col), sx in zip(stages, xs):
        draw_stage(draw, sx, 3235, num, label, desc, col)

    # Footer
    footer = "为养殖户提供可用、可解释、可追溯的巡检辅助工具"
    draw.text((120, 3588), footer, font=section_f, fill=(26, 57, 52))
    draw.line((120, 3670, 2040, 3670), fill=(31, 88, 82, 100), width=3)
    draw.text((120, 3710), "适用场景：中小牛舍 · 分阶段部署 · 低维护成本 · 数据驱动管理", font=small_f, fill=(77, 90, 80))

    out = OUT_DIR / f"muyun-project-background-poster-{datetime.now():%Y%m%d-%H%M%S}.png"
    img.convert("RGB").save(out, quality=95)
    return out


if __name__ == "__main__":
    print(main())
