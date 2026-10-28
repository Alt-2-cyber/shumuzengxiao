from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(r"D:\table\shumuzengxiao")
OUT = ROOT / "outputs" / "market_customer_charts"
OUT.mkdir(parents=True, exist_ok=True)

W, H = 2400, 1350

NAVY = "#17365D"
BLUE = "#1F4E79"
CYAN = "#1C9BD1"
GREEN = "#2E8B57"
LIME = "#88B04B"
YELLOW = "#E2B93B"
ORANGE = "#F28C28"
RED = "#C84B31"
PURPLE = "#7A5CFA"
INK = "#1F2933"
MUTED = "#5E6B78"
BG = "#F6F8FB"
CARD = "#FFFFFF"
WHITE = "#FFFFFF"
LINE = "#D7DEE8"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\msyhbd.ttc" if bold else r"C:\Windows\Fonts\msyh.ttc",
        r"C:\Windows\Fonts\simhei.ttf",
        r"C:\Windows\Fonts\simsun.ttc",
    ]
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size=size)
    return ImageFont.load_default()


F_TITLE = font(58, True)
F_SUB = font(28)
F_H = font(34, True)
F_BODY = font(25)
F_SMALL = font(21)
F_NUM = font(52, True)
F_NOTE = font(18)


def rounded(draw: ImageDraw.ImageDraw, xy, radius=28, fill=CARD, outline=LINE, width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, s, fnt, fill=INK, anchor=None):
    draw.text(xy, s, font=fnt, fill=fill, anchor=anchor)


def wrap(draw: ImageDraw.ImageDraw, s: str, fnt, max_w: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for ch in s:
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


def draw_wrapped(draw, xy, s: str, fnt, max_w: int, fill=INK, line_gap=8):
    x, y = xy
    for line in wrap(draw, s, fnt, max_w):
        text(draw, (x, y), line, fnt, fill)
        y += fnt.size + line_gap


def kpi_card(draw, x, y, w, h, label, value, change, color):
    rounded(draw, (x, y, x + w, y + h), radius=28)
    draw.rectangle((x, y, x + 12, y + h), fill=color)
    text(draw, (x + 36, y + 28), label, F_BODY, MUTED)
    text(draw, (x + 36, y + 78), value, F_NUM, color)
    text(draw, (x + 36, y + 146), change, F_SMALL, INK)


def market_chart() -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    text(draw, (110, 72), "市场分析数据图：牛业规模 × 智慧农业政策 × 牛舍痛点", F_TITLE, NAVY)
    text(draw, (112, 145), "公开行业数据 + 项目痛点测算，说明“低成本节点 + 多模态预警”切入空间", F_SUB, MUTED)

    kpi_w, kpi_h, gap = 515, 205, 34
    y0 = 225
    kpi_card(draw, 110, y0, kpi_w, kpi_h, "2024 年末全国牛存栏", "10047 万头", "同比 -4.4%，存量规模仍大", BLUE)
    kpi_card(draw, 110 + (kpi_w + gap), y0, kpi_w, kpi_h, "2024 年全国肉牛出栏", "5099 万头", "同比 +1.5%，生产保持稳定", GREEN)
    kpi_card(draw, 110 + 2 * (kpi_w + gap), y0, kpi_w, kpi_h, "2024 年全国牛肉产量", "779 万吨", "同比 +3.5%，供给持续增长", ORANGE)
    kpi_card(draw, 110 + 3 * (kpi_w + gap), y0, kpi_w, kpi_h, "农业生产信息化率目标", "30% → 32%", "2026 年以上 / 2028 年以上", PURPLE)

    # Pain-point bar chart
    x1, y1, w1, h1 = 110, 500, 1040, 620
    rounded(draw, (x1, y1, x1 + w1, y1 + h1), radius=30)
    text(draw, (x1 + 36, y1 + 34), "牛舍现场痛点强度（项目测算，5 分制）", F_H, NAVY)
    pain = [
        ("巡检不连续", 4.6, CYAN),
        ("异常发现滞后", 4.5, BLUE),
        ("证据链缺失", 4.4, PURPLE),
        ("AI 落地成本高", 4.3, ORANGE),
        ("环境联动不足", 4.2, GREEN),
        ("数据记录分散", 4.1, YELLOW),
    ]
    bar_x = x1 + 250
    bar_y = y1 + 120
    bar_max = 630
    for idx, (label, score, color) in enumerate(pain):
        y = bar_y + idx * 72
        text(draw, (x1 + 40, y + 8), label, F_BODY, INK)
        draw.rounded_rectangle((bar_x, y + 6, bar_x + bar_max, y + 42), radius=18, fill="#E9EEF5")
        draw.rounded_rectangle((bar_x, y + 6, bar_x + int(bar_max * score / 5), y + 42), radius=18, fill=color)
        text(draw, (bar_x + bar_max + 26, y + 3), f"{score:.1f}", F_BODY, color)

    # Market gap logic panel
    x2, y2, w2, h2 = 1200, 500, 1090, 620
    rounded(draw, (x2, y2, x2 + w2, y2 + h2), radius=30)
    text(draw, (x2 + 36, y2 + 34), "市场缺口与牧云智舍切入逻辑", F_H, NAVY)
    steps = [
        ("规模化场区", "具备信息化投入，但系统重、改造周期长", BLUE),
        ("中小牛舍", "预算有限，仍依赖人工巡检和分散记录", ORANGE),
        ("低成本节点", "ESP32-S3 / MaixCam / 声音节点渐进部署", GREEN),
        ("闭环平台", "Web + APP + 小程序完成确认、处置、复盘", PURPLE),
    ]
    sx, sy = x2 + 50, y2 + 126
    box_w, box_h = 470, 150
    for i, (title, desc, color) in enumerate(steps):
        bx = sx + (i % 2) * 520
        by = sy + (i // 2) * 205
        rounded(draw, (bx, by, bx + box_w, by + box_h), radius=24, fill="#F8FBFF", outline=color, width=4)
        text(draw, (bx + 24, by + 20), title, F_H, color)
        draw_wrapped(draw, (bx + 24, by + 72), desc, F_SMALL, box_w - 48, MUTED, 6)
    # Arrows
    draw.line((sx + box_w, sy + 75, sx + 520, sy + 75), fill=LINE, width=8)
    draw.polygon([(sx + 520, sy + 75), (sx + 492, sy + 58), (sx + 492, sy + 92)], fill=LINE)
    draw.line((sx + 235, sy + box_h, sx + 235, sy + 205), fill=LINE, width=8)
    draw.polygon([(sx + 235, sy + 205), (sx + 218, sy + 177), (sx + 252, sy + 177)], fill=LINE)
    draw.line((sx + 520 + box_w, sy + 75, sx + 520 + box_w, sy + 205), fill=LINE, width=8)
    draw.polygon([(sx + 520 + box_w, sy + 205), (sx + 520 + box_w - 17, sy + 177), (sx + 520 + box_w + 17, sy + 177)], fill=LINE)
    draw.line((sx + box_w, sy + 205 + 75, sx + 520, sy + 205 + 75), fill=LINE, width=8)
    draw.polygon([(sx + 520, sy + 205 + 75), (sx + 492, sy + 205 + 58), (sx + 492, sy + 205 + 92)], fill=LINE)

    note = "数据来源：国家统计局《2024年农业经济形势稳中向好》；农业农村部《全国智慧农业行动计划（2024—2028年）》。痛点强度为项目场景测算。"
    text(draw, (110, 1252), note, F_NOTE, MUTED)
    out = OUT / "market_analysis_data.png"
    img.save(out, quality=95)
    return out


def customer_chart() -> Path:
    img = Image.new("RGB", (W, H), BG)
    draw = ImageDraw.Draw(img)

    text(draw, (110, 72), "意向客户数据图：客户分层与试点转化路径", F_TITLE, NAVY)
    text(draw, (112, 145), "早期以可验证试点为核心，先形成案例，再进入设备渠道和区域农服复制", F_SUB, MUTED)

    # Donut panel
    x1, y1, w1, h1 = 110, 225, 850, 760
    rounded(draw, (x1, y1, x1 + w1, y1 + h1), radius=30)
    text(draw, (x1 + 36, y1 + 34), "早期客户优先级（项目测算）", F_H, NAVY)
    cx, cy, r = x1 + 330, y1 + 395, 230
    segments = [
        ("中小牛舍", 35, GREEN),
        ("高校农业实训基地", 20, BLUE),
        ("地方示范点", 18, CYAN),
        ("畜牧设备经销商", 15, ORANGE),
        ("农服机构", 12, PURPLE),
    ]
    total = sum(v for _, v, _ in segments)
    start = -90
    for label, value, color in segments:
        extent = 360 * value / total
        draw.pieslice((cx - r, cy - r, cx + r, cy + r), start, start + extent, fill=color)
        start += extent
    draw.ellipse((cx - 112, cy - 112, cx + 112, cy + 112), fill=CARD)
    text(draw, (cx, cy - 22), "试点", F_H, NAVY, anchor="mm")
    text(draw, (cx, cy + 30), "优先级", F_BODY, MUTED, anchor="mm")
    lx, ly = x1 + 575, y1 + 150
    for i, (label, value, color) in enumerate(segments):
        y = ly + i * 86
        draw.rounded_rectangle((lx, y, lx + 34, y + 34), radius=8, fill=color)
        text(draw, (lx + 50, y - 2), f"{label}", F_BODY, INK)
        text(draw, (lx + 50, y + 34), f"{value}%", F_SMALL, MUTED)

    # Funnel panel
    x2, y2, w2, h2 = 1010, 225, 1280, 760
    rounded(draw, (x2, y2, x2 + w2, y2 + h2), radius=30)
    text(draw, (x2 + 36, y2 + 34), "商业化验证路径", F_H, NAVY)
    funnel = [
        ("线索触达", "30 家/机构", BLUE),
        ("深度访谈", "10 家", CYAN),
        ("试点部署", "3-5 个场景", GREEN),
        ("可展示案例", "2-3 个案例", ORANGE),
        ("区域复制", "20-50 点位", PURPLE),
    ]
    top_y = y2 + 120
    max_w = 920
    for i, (name, value, color) in enumerate(funnel):
        layer_w = max_w - i * 120
        x = x2 + 170 + i * 60
        y = top_y + i * 102
        h = 74
        pts = [(x, y), (x + layer_w, y), (x + layer_w - 38, y + h), (x + 38, y + h)]
        draw.polygon(pts, fill=color)
        text(draw, (x + 62, y + 17), name, F_BODY, WHITE)
        text(draw, (x + layer_w - 210, y + 17), value, F_BODY, WHITE)
    draw_wrapped(
        draw,
        (x2 + 90, y2 + 660),
        "说明：转化数量为项目商业化验证假设，用于表达路线，不代表已签订单。",
        F_SMALL,
        w2 - 180,
        MUTED,
        6,
    )

    # Bottom matrix cards
    x3, y3, w3, h3 = 110, 1030, 2180, 210
    rounded(draw, (x3, y3, x3 + w3, y3 + h3), radius=30)
    text(draw, (x3 + 36, y3 + 30), "首批客户进入点", F_H, NAVY)
    cards = [
        ("高校实训基地", "教学展示 / 实训", "完整演示包"),
        ("中小牛舍", "环境异常 / 巡检记录", "基础监测包"),
        ("地方示范点", "展示 + 管理闭环", "Web 大屏 + 多端"),
        ("经销/农服", "客户资源 / 售后网络", "渠道合作包"),
    ]
    cw = 485
    for i, (a, b, c) in enumerate(cards):
        x = x3 + 40 + i * 525
        y = y3 + 94
        rounded(draw, (x, y, x + cw, y + 88), radius=18, fill="#F8FBFF", outline="#B8C7D9")
        text(draw, (x + 24, y + 14), a, F_BODY, NAVY)
        text(draw, (x + 24, y + 48), f"{b} → {c}", F_SMALL, MUTED)

    note = "数据口径：客户优先级和转化路径为牧云智舍试点规划测算；用于商业计划展示，非已签约客户数据。"
    text(draw, (110, 1252), note, F_NOTE, MUTED)
    out = OUT / "customer_segments_path.png"
    img.save(out, quality=95)
    return out


if __name__ == "__main__":
    print(market_chart())
    print(customer_chart())
