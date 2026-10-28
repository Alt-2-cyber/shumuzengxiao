from pathlib import Path

from pypdf import PdfReader


BASE = Path("D:/table")
PDF_PATH = BASE / "\u7269\u6599\u7533\u8bf7\u8868(3)-\u6570\u7267\u589e\u6548\u5b8c\u6210\u7248.pdf"

NEEDLES = [
    "\u7269\u6599\u91c7\u8d2d\u7533\u8bf7\u62a5\u544a",
    "\u91c7\u8d2d\u786c\u4ef6\u53ca\u4f7f\u7528\u65b9\u5f0f",
    "ESP32-S3 / N16R8 \u5f00\u53d1\u677f",
    "Sipeed MaixCam \u8fb9\u7f18 AI \u6444\u50cf\u5934\u5f00\u53d1\u677f",
    "60w\u5200\u5934",
    "\u9884\u8ba1\u53c2\u4e0e\u6bd4\u8d5b",
    "\u5929\u6d25\u5e02\u5927\u5b66\u751f\u521b\u65b0\u8bad\u7ec3\u8ba1\u5212",
    "\u534e\u5317\u4e94\u7701",
]


def main():
    reader = PdfReader(str(PDF_PATH))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    compact_text = "".join(text.split())
    missing = [needle for needle in NEEDLES if "".join(needle.split()) not in compact_text]
    if missing:
        raise RuntimeError("PDF text check missing: " + " / ".join(missing))
    print("PDF text verification passed")
    print(f"pages={len(reader.pages)}")
    print(f"chars={len(text)}")


if __name__ == "__main__":
    main()
