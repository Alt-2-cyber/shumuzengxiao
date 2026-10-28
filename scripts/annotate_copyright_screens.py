from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / ".run" / "cattle-preview"
OUT = ROOT / ".run" / "cow-copyright" / "screens" / "annotated"
OUT.mkdir(parents=True, exist_ok=True)
FONT = r"C:\Windows\Fonts\msyhbd.ttc"
SMALL = r"C:\Windows\Fonts\msyh.ttc"


def annotate(source_name, target_name, boxes):
    image = Image.open(SOURCE / source_name).convert("RGB")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype(FONT, max(18, image.width // 50))
    small = ImageFont.truetype(SMALL, max(15, image.width // 70))
    for x1, y1, x2, y2, label in boxes:
        draw.rectangle((x1, y1, x2, y2), outline="#E21D2E", width=max(5, image.width // 180))
        top = max(2, y1 - font.size - 12)
        bbox = draw.textbbox((0, 0), label, font=font)
        pad = 8
        draw.rounded_rectangle((x1, top, x1 + bbox[2] - bbox[0] + pad * 2, top + bbox[3] - bbox[1] + pad * 2), radius=5, fill="#E21D2E")
        draw.text((x1 + pad, top + pad), label, fill="white", font=font)
    image.save(OUT / target_name, quality=94)


# The boxes use the real emulator/developer-tool viewport coordinates.
annotate("harmony-news-list.jpeg", "hm-news-list.png", [(735, 240, 1080, 380, "1 订阅设置")])
annotate("harmony-news-favorites.jpeg", "hm-news-favorites.png", [(60, 360, 300, 470, "2 收藏")])
annotate("harmony-news-messages.jpeg", "hm-news-messages.png", [(850, 610, 1215, 760, "3 消息")])
annotate("harmony-news-subscriptions.jpeg", "hm-news-subscriptions.png", [(1030, 520, 1215, 720, "4 开关订阅")])
annotate("harmony-assistant-live.jpeg", "hm-assistant.png", [(45, 2200, 1215, 2600, "5 输入并发送问题")])
annotate("harmony-consultation-cancelled-final.jpeg", "hm-consultation.png", [(45, 2180, 1215, 2400, "6 查看咨询状态")])

annotate("mini-news-list.png", "wx-news-list.png", [(170, 20, 270, 65, "1 订阅设置")])
annotate("mini-news-favorites.png", "wx-news-favorites.png", [(15, 110, 120, 170, "2 收藏")])
annotate("mini-news-messages.png", "wx-news-messages.png", [(330, 205, 420, 260, "3 消息")])
annotate("mini-news-subscriptions.png", "wx-news-subscriptions.png", [(370, 55, 425, 110, "4 开关订阅")])
annotate("mini-assistant-deepseek.png", "wx-assistant.png", [(15, 700, 420, 815, "5 发送或转专家咨询")])
annotate("mini-consultation-receipt.png", "wx-consultation.png", [(120, 625, 310, 715, "6 查看咨询回执")])

print(f"Annotated screenshots written to {OUT}")
