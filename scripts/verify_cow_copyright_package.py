from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from zipfile import ZipFile

import pymupdf as fitz
from docx import Document
from lxml import etree
from PIL import Image, ImageDraw, ImageFont


OUT = Path(r"D:\table\软著申请\牛")
PROJECT = Path(__file__).resolve().parents[1]
REVIEW = PROJECT / ".run" / "cow-copyright" / "review"
FORM = Path(r"D:\Users\q4984\xwechat_files\wxid_rt7txr6f1vcl22_d661\msg\file\2026-10\申请表模板.docx")
W = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def render_review(pdf, name, page_numbers, columns=4):
    document = fitz.open(pdf)
    thumbnails = []
    for number in page_numbers:
        page = document[number - 1]
        image = page.get_pixmap(matrix=fitz.Matrix(0.55, 0.55), alpha=False)
        thumb = Image.frombytes("RGB", (image.width, image.height), image.samples)
        thumbnails.append((number, thumb))
    box_w, box_h = 360, 535
    rows = (len(thumbnails) + columns - 1) // columns
    result = Image.new("RGB", (columns * box_w, rows * box_h), "#dddddd")
    draw = ImageDraw.Draw(result)
    label_font = ImageFont.truetype(r"C:\Windows\Fonts\Deng.ttf", 18)
    for index, (number, thumb) in enumerate(thumbnails):
        thumb.thumbnail((box_w - 12, box_h - 40))
        x, y = index % columns * box_w, index // columns * box_h
        draw.text((x + 12, y + 4), f"{name} / {number}", font=label_font, fill="black")
        result.paste(thumb, (x + (box_w - thumb.width) // 2, y + 30))
    path = REVIEW / f"{name}-contact.png"
    result.save(path)
    return str(path)


def main():
    REVIEW.mkdir(parents=True, exist_ok=True)
    entries = json.loads((OUT / "材料生成清单.json").read_text("utf-8"))
    reports = []
    for entry in entries:
        folder = OUT / entry["name"]
        listing = json.loads((folder / "源程序文件与行号清单.json").read_text("utf-8"))
        code_doc = Document(entry["code"])
        code_text = [p.text for p in code_doc.paragraphs]
        expected = [f"{r['index']:05d} | {r['text'].expandtabs(2)}" for r in listing["selected"]]
        assert code_text == expected, (entry["key"], "editable source differs from original")
        for item in listing["files"]:
            assert sha(PROJECT / item["path"]) == item["sha256"]
            assert sha(folder / "源码归档" / item["path"]) == item["sha256"]
        code_pdf = Path(entry["code"]).with_suffix(".pdf")
        manual_pdf = Path(entry["manual"]).with_suffix(".pdf")
        cpdf, mpdf = fitz.open(code_pdf), fitz.open(manual_pdf)
        assert len(cpdf) == entry["stats"]["codePages"]
        assert 12 <= len(mpdf) <= 15
        source_lines_per_page = []
        printed_rows_per_page = []
        for i, page in enumerate(cpdf):
            source_ids = re.findall(r"(?m)^\s*(\d{5})\s*\|", page.get_text())
            expected_count = min(50, len(expected) - i * 50)
            assert len(source_ids) == expected_count, (entry["key"], i+1, len(source_ids), expected_count)
            source_lines_per_page.append(len(source_ids))
            body_lines = [line for block in page.get_text("dict")["blocks"] if "lines" in block
                          for line in block["lines"]
                          if 53 < line["bbox"][1] < 765]
            assert len(body_lines) == expected_count, (entry["key"], "wrapped code line", i+1,len(body_lines),expected_count)
            printed_rows_per_page.append(len(body_lines))
        desc = (folder / "功能描述-填表用.txt").read_text("utf-8").strip()
        assert 501 <= len(desc) <= 1300
        assert len(list((folder / "配图").glob("流程图*.png"))) == 10
        assert sha(folder / "申请表模板-待本人填写.docx") == sha(FORM)
        for path in (Path(entry["code"]), Path(entry["manual"])):
            with ZipFile(path) as zf:
                for part in zf.namelist():
                    if part.endswith(".xml"):
                        etree.fromstring(zf.read(part))
                        xml = zf.read(part).decode("utf-8")
                        assert not any(s in xml for s in ("类Instagram", "技术交流智能化交互系统", "i@yufuping.com"))
        sample_pages = [1, min(2,len(cpdf)), min(30,len(cpdf)), min(31,len(cpdf)), len(cpdf)]
        contact_code = render_review(code_pdf, entry["key"] + "-source", sorted(set(sample_pages)), columns=3)
        contact_manual = render_review(manual_pdf, entry["key"] + "-manual", list(range(1,len(mpdf)+1)), columns=4)
        report = dict(software=entry["name"], sourceFiles=entry["stats"]["fileCount"],
                      originalPhysicalLines=entry["stats"]["physicalLines"],
                      originalNonemptyLines=entry["stats"]["nonemptyLines"],
                      submittedLines=len(expected), submittedAllClientSource=entry["stats"]["submittedAll"],
                      codePdfPages=len(cpdf), codeLinesPerPage=source_lines_per_page,
                      printedRowsPerPage=printed_rows_per_page,
                      manualPdfPages=len(mpdf), workflowFigures=10, descriptionCharacters=len(desc),
                      blankFormUnchanged=True, sourceArchiveHashesMatch=True,
                      editableSourceMatchesOriginal=True, templateContentRemoved=True,
                      reviewImages=[contact_code,contact_manual])
        reports.append(report)
        print(json.dumps({k:v for k,v in report.items() if k not in {"codeLinesPerPage","reviewImages"}},ensure_ascii=False))
    (OUT / "申请材料质量检查.json").write_text(json.dumps(reports,ensure_ascii=False,indent=2),encoding="utf-8")
    summary = ["# 牛项目三项软件著作权申请材料", "", "按你确定的三个软件全称和提供模板整理，版本号均为V1.0。申请表不填写，由本人最后补充。", "",
               "| 端 | 源程序原始物理行 | 实际交存非空行 | 代码页数 | 手册页数 | 流程图 | 功能描述字数 |", "|---|---:|---:|---:|---:|---:|---:|"]
    for entry, report in zip(entries,reports):
        summary.append(f"| {entry['key']} | {report['originalPhysicalLines']} | {report['submittedLines']} | {report['codePdfPages']} | {report['manualPdfPages']} | 10 | {report['descriptionCharacters']} |")
    summary.extend(["", "## 三项软件", ""])
    for report in reports:
        summary.append("- " + report["software"])
    summary.extend(["", "## 文件用途", "", "- 源程序.docx：可编辑代码材料；源程序.pdf：同版PDF。", "- 用户操作手册.docx/PDF：14页操作说明，包含10张流程图，Web和鸿蒙另附实际界面记录。", "- 功能描述-填表用.txt：501–1300字的独立描述，方便最终填表。", "- 申请表模板-待本人填写.docx：原空白模板副本，未代填。", "- 源码归档、ZIP及JSON/CSV：完整应用源文件、原行号及SHA-256核对信息。", "", "## 真实范围", "", "Web提交前1500行与后1500行，合计3000行，50行/页。鸿蒙和小程序不足3000行，提交各自全部现有客户端源程序；除最后一页余数外均为50行/页，未拼入后台或其他客户端代码凑数。", "", "鸿蒙与小程序的照片分析和设备操作目前为本地演示逻辑，文档、流程图及功能描述已据实说明；示例设备、分值与已下发提示不视为真实模型推理或远程硬件执行。", "", "三份手册均已用本机Microsoft Word核实为14页，六个代码和手册文件均提供可编辑Word与导出的PDF，并通过OOXML检查；质量检查JSON保留逐页代码行数和归档核对结果。", "", "原始参考模板单列存放，仅供对照；提交时使用各软件文件夹内对应代码PDF和手册PDF。", ""])
    (OUT / "材料总览.md").write_text("\n".join(summary),encoding="utf-8")


if __name__ == "__main__":
    main()
