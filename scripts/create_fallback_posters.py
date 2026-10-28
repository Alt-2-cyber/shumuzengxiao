from __future__ import annotations

from pathlib import Path
from math import cos, sin, pi
import random

from PIL import Image, ImageDraw, ImageFont, ImageFilter


W, H = 2048, 1152
OUT = Path("outputs/imagegen")
FONT_BOLD = "C:/Windows/Fonts/msyhbd.ttf"
FONT_REG = "C:/Windows/Fonts/msyh.ttf"
FONT_HEI = "C:/Windows/Fonts/simhei.ttf"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = FONT_BOLD if bold else FONT_REG
    if not Path(path).exists():
        path = FONT_HEI
    return ImageFont.truetype(path, size=size)


def text_size(draw: ImageDraw.ImageDraw, text: str, fnt: ImageFont.ImageFont) -> tuple[int, int]:
    box = draw.textbbox((0, 0), text, font=fnt)
    return box[2] - box[0], box[3] - box[1]


def rounded(draw: ImageDraw.ImageDraw, box, fill, outline=None, width=2, radius=24):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def glow_line(draw: ImageDraw.ImageDraw, points, color, width=4):
    for scale, alpha in [(5, 28), (3, 45), (1, 210)]:
        rgba = (*color[:3], alpha)
        draw.line(points, fill=rgba, width=width * scale, joint="curve")


def draw_bg(seed: int = 1) -> Image.Image:
    rng = random.Random(seed)
    img = Image.new("RGB", (W, H), "#050812")
    px = img.load()
    for y in range(H):
        for x in range(W):
            t = y / H
            v = int(8 + 22 * (1 - t) + 16 * (x / W))
            px[x, y] = (3, 8 + v // 3, 18 + v)
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d = ImageDraw.Draw(overlay, "RGBA")
    for i in range(26):
        x = int(W * i / 25)
        y = int(H * (0.18 + 0.09 * sin(i * 0.9)))
        d.line([(x, y), (x + 280, y + rng.randint(-80, 120))], fill=(0, 220, 255, 24), width=rng.randint(2, 5))
    for color, y0 in [((0, 210, 255), 270), ((190, 80, 255), 360), ((255, 68, 190), 480)]:
        pts = []
        for x in range(-100, W + 120, 70):
            y = y0 + int(48 * sin(x * 0.008 + seed)) + rng.randint(-18, 18)
            pts.append((x, y))
        glow_line(d, pts, color, 3)
    for _ in range(160):
        x, y = rng.randrange(W), rng.randrange(H)
        d.ellipse((x, y, x + 2, y + 2), fill=(140, 230, 255, rng.randrange(50, 140)))
    img = Image.alpha_composite(img.convert("RGBA"), overlay)
    return img


def title(draw, text: str, subtitle: str | None = None):
    f = font(56, True)
    tw, th = text_size(draw, text, f)
    draw.text(((W - tw) // 2, 52), text, font=f, fill=(245, 252, 255))
    draw.line(((W - tw) // 2 - 40, 126, (W + tw) // 2 + 40, 126), fill=(0, 210, 255, 210), width=4)
    if subtitle:
        sf = font(24)
        sw, _ = text_size(draw, subtitle, sf)
        draw.text(((W - sw) // 2, 142), subtitle, font=sf, fill=(146, 228, 255))


def label(draw, xy, text, color=(0, 210, 255), size=28):
    x, y = xy
    f = font(size, True)
    tw, th = text_size(draw, text, f)
    rounded(draw, (x, y, x + tw + 36, y + th + 24), fill=(8, 28, 45, 205), outline=(*color[:3], 210), width=2, radius=16)
    draw.text((x + 18, y + 10), text, font=f, fill=(235, 250, 255))
    return x + tw + 36, y + th + 24


def arrow(draw, start, end, color=(0, 210, 255)):
    draw.line((start, end), fill=(*color, 210), width=5)
    ang = pi + __import__("math").atan2(start[1] - end[1], start[0] - end[0])
    p1 = (end[0] + 18 * cos(ang - 0.45), end[1] + 18 * sin(ang - 0.45))
    p2 = (end[0] + 18 * cos(ang + 0.45), end[1] + 18 * sin(ang + 0.45))
    draw.polygon([end, p1, p2], fill=(*color, 230))


def chips(draw, items, y=1015):
    f = font(28, True)
    x = 110
    for text, color in items:
        tw, th = text_size(draw, text, f)
        rounded(draw, (x, y, x + tw + 34, y + 58), fill=(8, 20, 34, 220), outline=(*color, 230), radius=18)
        draw.text((x + 17, y + 14), text, font=f, fill=(235, 250, 255))
        x += tw + 58


def poster_04():
    img = draw_bg(4)
    d = ImageDraw.Draw(img, "RGBA")
    title(d, "硬件与多模态 AI：低成本节点支撑主动预警")
    rounded(d, (90, 185, 945, 900), fill=(5, 20, 34, 210), outline=(0, 210, 255, 180), radius=28)
    rounded(d, (1105, 185, 1960, 900), fill=(7, 18, 35, 210), outline=(190, 85, 255, 180), radius=28)
    label(d, (128, 218), "硬件拓扑", (0, 210, 255), 34)
    label(d, (1142, 218), "多模态 AI 融合", (190, 85, 255), 34)

    center = (520, 535)
    d.ellipse((center[0] - 95, center[1] - 95, center[0] + 95, center[1] + 95), fill=(0, 110, 150, 130), outline=(0, 235, 255, 240), width=4)
    d.text((center[0] - 82, center[1] - 24), "ESP32-S3\n主控", font=font(34, True), fill=(245, 255, 255), align="center")
    nodes = [
        ("MaixCam\n视觉", 245, 330, (0, 210, 255)),
        ("INMP441\n声音", 775, 330, (255, 76, 190)),
        ("温湿度\n传感器", 210, 590, (80, 255, 180)),
        ("氨气/光照\n烟雾", 780, 590, (255, 205, 80)),
        ("风扇/雾化\n报警器", 515, 770, (190, 85, 255)),
    ]
    for txt, x, y, c in nodes:
        rounded(d, (x - 105, y - 54, x + 105, y + 54), fill=(10, 33, 50, 225), outline=(*c, 230), radius=18)
        d.text((x - 82, y - 32), txt, font=font(25, True), fill=(240, 252, 255), align="center")
        arrow(d, (x, y + (54 if y < center[1] else -54)), center, c)
    arrow(d, (730, 535), (1038, 535), (0, 210, 255))
    d.text((805, 488), "MQTT / HTTP", font=font(28, True), fill=(148, 232, 255))

    inputs = [("环境阈值", 1240, 330), ("视觉事件", 1510, 330), ("声音事件", 1780, 330), ("历史趋势", 1340, 515), ("人工复核", 1640, 515)]
    hub = (1535, 665)
    for txt, x, y in inputs:
        rounded(d, (x - 90, y - 44, x + 90, y + 44), fill=(18, 28, 55, 225), outline=(0, 210, 255, 190), radius=16)
        d.text((x - 58, y - 17), txt, font=font(27, True), fill=(245, 252, 255))
        arrow(d, (x, y + 44), hub, (110, 230, 255))
    d.ellipse((hub[0] - 115, hub[1] - 78, hub[0] + 115, hub[1] + 78), fill=(78, 25, 115, 190), outline=(255, 76, 190, 230), width=4)
    d.text((hub[0] - 82, hub[1] - 20), "风险评分", font=font(36, True), fill=(255, 245, 255))
    outputs = [("告警等级", 1250, 820), ("证据链", 1535, 820), ("处置建议", 1815, 820)]
    for txt, x, y in outputs:
        arrow(d, hub, (x, y - 44), (255, 76, 190))
        rounded(d, (x - 88, y - 42, x + 88, y + 42), fill=(40, 18, 48, 225), outline=(255, 76, 190, 220), radius=16)
        d.text((x - 56, y - 17), txt, font=font(27, True), fill=(255, 245, 255))
    label(d, (540, 948), "辅助巡检与预警，不替代兽医诊断", (255, 205, 80), 32)
    img.save(OUT / "04-hardware-multimodal-ai.png")


def poster_05():
    img = draw_bg(5)
    d = ImageDraw.Draw(img, "RGBA")
    title(d, "软件成果展示：Web、鸿蒙 APP、小程序协同")
    rounded(d, (86, 190, 1275, 865), fill=(5, 19, 31, 218), outline=(0, 210, 255, 210), radius=28)
    label(d, (124, 220), "Web 驾驶舱", (0, 210, 255), 32)
    rounded(d, (140, 290, 1220, 815), fill=(8, 24, 38, 235), outline=(80, 190, 255, 210), radius=18)
    stats = [("存栏", "128"), ("在线设备", "36"), ("风险告警", "7"), ("模型版本", "v1.8")]
    for i, (k, v) in enumerate(stats):
        x = 175 + i * 250
        rounded(d, (x, 325, x + 210, 425), fill=(11, 35, 55, 220), outline=(0, 210, 255, 150), radius=14)
        d.text((x + 22, 346), k, font=font(24), fill=(150, 225, 255))
        d.text((x + 22, 378), v, font=font(38, True), fill=(245, 255, 255))
    chart = [(180, 610), (270, 540), (360, 565), (450, 505), (540, 530), (630, 470), (720, 500), (810, 445)]
    glow_line(d, chart, (0, 210, 255), 3)
    for x in range(180, 840, 90):
        d.line((x, 455, x, 665), fill=(80, 150, 190, 50), width=1)
    for y in range(455, 685, 42):
        d.line((165, y, 850, y), fill=(80, 150, 190, 50), width=1)
    rounded(d, (890, 470, 1168, 690), fill=(10, 32, 50, 230), outline=(190, 85, 255, 170), radius=16)
    d.text((930, 495), "3D 牛舍态势", font=font(30, True), fill=(240, 252, 255))
    for i in range(5):
        x = 940 + i * 38
        d.rectangle((x, 575, x + 24, 640), outline=(0, 210, 255, 180), width=2)
        d.arc((x - 16, 552, x + 42, 600), 200, 340, fill=(0, 210, 255, 160), width=2)
    d.text((180, 710), "环境趋势", font=font(28, True), fill=(150, 230, 255))
    d.text((910, 710), "风险告警", font=font(28, True), fill=(255, 122, 200))

    phones = [(1390, 245, "鸿蒙 APP"), (1685, 245, "微信小程序")]
    for x, y, name in phones:
        rounded(d, (x, y, x + 235, y + 600), fill=(7, 18, 31, 235), outline=(235, 245, 255, 180), radius=38)
        d.text((x + 48, y + 35), name, font=font(28, True), fill=(245, 252, 255))
        items = ["告警列表", "证据查看", "状态确认", "设备控制", "闭环记录"]
        for i, item in enumerate(items):
            yy = y + 105 + i * 82
            rounded(d, (x + 28, yy, x + 207, yy + 54), fill=(13, 35, 55, 230), outline=(0, 210, 255, 130), radius=12)
            d.text((x + 56, yy + 13), item, font=font(24, True), fill=(230, 250, 255))
    arrow(d, (1275, 520), (1390, 520), (0, 210, 255))
    arrow(d, (1275, 605), (1685, 605), (190, 85, 255))
    label(d, (875, 912), "同一后端 API / 同一告警闭环", (80, 255, 180), 30)
    chips(d, [("总览分析", (0, 210, 255)), ("现场巡检", (80, 255, 180)), ("告警处置", (255, 76, 190)), ("设备控制", (190, 85, 255)), ("模型管理", (255, 205, 80))], 1015)
    img.save(OUT / "05-software-results.png")


def poster_06():
    img = draw_bg(6)
    d = ImageDraw.Draw(img, "RGBA")
    title(d, "创新应用与计划：从原型到试点部署")
    cx, cy = 560, 545
    d.ellipse((cx - 130, cy - 130, cx + 130, cy + 130), fill=(9, 45, 65, 215), outline=(0, 230, 255, 230), width=4)
    d.text((cx - 72, cy - 44), "创新\n闭环", font=font(44, True), fill=(245, 255, 255), align="center")
    modules = [
        ("端边云服协同", 560, 250, (0, 210, 255)),
        ("多模态融合", 260, 430, (190, 85, 255)),
        ("低成本硬件", 325, 735, (80, 255, 180)),
        ("证据链追溯", 800, 735, (255, 205, 80)),
        ("多端协同", 870, 430, (255, 76, 190)),
    ]
    for txt, x, y, c in modules:
        rounded(d, (x - 125, y - 48, x + 125, y + 48), fill=(10, 27, 45, 225), outline=(*c, 230), radius=18)
        d.text((x - 86, y - 17), txt, font=font(28, True), fill=(245, 252, 255))
        arrow(d, (x, y + (48 if y < cy else -48)), (cx, cy), c)

    rounded(d, (1110, 190, 1960, 890), fill=(6, 18, 34, 220), outline=(0, 210, 255, 180), radius=28)
    label(d, (1142, 224), "应用场景", (0, 210, 255), 32)
    scenes = ["中小牛舍巡检", "规模化场区监测", "环境联动控制", "风险早筛", "教学实训", "示范基地展示"]
    for i, sc in enumerate(scenes):
        x = 1150 + (i % 2) * 370
        y = 310 + (i // 2) * 90
        rounded(d, (x, y, x + 310, y + 60), fill=(12, 34, 52, 225), outline=(80, 255, 180, 140), radius=14)
        d.text((x + 24, y + 15), sc, font=font(26, True), fill=(235, 252, 255))
    label(d, (1142, 595), "未来路线", (190, 85, 255), 32)
    stages = ["真实牛舍试点", "传感器标定", "模型样本扩充", "设备 OTA 与平台运营"]
    y = 710
    xs = [1180, 1380, 1580, 1780]
    for i, (x, st) in enumerate(zip(xs, stages), start=1):
        d.ellipse((x - 44, y - 44, x + 44, y + 44), fill=(35, 18, 58, 235), outline=(190, 85, 255, 230), width=3)
        d.text((x - 13, y - 20), str(i), font=font(34, True), fill=(255, 245, 255))
        d.text((x - 82, y + 62), st, font=font(23, True), fill=(235, 245, 255))
        if i < 4:
            arrow(d, (x + 50, y), (xs[i] - 50, y), (190, 85, 255))
    rounded(d, (265, 955, 1785, 1060), fill=(8, 24, 36, 235), outline=(255, 76, 190, 230), radius=24)
    msg = "让牛舍风险更早被看见、被确认、被处置"
    f = font(52, True)
    tw, _ = text_size(d, msg, f)
    d.text(((W - tw) // 2, 978), msg, font=f, fill=(255, 245, 255))
    img.save(OUT / "06-innovation-plan.png")


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for create, name in [
        (poster_04, "04-hardware-multimodal-ai.png"),
        (poster_05, "05-software-results.png"),
        (poster_06, "06-innovation-plan.png"),
    ]:
        path = OUT / name
        if path.exists():
            continue
        create()
        print(f"Wrote {path}")


if __name__ == "__main__":
    main()
