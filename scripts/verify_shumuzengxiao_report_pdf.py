from pathlib import Path

from pypdf import PdfReader


PDF = Path("D:/table/shumuzengxiao/\u6570\u7267\u589e\u6548\u667a\u80fd\u725b\u820d\u76d1\u6d4b\u5e73\u53f0\u6280\u672f\u62a5\u544a.pdf")
NEEDLES = [
    "\u6570\u7267\u589e\u6548",
    "ESP32-S3",
    "MaixCam",
    "Spring Boot",
    "Vue3",
    "\u9e3f\u8499 APP",
    "\u521b\u65b0\u70b9",
    "\u6d4b\u8bd5\u9a8c\u8bc1",
]


def main():
    reader = PdfReader(str(PDF))
    text = "\n".join(page.extract_text() or "" for page in reader.pages)
    compact = "".join(text.split())
    missing = [n for n in NEEDLES if "".join(n.split()) not in compact]
    if missing:
        raise RuntimeError("missing in pdf: " + ", ".join(missing))
    print("PDF text verification passed")
    print(f"pages={len(reader.pages)}")
    print(f"chars={len(text)}")
    print(f"file={PDF}")


if __name__ == "__main__":
    main()
