import json
import zipfile
from pathlib import Path

from docx import Document

ROOT = Path(r"D:\table\软著申请\牛")
entries = json.loads((ROOT / "材料生成清单.json").read_text(encoding="utf-8"))
for entry in entries:
    folder = ROOT / entry["name"]
    code = Path(entry["code"])
    manual = Path(entry["manual"])
    document = Document(code)
    ids = [p.text.split("|", 1)[0].strip() for p in document.paragraphs if "|" in p.text]
    expected = entry["stats"]["selectedLines"]
    assert len(ids) == expected, (entry["key"], len(ids), expected)
    with zipfile.ZipFile(manual) as archive:
        media = [name for name in archive.namelist() if name.startswith("word/media/")]
    assert len(media) >= 14, (entry["key"], len(media))
    description = (folder / "功能描述-填表用.txt").read_text(encoding="utf-8").strip()
    assert 501 <= len(description) <= 1300
    print(entry["key"], "source_paragraphs=", len(ids), "media_parts=", len(media))
print("DOCX source, image and description checks passed")
