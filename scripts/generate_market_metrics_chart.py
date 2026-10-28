from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "outputs" / "charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_PATH = OUT_DIR / "market_metrics_chart.png"
SVG_PATH = OUT_DIR / "market_metrics_chart.svg"

W, H = 1920, 1080
BG = (246, 249, 252)
INK = (18, 29, 43)
MUTED = (95, 111, 128)
GREEN = (22, 132, 101)
BLUE = (31, 111, 235)
ORANGE = (238, 137, 35)
TEAL = (25, 150, 170)
CARD = (255, 255, 255)
BORDER = (220, 229, 238)
GRID = (228, 235, 242)


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    path = r"C:\Windows\Fonts\msyhbd.ttf" if bold else r"C:\Windows\Fonts\msyh.ttc"
    return ImageFont.truetype(path, size=size)


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def text_center(draw, box, text, fnt, fill):
    x1, y1, x2, y2 = box
    bbox = draw.textbbox((0, 0), text, font=fnt)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((x1 + (x2 - x1 - tw) / 2, y1 + (y2 - y1 - th) / 2 - bbox[1]), text, font=fnt, fill=fill)


def draw_soft_shadow(base, xy, radius=28, offset=(0, 10), blur_layers=12):
    shadow = Image.new("RGBA", base.size, (0, 0, 0, 0))
    sd = ImageDraw.Draw(shadow)
    x1, y1, x2, y2 = xy
    ox, oy = offset
    for i in range(blur_layers, 0, -1):
        alpha = int(34 * (i / blur_layers) ** 2)
        expand = (blur_layers - i) * 2
        sd.rounded_rectangle(
            (x1 + ox - expand, y1 + oy - expand, x2 + ox + expand, y2 + oy + expand),
            radius=radius + expand,
            fill=(22, 41, 64, alpha),
        )
    base.alpha_composite(shadow)


def draw_trend(draw, x, y, w, h, color):
    pts = [
        (x + 24, y + h - 34),
        (x + w * 0.30, y + h - 70),
        (x + w * 0.52, y + h - 46),
        (x + w * 0.72, y + 48),
        (x + w - 24, y + 28),
    ]
    draw.line(pts, fill=color, width=10, joint="curve")
    for px, py in pts:
        draw.ellipse((px - 8, py - 8, px + 8, py + 8), fill=color)


def draw_bar(draw, x, y, w, h, value, max_value, color):
    rounded_rect(draw, (x, y, x + w, y + h), h // 2, (232, 239, 246))
    fill_w = max(16, int(w * value / max_value))
    rounded_rect(draw, (x, y, x + fill_w, y + h), h // 2, color)


def draw_donut(draw, cx, cy, r, pct, color):
    box = (cx - r, cy - r, cx + r, cy + r)
    draw.arc(box, start=0, end=360, fill=(230, 237, 244), width=18)
    draw.arc(box, start=-90, end=-90 + 360 * pct, fill=color, width=18)


def draw_card(base, x, y, w, h, metric, label, color, kind):
    draw = ImageDraw.Draw(base)
    draw_soft_shadow(base, (x, y, x + w, y + h), radius=26)
    rounded_rect(draw, (x, y, x + w, y + h), 26, CARD, BORDER, 2)

    draw.rectangle((x, y, x + 10, y + h), fill=color)
    draw.text((x + 42, y + 42), metric, font=font(64, True), fill=INK)
    draw.text((x + 42, y + 128), label, font=font(34, True), fill=INK)

    if kind == "scale":
        draw_bar(draw, x + 44, y + h - 92, w - 88, 26, 54.4, 110, color)
        draw.text((x + 44, y + h - 54), "54.4 / 100+ 亿", font=font(24), fill=MUTED)
    elif kind == "cagr":
        draw_trend(draw, x + 42, y + h - 128, w - 84, 92, color)
        draw.text((x + 44, y + h - 54), "复合增长率", font=font(24), fill=MUTED)
    elif kind == "control":
        draw_bar(draw, x + 44, y + h - 92, w - 88, 26, 100, 110, color)
        draw.text((x + 44, y + h - 54), "自动化控制系统市场", font=font(24), fill=MUTED)
    else:
        draw_donut(draw, x + w - 92, y + h - 76, 46, 0.375, color)
        draw.text((x + 44, y + h - 54), "财政补贴资金增幅", font=font(24), fill=MUTED)


def main():
    img = Image.new("RGBA", (W, H), BG + (255,))
    draw = ImageDraw.Draw(img)

    for i in range(0, W, 80):
        draw.line((i, 0, i, H), fill=GRID + (80,), width=1)
    for i in range(0, H, 80):
        draw.line((0, i, W, i), fill=GRID + (80,), width=1)

    draw.text((110, 80), "智慧畜牧市场增长指标", font=font(64, True), fill=INK)
    draw.text((112, 158), "牛健康监测、自动化控制与财政补贴三类关键机会数据", font=font(32), fill=MUTED)

    accent = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ad = ImageDraw.Draw(accent)
    ad.ellipse((1460, -180, 2040, 400), fill=(31, 111, 235, 28))
    ad.ellipse((-160, 720, 440, 1320), fill=(22, 132, 101, 24))
    img.alpha_composite(accent)

    card_w, card_h = 760, 300
    left, top = 110, 265
    gap_x, gap_y = 180, 90
    draw_card(img, left, top, card_w, card_h, "54.4亿", "牛健康监测市场规模", GREEN, "scale")
    draw_card(img, left + card_w + gap_x, top, card_w, card_h, "23.9%", "市场复合年增长率", BLUE, "cagr")
    draw_card(img, left, top + card_h + gap_y, card_w, card_h, ">100亿", "自动化控制系统规模", ORANGE, "control")
    draw_card(img, left + card_w + gap_x, top + card_h + gap_y, card_w, card_h, "37.5%", "财政补贴资金增幅", TEAL, "subsidy")

    draw.line((110, 1006, 1810, 1006), fill=(210, 221, 232), width=2)
    draw.text((110, 1025), "数据口径：按提供截图整理生成", font=font(24), fill=MUTED)

    img = img.convert("RGB")
    img.save(OUT_PATH, quality=96)
    SVG_PATH.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="1920" height="1080" viewBox="0 0 1920 1080">
  <defs>
    <style>
      .title{font:700 64px 'Microsoft YaHei',sans-serif;fill:#121d2b}
      .sub{font:400 32px 'Microsoft YaHei',sans-serif;fill:#5f6f80}
      .metric{font:700 64px 'Microsoft YaHei',sans-serif;fill:#121d2b}
      .label{font:700 34px 'Microsoft YaHei',sans-serif;fill:#121d2b}
      .note{font:400 24px 'Microsoft YaHei',sans-serif;fill:#5f6f80}
      .card{fill:#fff;stroke:#dce5ee;stroke-width:2}
      .track{fill:#e8eff6}
    </style>
    <pattern id="grid" width="80" height="80" patternUnits="userSpaceOnUse">
      <path d="M80 0H0V80" fill="none" stroke="#dce8f3" stroke-width="1"/>
    </pattern>
    <filter id="shadow" x="-10%" y="-20%" width="120%" height="150%">
      <feDropShadow dx="0" dy="10" stdDeviation="10" flood-color="#162940" flood-opacity=".14"/>
    </filter>
  </defs>
  <rect width="1920" height="1080" fill="#f6f9fc"/>
  <rect width="1920" height="1080" fill="url(#grid)" opacity=".75"/>
  <circle cx="1750" cy="110" r="290" fill="#1f6feb" opacity=".10"/>
  <circle cx="145" cy="1015" r="295" fill="#168465" opacity=".10"/>
  <text x="110" y="150" class="title">智慧畜牧市场增长指标</text>
  <text x="112" y="195" class="sub">牛健康监测、自动化控制与财政补贴三类关键机会数据</text>

  <g filter="url(#shadow)">
    <rect x="110" y="265" width="760" height="300" rx="26" class="card"/>
    <rect x="110" y="265" width="10" height="300" fill="#168465"/>
    <text x="154" y="375" class="metric">54.4亿</text>
    <text x="154" y="430" class="label">牛健康监测市场规模</text>
    <rect x="154" y="473" width="674" height="27" rx="13.5" class="track"/>
    <rect x="154" y="473" width="333" height="27" rx="13.5" fill="#168465"/>
    <text x="154" y="538" class="note">54.4 / 100+ 亿</text>
  </g>

  <g filter="url(#shadow)">
    <rect x="1050" y="265" width="760" height="300" rx="26" class="card"/>
    <rect x="1050" y="265" width="10" height="300" fill="#1f6feb"/>
    <text x="1094" y="375" class="metric">23.9%</text>
    <text x="1094" y="430" class="label">市场复合年增长率</text>
    <polyline points="1116,495 1294,459 1445,483 1578,484 1746,465" fill="none" stroke="#1f6feb" stroke-width="10" stroke-linejoin="round" stroke-linecap="round"/>
    <g fill="#1f6feb"><circle cx="1116" cy="495" r="8"/><circle cx="1294" cy="459" r="8"/><circle cx="1445" cy="483" r="8"/><circle cx="1578" cy="484" r="8"/><circle cx="1746" cy="465" r="8"/></g>
    <text x="1094" y="540" class="note">复合增长率</text>
  </g>

  <g filter="url(#shadow)">
    <rect x="110" y="655" width="760" height="300" rx="26" class="card"/>
    <rect x="110" y="655" width="10" height="300" fill="#ee8923"/>
    <text x="154" y="765" class="metric">&gt;100亿</text>
    <text x="154" y="820" class="label">自动化控制系统规模</text>
    <rect x="154" y="863" width="674" height="27" rx="13.5" class="track"/>
    <rect x="154" y="863" width="613" height="27" rx="13.5" fill="#ee8923"/>
    <text x="154" y="928" class="note">自动化控制系统市场</text>
  </g>

  <g filter="url(#shadow)">
    <rect x="1050" y="655" width="760" height="300" rx="26" class="card"/>
    <rect x="1050" y="655" width="10" height="300" fill="#1996aa"/>
    <text x="1094" y="765" class="metric">37.5%</text>
    <text x="1094" y="820" class="label">财政补贴资金增幅</text>
    <circle cx="1718" cy="881" r="46" fill="none" stroke="#e8eff6" stroke-width="18"/>
    <circle cx="1718" cy="881" r="46" fill="none" stroke="#1996aa" stroke-width="18" stroke-dasharray="108.4 180.6" transform="rotate(-90 1718 881)"/>
    <text x="1094" y="928" class="note">财政补贴资金增幅</text>
  </g>
  <line x1="110" y1="1006" x2="1810" y2="1006" stroke="#d2dde8" stroke-width="2"/>
  <text x="110" y="1052" class="note">数据口径：按提供截图整理生成</text>
</svg>
""",
        encoding="utf-8",
    )
    print(str(OUT_PATH))
    print(str(SVG_PATH))


if __name__ == "__main__":
    main()
