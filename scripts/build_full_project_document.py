from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Iterable, Sequence

from docx import Document
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor


BASE = Path(__file__).resolve().parent.parent
ASSETS = BASE / "report_assets"
OUTPUT = BASE / "文档" / "数牧增效智能牛舍监测平台全项目介绍与工程落地说明书.docx"
CONTENT_DXA = 9360

GREEN = "2F6F46"
DARK = "102216"
TEAL = "1F6B68"
LIGHT_GREEN = "E8F6EC"
LIGHT_TEAL = "E4F3F1"
LIGHT_YELLOW = "FFF4CE"
LIGHT_RED = "FCE9E7"
LIGHT_GRAY = "F5F7F5"
MID_GRAY = "D9E2DC"
TEXT_GRAY = "555E58"

# These directories are generated caches, vendored dependencies, or duplicate
# render outputs. Source, data, reports, and project documentation remain in
# the scan so the report describes the engineering materials rather than the
# dependency tree.
SCAN_EXCLUDED_DIRS = {
    ".git",
    ".pio",
    "node_modules",
    "target",
    "dist",
    "build",
    "__pycache__",
    ".playwright-cli",
    ".run",
    "_hf_image_dataset_tmp",
    "output",
    "outputs",
    "report_rendered",
    "report_pdf_pages",
    "rendered_material_request",
    "review_docx_unzip",
    "review_media",
    "review_rendered_revised",
    "review_rendered_revised_final",
}


def set_run_font(run, font_name="宋体", size=None, bold=None, color=None, italic=None):
    run.font.name = font_name
    run._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), font_name)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if italic is not None:
        run.italic = italic
    if color:
        run.font.color.rgb = RGBColor.from_string(color)


def shade_cell(cell, fill):
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        # CT_TcPr orders shading before noWrap/tcMar/vAlign. Insert it at
        # that schema position because width and margins may already exist.
        insert_before = None
        for tag in (
            "w:noWrap",
            "w:tcMar",
            "w:textDirection",
            "w:tcFitText",
            "w:vAlign",
            "w:hideMark",
            "w:headers",
            "w:cellIns",
            "w:cellDel",
            "w:cellMerge",
            "w:tcPrChange",
        ):
            insert_before = tc_pr.find(qn(tag))
            if insert_before is not None:
                break
        if insert_before is None:
            tc_pr.append(shd)
        else:
            tc_pr.insert(tc_pr.index(insert_before), shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def set_cell_margins(cell, top=100, start=120, bottom=100, end=120):
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for side, value in (("top", top), ("start", start), ("bottom", bottom), ("end", end)):
        node = tc_mar.find(qn(f"w:{side}"))
        if node is None:
            node = OxmlElement(f"w:{side}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_cell_width(cell, width_dxa):
    cell.width = Cm(width_dxa / 567.0)
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(int(width_dxa)))
    tc_w.set(qn("w:type"), "dxa")


def set_table_width(table, width_dxa=CONTENT_DXA):
    tbl_pr = table._tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(int(width_dxa)))
    tbl_w.set(qn("w:type"), "dxa")
    layout = tbl_pr.find(qn("w:tblLayout"))
    if layout is None:
        layout = OxmlElement("w:tblLayout")
        tbl_pr.append(layout)
    layout.set(qn("w:type"), "fixed")


def set_row_cant_split(row):
    tr_pr = row._tr.get_or_add_trPr()
    if tr_pr.find(qn("w:cantSplit")) is None:
        tr_pr.append(OxmlElement("w:cantSplit"))


def set_paragraph_shading(paragraph, fill):
    p_pr = paragraph._p.get_or_add_pPr()
    shd = p_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        # CT_PPrBase places shading before spacing/indentation. Appending it
        # after python-docx paragraph properties produces invalid OOXML.
        insert_before = None
        for tag in (
            "w:tabs",
            "w:suppressAutoHyphens",
            "w:kinsoku",
            "w:wordWrap",
            "w:overflowPunct",
            "w:topLinePunct",
            "w:autoSpaceDE",
            "w:autoSpaceDN",
            "w:bidi",
            "w:adjustRightInd",
            "w:snapToGrid",
            "w:spacing",
            "w:ind",
            "w:contextualSpacing",
            "w:mirrorIndents",
            "w:suppressOverlap",
            "w:jc",
            "w:textDirection",
            "w:textAlignment",
            "w:textboxTightWrap",
            "w:outlineLvl",
            "w:divId",
            "w:cnfStyle",
            "w:rPr",
            "w:sectPr",
            "w:pPrChange",
        ):
            insert_before = p_pr.find(qn(tag))
            if insert_before is not None:
                break
        if insert_before is None:
            p_pr.append(shd)
        else:
            p_pr.insert(p_pr.index(insert_before), shd)
    shd.set(qn("w:fill"), fill)
    shd.set(qn("w:val"), "clear")


def add_page_number(paragraph):
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    run = paragraph.add_run("第 ")
    set_run_font(run, "宋体", 9, color=TEXT_GRAY)
    begin = OxmlElement("w:fldChar")
    begin.set(qn("w:fldCharType"), "begin")
    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = "PAGE"
    end = OxmlElement("w:fldChar")
    end.set(qn("w:fldCharType"), "end")
    run._r.append(begin)
    run._r.append(instr)
    run._r.append(end)
    tail = paragraph.add_run(" 页")
    set_run_font(tail, "宋体", 9, color=TEXT_GRAY)


def configure_document(doc):
    section = doc.sections[0]
    section.page_width = Cm(21.0)
    section.page_height = Cm(29.7)
    section.top_margin = Cm(2.35)
    section.bottom_margin = Cm(2.25)
    section.left_margin = Cm(2.25)
    section.right_margin = Cm(2.25)
    section.header_distance = Cm(1.15)
    section.footer_distance = Cm(1.15)

    normal = doc.styles["Normal"]
    normal.font.name = "宋体"
    normal._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "宋体")
    normal.font.size = Pt(10.8)
    normal.paragraph_format.first_line_indent = Cm(0.74)
    normal.paragraph_format.line_spacing = 1.28
    normal.paragraph_format.space_after = Pt(5)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    heading_specs = {
        "Heading 1": (16, 20, 13, WD_ALIGN_PARAGRAPH.CENTER, 0),
        "Heading 2": (13.5, 13, 8, WD_ALIGN_PARAGRAPH.LEFT, 1),
        "Heading 3": (11.5, 9, 5, WD_ALIGN_PARAGRAPH.LEFT, 2),
    }
    for name, (size, before, after, alignment, outline) in heading_specs.items():
        style = doc.styles[name]
        style.font.name = "黑体"
        style._element.get_or_add_rPr().rFonts.set(qn("w:eastAsia"), "黑体")
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(DARK)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.2
        style.paragraph_format.alignment = alignment
        style.paragraph_format.keep_with_next = True
        style.paragraph_format.outline_level = outline

    header = section.header.paragraphs[0]
    header.alignment = WD_ALIGN_PARAGRAPH.CENTER
    header_run = header.add_run("数牧增效智能牛舍监测平台全项目介绍与工程落地说明书")
    set_run_font(header_run, "宋体", 8.5, color=TEXT_GRAY)
    add_page_number(section.footer.paragraphs[0])

    # python-docx may emit w:zoom with only w:val; Word's schema also
    # requires w:percent when the zoom element is present.
    settings = doc.settings._element
    zoom = settings.find(qn("w:zoom"))
    if zoom is None:
        zoom = OxmlElement("w:zoom")
        settings.append(zoom)
    zoom.set(qn("w:percent"), "100")

    doc.core_properties.title = "数牧增效智能牛舍监测平台全项目介绍与工程落地说明书"
    doc.core_properties.subject = "硬件、边缘 AI、后端、Web、鸿蒙 APP、微信小程序和生产落地"
    doc.core_properties.author = "数牧增效项目组"
    doc.core_properties.comments = "本报告仅使用 D:/table/shumuzengxiao 内的项目资料。"


def add_paragraph(doc, text="", style=None, bold_prefix=None, color=None, italic=False):
    paragraph = doc.add_paragraph(style=style)
    paragraph.paragraph_format.line_spacing = 1.28
    paragraph.paragraph_format.space_after = Pt(5)
    paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    if bold_prefix and text.startswith(bold_prefix):
        first = paragraph.add_run(bold_prefix)
        set_run_font(first, "宋体", 10.8, True, color or DARK)
        rest = paragraph.add_run(text[len(bold_prefix):])
        set_run_font(rest, "宋体", 10.8, color=color, italic=italic)
    else:
        run = paragraph.add_run(text)
        set_run_font(run, "宋体", 10.8, color=color, italic=italic)
    return paragraph


def add_heading(doc, text, level=1):
    paragraph = doc.add_heading(text, level=level)
    for run in paragraph.runs:
        set_run_font(run, "黑体", {1: 16, 2: 13.5, 3: 11.5}.get(level, 11.5), True, DARK)
    return paragraph


def add_caption(doc, text):
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = None
    paragraph.paragraph_format.space_before = Pt(2)
    paragraph.paragraph_format.space_after = Pt(7)
    run = paragraph.add_run(text)
    set_run_font(run, "宋体", 9.2, color=TEXT_GRAY)
    return paragraph


def add_picture(doc, path: Path, width_cm=16.0, caption=None):
    if not path.exists() or path.stat().st_size == 0:
        return False
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = None
    paragraph.paragraph_format.space_after = Pt(2)
    run = paragraph.add_run()
    run.add_picture(str(path), width=Cm(width_cm))
    if caption:
        add_caption(doc, caption)
    return True


def add_table(doc, headers: Sequence[str], rows: Iterable[Sequence[object]], widths=None, header_fill=LIGHT_GREEN, font_size=9.2):
    headers = list(headers)
    rows = [list(row) for row in rows]
    if widths is None:
        base = CONTENT_DXA // len(headers)
        widths = [base] * len(headers)
        widths[-1] += CONTENT_DXA - sum(widths)
    else:
        widths = list(widths)
        if sum(widths) != CONTENT_DXA:
            widths[-1] += CONTENT_DXA - sum(widths)

    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_width(table)
    header_cells = table.rows[0].cells
    set_row_cant_split(table.rows[0])
    for index, title in enumerate(headers):
        cell = header_cells[index]
        set_cell_width(cell, widths[index])
        set_cell_margins(cell, 115, 125, 115, 125)
        shade_cell(cell, header_fill)
        cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        cell.text = ""
        paragraph = cell.paragraphs[0]
        paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        paragraph.paragraph_format.space_after = Pt(0)
        run = paragraph.add_run(str(title))
        set_run_font(run, "黑体", font_size, True, DARK)

    for row in rows:
        cells = table.add_row().cells
        set_row_cant_split(table.rows[-1])
        for index in range(len(headers)):
            value = row[index] if index < len(row) else ""
            cell = cells[index]
            set_cell_width(cell, widths[index])
            set_cell_margins(cell, 95, 125, 95, 125)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            cell.text = ""
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_after = Pt(0)
            paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
            run = paragraph.add_run(str(value))
            set_run_font(run, "宋体", font_size, False, DARK)
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(1)
    return table


def add_callout(doc, label, text, fill=LIGHT_YELLOW):
    table = doc.add_table(rows=1, cols=1)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    set_table_width(table)
    cell = table.cell(0, 0)
    set_cell_width(cell, CONTENT_DXA)
    set_cell_margins(cell, 140, 180, 140, 180)
    shade_cell(cell, fill)
    paragraph = cell.paragraphs[0]
    paragraph.paragraph_format.space_after = Pt(0)
    paragraph.paragraph_format.first_line_indent = None
    first = paragraph.add_run(f"{label}：")
    set_run_font(first, "黑体", 10.5, True, DARK)
    rest = paragraph.add_run(text)
    set_run_font(rest, "宋体", 10.5, False, DARK)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_items(doc, items, numbered=True):
    for index, item in enumerate(items, 1):
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.first_line_indent = None
        paragraph.paragraph_format.left_indent = Cm(0.55)
        paragraph.paragraph_format.right_indent = Cm(0.15)
        paragraph.paragraph_format.space_after = Pt(3)
        marker = f"（{index}）" if numbered else "要点："
        run = paragraph.add_run(marker)
        set_run_font(run, "宋体", 10.8, True, GREEN)
        run = paragraph.add_run(str(item))
        set_run_font(run, "宋体", 10.8, False, DARK)


def add_code_block(doc, text):
    for line in text.splitlines():
        paragraph = doc.add_paragraph()
        paragraph.paragraph_format.first_line_indent = None
        paragraph.paragraph_format.left_indent = Cm(0.35)
        paragraph.paragraph_format.right_indent = Cm(0.35)
        paragraph.paragraph_format.space_after = Pt(0)
        paragraph.paragraph_format.line_spacing = 1.0
        set_paragraph_shading(paragraph, LIGHT_GRAY)
        run = paragraph.add_run(line)
        set_run_font(run, "Consolas", 8.5, color=DARK)
    doc.add_paragraph().paragraph_format.space_after = Pt(1)


def add_status_legend(doc):
    add_table(doc, ["状态标识", "本报告含义", "判定依据"], [
        ("已实现", "代码、页面或工程资料已经存在于本项目目录。", "源代码、配置文件或可运行脚本。"),
        ("已通过自动化测试", "在本次报告生成前已执行并成功。", "编译、Maven 测试或前端构建日志。"),
        ("方案已完成，待实机/现场验证", "工程路径已写入代码和文档，但不能用静态文件代替实物联调。", "需要串口、网络、电源或牛舍现场证据。"),
        ("未启用/受门禁保护", "输出只能保持 feature_only，不产生疾病候选。", "模型头文件中的 kEnabled=false 和发布门禁。"),
    ], widths=[1750, 4050, 3560], header_fill=LIGHT_TEAL)


def optional_picture(doc, name, width, caption):
    return add_picture(doc, ASSETS / name, width, caption)


def load_json(path, fallback):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return fallback


def sha256(path: Path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return "unavailable"


def iter_scanned_files(path: Path):
    """Yield project files while pruning generated/vendor directories."""
    path = path.resolve()
    if path.is_file():
        yield path
        return
    if not path.is_dir():
        return
    for root, dirnames, filenames in os.walk(path):
        dirnames[:] = [name for name in dirnames if name not in SCAN_EXCLUDED_DIRS]
        for filename in filenames:
            yield Path(root) / filename


def scan_path_stats(path: Path):
    count = 0
    total_bytes = 0
    for file_path in iter_scanned_files(path):
        count += 1
        try:
            total_bytes += file_path.stat().st_size
        except OSError:
            pass
    return count, total_bytes


def project_inventory():
    """Return a reproducible top-level inventory for the project appendix."""
    rows = []
    root_file_count = 0
    root_file_bytes = 0
    for child in sorted(BASE.iterdir(), key=lambda item: item.name.lower()):
        if child.is_dir() and child.name in SCAN_EXCLUDED_DIRS:
            continue
        if child.is_file():
            root_file_count += 1
            try:
                root_file_bytes += child.stat().st_size
            except OSError:
                pass
            continue
        count, total_bytes = scan_path_stats(child)
        rows.append((child.name, count, f"{total_bytes / (1024 * 1024):.2f} MB"))
    rows.insert(0, ("根目录文件", root_file_count, f"{root_file_bytes / (1024 * 1024):.2f} MB"))
    total_count = sum(row[1] for row in rows)
    total_bytes = sum(scan_path_stats(child)[1] for child in BASE.iterdir() if not (child.is_dir() and child.name in SCAN_EXCLUDED_DIRS))
    return rows, total_count, total_bytes


def add_cover(doc):
    for _ in range(2):
        doc.add_paragraph()
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = None
    run = paragraph.add_run("数牧增效")
    set_run_font(run, "黑体", 29, True, DARK)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = None
    run = paragraph.add_run("智能牛舍监测平台全项目介绍与工程落地说明书")
    set_run_font(run, "黑体", 20, True, DARK)
    paragraph = doc.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.first_line_indent = None
    run = paragraph.add_run("硬件节点、边缘 AI、平台软件、移动端与生产发布规范")
    set_run_font(run, "宋体", 12.5, False, TEAL)
    optional_picture(doc, "ai-generated-smart-barn.png", 14.7, "图 0-1 智能牛舍端边云服协同场景示意图")
    add_table(doc, ["项目属性", "内容"], [
        ("项目名称", "数牧增效智能牛舍监测平台"),
        ("文档类型", "全项目介绍与工程落地说明书"),
        ("技术栈", "ESP32 / ESP32-S3、MaixCam、Spring Boot、Vue3、HarmonyOS、微信小程序"),
        ("资料范围", "仅使用 D:/table/shumuzengxiao 内的项目资料"),
        ("编制日期", "2026 年 9 月 2 日"),
    ], widths=[2000, 7360], header_fill=LIGHT_GREEN, font_size=9.8)
    add_callout(doc, "阅读提示", "本说明书把已实现、已自动化验证、待实机验证和生产前置条件分开陈述。声音疾病模型与三位置跛行模型当前均保持 feature_only，疾病相关输出只能作为筛查或人工分诊线索。", LIGHT_YELLOW)
    doc.add_page_break()


def add_document_note(doc):
    add_heading(doc, "编制说明与完成度判定", 1)
    add_paragraph(doc, "本说明书面向项目答辩、工程交接、现场联调和后续生产试点。文档内容以 D:/table/shumuzengxiao 当前目录中的源代码、配置、训练报告、数据库脚本、论文索引、页面截图和测试结果为准。没有从项目目录外引入硬件型号、现场测量值或临床结论。")
    add_paragraph(doc, "项目目前已经形成软件平台、硬件固件、边缘视觉程序、模型训练工具和疾病生产治理资料的完整骨架。需要特别区分：编译通过说明代码可构建，不等于传感器已接线正确；页面可以展示数据，不等于现场数据已持续接入；模型有离线指标，不等于已经满足临床发布门禁。")
    add_status_legend(doc)
    add_heading(doc, "章节导航", 2)
    sections = [
        "1 项目概述与建设目标", "2 养殖痛点与需求分析", "3 系统总体架构", "4 硬件组成、接线与供电",
        "5 ESP32、牛身节点与 MaixCam 固件", "6 通信协议、数据流与实时遥测", "7 三位置 IMU 行为与跛行筛查",
        "8 INMP441 声音健康风险筛查与论文依据", "9 多模态风险融合与疾病边界", "10 后端、数据库与 API",
        "11 Web、鸿蒙 APP 与微信小程序", "12 数据治理、权限与审计", "13 测试验证与当前完成度",
        "14 生产部署、运维与验收", "15 创新点与应用价值", "16 路线图与风险", "17 项目文件索引", "附录：接口、接线、论文与命令清单",
    ]
    add_items(doc, sections)
    add_callout(doc, "安全边界", "本平台不是兽医诊断系统，不输出疾病阳性/阴性，不生成用药处方，不因传感器正常而排除口蹄疫，也不允许用公开行为或普通牛叫数据绕过临床发布门禁。", LIGHT_RED)
    doc.add_page_break()


def section_1(doc):
    add_heading(doc, "1 项目概述与建设目标", 1)
    add_heading(doc, "1.1 项目背景与定位", 2)
    add_paragraph(doc, "数牧增效智能牛舍监测平台面向中小规模肉牛养殖场，定位为低成本、可解释、可扩展的主动监测系统。项目把牛舍环境、牛只运动、声音事件、局部视觉、边缘设备控制和人工复核放到同一条数据链路中，目标是帮助管理人员优先发现值得检查的牛只或栏位，并保留足够证据供复核和后续模型改进。")
    add_paragraph(doc, "系统采用 ESP32 系列节点完成传感器采集和现场控制，MaixCam 完成视觉推理，Spring Boot 完成数据服务和风险融合，Vue3 Web 负责管理驾驶舱，HarmonyOS 应用和微信小程序负责移动巡检。项目设计强调本地先响应、边缘先筛选、平台统一归档、人工最终复核。")
    optional_picture(doc, "multimodal-dataflow.png", 16.0, "图 1-1 多模态数据从现场采集到风险复核的主链路")
    add_heading(doc, "1.2 建设目标", 2)
    add_items(doc, [
        "建立温湿度、氨气趋势、光照、烟雾/火焰和执行器状态的连续采集与展示能力。",
        "建立颈部、背部、腿部三位置运动采集能力，为行为分析和后续跛行筛查积累同步原始数据。",
        "建立 INMP441 声音特征采集与可回放归档能力，为咳嗽、喘鸣等呼吸道风险候选提供数据基础。",
        "建立 MaixCam 本地视觉事件、关键截图、模型版本和真实牛只身份关联能力。",
        "建立后端风险融合、告警闭环、临床复核、模型发布和审计链路。",
        "建立 Web、鸿蒙 APP 和微信小程序的统一业务入口，支撑电脑管理与移动巡检。",
    ])
    add_heading(doc, "1.3 当前工程范围", 2)
    add_table(doc, ["子系统", "已经具备", "当前限制"], [
        ("现场综合演示节点", "普通 ESP32 DevKit 固件；环境、三位置 IMU、OLED、MAX30102、INMP441、B-1、风扇、LED、蜂鸣器等代码。", "需要按实际丝印接线、稳定供电并用串口日志完成实机验收。"),
        ("牛身节点", "独立 ESP32 项目；ADXL345、MLX90614、MAX30102、电池电压、WiFi/MQTT 和串口配置。", "当前是单牛节点工程，批量部署还需耳标、功耗和防护验证。"),
        ("MaixCam", "摄像头、YOLO 加载、事件状态机、截图、UART、MQTT/HTTP 上报。", "没有本地模型文件或现场数据时只显示画面和状态，不产生可靠疾病事件。"),
        ("行为模型", "公开颈部单传感器六分类随机森林已导出为 ESP32 头文件。", "背部和腿部目前为规则融合，不能写成真正三位置训练模型。"),
        ("声音模型", "公开数据基础声学基线、质量门禁、训练脚本和临床清单工具。", "无临床咳嗽/喘鸣样本，头文件 kEnabled=false。"),
        ("跛行模型", "三位置 20 Hz 临床采集、临床签核、血缘校验和训练发布脚本。", "没有通过独立动物和外部测试，头文件 kEnabled=false。"),
        ("平台软件", "13 个后端 Controller、JPA 数据层、WebSocket、Vue3 页面、移动端原型。", "现场 MQTT、真实身份、权限部署和连续运行仍需试点验收。"),
    ], widths=[1900, 3900, 3560])


def section_2(doc):
    add_heading(doc, "2 养殖痛点与需求分析", 1)
    add_heading(doc, "2.1 现场问题", 2)
    add_paragraph(doc, "牛舍健康异常通常由多个弱信号叠加出现。高湿、氨气升高、通风不足可能构成呼吸道风险背景；咳嗽或喘鸣是需要回放复核的声音事件；活动下降、卧倒时间变化和腿部冲击异常是运动线索；眼鼻或蹄部外观异常需要视觉或人工检查。单一传感器不具备稳定的疾病判别能力，因此平台把“证据收集与复核优先级”作为主要业务目标。")
    add_table(doc, ["现场痛点", "传统方式", "平台方案"], [
        ("异常发现滞后", "巡栏有时间间隔，短时咳嗽、跌倒或火情可能被错过。", "端侧按周期采样，告警事件即时生成，关键事件留存截图或音频。"),
        ("环境与个体信息分离", "温湿度、牛只行为和人工记录分散在不同表格。", "统一设备 ID、牛只 ID、栏位、时间戳和证据引用。"),
        ("数据无法复核", "口头描述缺少原始证据，难以分析误报。", "保存 WAV、NDJSON、图片、模型版本、阈值、审查人和处理结论。"),
        ("网络和算力受限", "持续上传视频和音频成本高，弱网时不稳定。", "MaixCam 本地推理，ESP32 只传结构化遥测；关键原件按权限归档。"),
        ("设备故障不透明", "传感器不读数时容易被当成正常。", "遥测中明确 missing、invalid、stale、feature_only 等状态。"),
        ("控制动作缺少审计", "手工开关风扇、报警器后难以追责。", "控制命令有角色权限、状态回执、命令历史和审计记录。"),
    ], widths=[2000, 3600, 3760])
    add_heading(doc, "2.2 用户角色与流程", 2)
    add_table(doc, ["角色", "关心内容", "主要操作"], [
        ("养殖户/场长", "整体风险、设备在线率、未闭环告警。", "查看驾驶舱、安排复核、控制风扇或报警。"),
        ("巡检人员", "具体牛只、截图、音频、体温和步态结果。", "现场复核、录入临床检查、上传图片或视频引用。"),
        ("兽医/临床负责人", "临床标签、复核证据、模型发布风险。", "签核音频和 IMU 会话，确认或否决发布条件。"),
        ("技术维护人员", "供电、传感器、网络、固件和日志。", "串口调试、设备注册、故障处理、模型回滚。"),
        ("管理员", "权限、模型、审计、数据库和备份。", "管理角色密钥、批准/撤回模型、导出审计记录。"),
    ], widths=[1900, 3900, 3560])
    add_heading(doc, "2.3 最小业务闭环", 2)
    add_items(doc, [
        "发现：设备或边缘节点产生可追溯的环境、运动、声音或视觉事件。",
        "关联：事件关联牛舍、设备、真实耳标/管理编号、时间窗口和模型版本。",
        "融合：后端按个体基线、环境背景和独立证据生成筛查风险。",
        "复核：巡检人员或兽医回放音频、查看图片、测量核心体温并填写步态/蹄部结果。",
        "处置：平台记录告警、人工交接、现场动作和设备控制回执。",
        "回流：只有经过授权和签核的样本才进入训练清单，模型版本不可覆盖并可撤回。",
    ])


def section_3(doc):
    add_heading(doc, "3 系统总体架构", 1)
    optional_picture(doc, "architecture-diagram.png", 16.0, "图 3-1 数牧增效端、边、云、服总体架构")
    add_heading(doc, "3.1 分层设计", 2)
    add_table(doc, ["层级", "主要组件", "职责"], [
        ("端侧感知与执行", "传感器、ESP32、OLED、LED、蜂鸣器、风扇驱动。", "采样、滤波、本地阈值控制、声光报警和状态显示。"),
        ("边缘 AI", "MaixCam、摄像头、SD 卡、INMP441 特征采集。", "本地视觉推理、跟踪、事件截图、声音事件候选和短时音频归档。"),
        ("平台服务", "Spring Boot 3.3.5、JPA、WebSocket、H2/MySQL。", "接收、校验、持久化、风险融合、临床复核、模型发布和审计。"),
        ("应用服务", "Vue3 Web、HarmonyOS、微信小程序。", "驾驶舱、环境、健康、行为、音频、临床、设备、模型和移动巡检。"),
    ], widths=[1900, 3450, 4010])
    add_heading(doc, "3.2 数据和控制闭环", 2)
    optional_picture(doc, "alarm-closed-loop.png", 16.0, "图 3-2 环境异常、健康筛查与人工处置闭环")
    optional_picture(doc, "edge-sequence-flow.png", 16.0, "图 3-3 端边云服数据与控制时序")
    add_paragraph(doc, "安全相关控制动作采用本地优先原则。火焰和高氨气等环境信号由 ESP32 先执行规则，风扇和报警状态再上报平台；视觉和声音节点先筛选，后端保留原件与证据关联；健康风险必须通过证据门禁和临床复核流程，不能由一条遥测或一段普通牛叫直接生成。")
    add_heading(doc, "3.3 关键设计原则", 2)
    add_table(doc, ["原则", "工程落地"], [
        ("本地先响应", "环境告警和执行器动作不等待云端返回，云端负责记录和管理。"),
        ("边缘先筛选", "MaixCam 本地处理图像，ESP32 提取声音特征，减少无效原始数据上行。"),
        ("身份可追溯", "真实 cattleId 必须来自耳标、RFID 或人工关联，视觉 trackId 不能冒充牛只身份。"),
        ("数据质量显式化", "missing、stale、invalid、rejected、feature_only 都作为状态保留。"),
        ("模型不可越权", "模型发布必须有数据清单、临床证据、外部验证、审批和固件哈希。"),
        ("人机协同", "模型只排序复核优先级，兽医和主管部门承担临床、隔离和报告决定。"),
    ], widths=[2200, 7160])


def section_4(doc):
    add_heading(doc, "4 硬件组成、接线与供电", 1)
    optional_picture(doc, "hardware-topology.png", 16.0, "图 4-1 现场硬件拓扑与接口分配")
    add_heading(doc, "4.1 硬件清单与分工", 2)
    add_table(doc, ["硬件", "接口/地址", "部署位置", "用途与边界"], [
        ("普通 ESP32 综合演示节点", "GPIO、I2C、I2S、UART", "控制箱/台架", "环境采集、三位置 IMU 汇总、声音特征、B-1、LED/蜂鸣器/风扇。"),
        ("牛身 ESP32 节点", "I2C、ADC、WiFi/MQTT", "牛身/项圈", "单牛运动、红外温度趋势、心率模块和电池电压上报。"),
        ("MPU-9250/6500 两块", "I2C 0x68、0x69", "颈部、腿部", "三轴加速度和三轴角速度；用于行为特征和跛行采集。"),
        ("ADXL345", "I2C 0x53", "背部", "三轴加速度；用于躯干姿态和活动趋势。"),
        ("SHT31 / DHT11", "I2C 0x44 / GPIO4", "牛舍", "优先 SHT31，DHT11 作为兼容回退。"),
        ("GY-302 / BH1750", "I2C 0x23 或 0x5C", "牛舍", "光照趋势；固件自动兼容两个地址。"),
        ("MAX30102", "I2C 0x57", "台架/接触式位置", "读取 IR/Red 并尝试心率血氧；牛身安装需固定接触和临床标定。"),
        ("B-1 红外测温", "UART 38400 8N1", "对准目标", "非接触体表温度趋势，不等同牛核心体温。"),
        ("INMP441", "I2S", "牛舍定向拾音", "声音特征和两秒音频片段；受风噪、机械噪声和安装位置影响。"),
        ("MaixCam", "UART/MQTT/HTTP", "牛舍摄像机点位", "本地视觉检测、跟踪、截图和事件上报。"),
    ], widths=[2250, 2250, 1900, 2960], font_size=8.7)
    add_heading(doc, "4.2 电源总线与安全", 2)
    add_code_block(doc, "ESP32 3V3 -> 3.3V 电源轨\nESP32 GND -> 公共 GND 轨\nESP32 VIN/5V -> 5V 外设电源轨（仅供允许 5V 的模块/风扇）\nMaixCam -> 独立稳定 5V，建议至少 2A\n执行器 -> 独立负载电源，经继电器或 MOSFET 隔离，和 ESP32 共地")
    add_table(doc, ["项目", "要求"], [
        ("3.3V 稳定性", "ESP32、I2C 传感器、INMP441、B-1 按模块要求使用稳定 3.3V；不要把多个不确定的 3.3V 输出直接并联。若需要并联，必须确认电源输出端允许并联、输出电压一致、共地并有足够电流余量。"),
        ("5V 与 3.3V 分区", "MQ 模块和风扇等 5V 负载不能把高电平模拟输出直接送进 ESP32 ADC；MQ AO 使用 5V 时必须做分压。"),
        ("电机/继电器干扰", "风扇和雾化器使用隔离驱动、续流/浪涌保护、独立供电和保险丝，避免启动瞬间造成 ESP32 复位。"),
        ("现场防护", "建议 IP65 控制箱、防水接头、端子排、线缆应力释放、保险丝、TVS、手动急停和维护标签。"),
        ("接线原则", "接线或改线前断电，按 PCB 丝印确认 VCC/GND，不按线色猜测；所有设备必须公共地。"),
    ], widths=[2100, 7260])
    add_heading(doc, "4.3 I2C 总线接线", 2)
    add_paragraph(doc, "三块运动传感器采用同一条 I2C 总线：ESP32 D21/GPIO21 为 SDA，D22/GPIO22 为 SCL，所有 I2C 模块共用 3.3V 和 GND。两块 MPU 依靠 AD0 区分地址，必须一低一高；若都为 0x68，程序无法区分。")
    add_table(doc, ["身体位置", "模块", "地址选择脚", "ESP32 接线"], [
        ("颈部/项圈", "MPU-9250/6500", "AD0 -> GND；NCS -> 3V3（I2C 模式）", "VCC -> 3V3；GND -> GND；SDA -> D21；SCL -> D22；EDA/ECL/INT/FSYNC 不接。"),
        ("背部", "ADXL345", "CS -> 3V3；SDO -> GND", "VCC -> 3V3；GND -> GND；SDA -> D21；SCL -> D22；INT1/INT2 不接。"),
        ("腿部", "MPU-9250/6500", "AD0 -> 3V3；NCS -> 3V3（I2C 模式）", "VCC -> 3V3；GND -> GND；SDA -> D21；SCL -> D22；EDA/ECL/INT/FSYNC 不接。"),
        ("牛舍环境", "SHT31", "默认地址", "VCC -> 3V3；GND -> GND；SDA/SCL -> D21/D22；地址 0x44。"),
        ("光照", "GY-302/BH1750", "ADDR -> GND 为 0x23；ADDR -> 3V3 为 0x5C", "VCC -> 3V3；GND -> GND；SDA/SCL -> D21/D22。"),
        ("显示", "SH1106 OLED", "默认 0x3C", "VCC -> 3V3；GND -> GND；SDA/SCL -> D21/D22。"),
        ("心率血氧", "MAX30102", "默认 0x57", "VCC -> 3V3；GND -> GND；SDA/SCL -> D21/D22；INT 不接。"),
    ], widths=[1600, 2100, 2350, 3310], font_size=8.4)
    add_heading(doc, "4.4 INMP441 六针接线", 2)
    add_table(doc, ["INMP441 丝印", "ESP32", "说明"], [
        ("VDD", "3V3", "只能按模块规格使用 3.3V。"),
        ("GND", "GND", "必须与 ESP32 共地。"),
        ("SCK", "D5", "I2S BCLK。"),
        ("WS", "D16", "I2S LRCLK/左右声道时钟。"),
        ("SD", "D17", "数字音频数据输出，不是模拟 AO。"),
        ("L/R", "GND", "选择左声道，与当前固件的槽位自动校准一致。"),
    ], widths=[2200, 1600, 5560])
    add_heading(doc, "4.5 B-1 UART 接线", 2)
    add_paragraph(doc, "当前综合演示固件使用 B-1 UART 方式，串口为 38400、8 数据位、无校验、1 停止位。B-1 的 TX/RX 必须交叉连接，当前代码配置为 ESP32 RX=D23、TX=D19，因此接线是 B-1 TX -> ESP32 D23，B-1 RX -> ESP32 D19。")
    add_table(doc, ["B-1 丝印", "ESP32 当前配置", "注意"], [
        ("TX", "D23 / GPIO23（ESP32 RX）", "交叉接收；不要按旧的 D35/D13/D18 方案接，除非同步修改 config.h 并重新验证。"),
        ("RX", "D19 / GPIO19（ESP32 TX）", "交叉发送；保持与代码 PIN_B1_UART_TX 一致。"),
        ("VDD", "3V3", "官方资料要求 3.3V，禁止直接接 5V。"),
        ("GND", "GND", "和 ESP32、其他模块公共地。"),
    ], widths=[1900, 3150, 4310], header_fill=LIGHT_TEAL)
    add_paragraph(doc, "固件上电后发送测温请求和体温模式命令，按包头、长度、累加校验和、包尾校验后才更新温度。B-1 读数是目标表面温度趋势，受毛发、距离、角度、风速和环境影响，不能写入接触式核心体温临床检查接口。")
    add_heading(doc, "4.6 其他 GPIO 接线", 2)
    add_table(doc, ["模块", "引脚/信号", "ESP32 当前 GPIO", "备注"], [
        ("DHT11", "DATA", "D4", "SHT31 正常时优先使用 SHT31，DHT11 作为回退。"),
        ("火焰传感器", "DO", "D32", "当前为低电平有效；接线和模块逻辑要以丝印/实测为准。"),
        ("MQ", "AO", "D34", "若模块 5V 供电，AO 必须电阻分压后再进 ADC。"),
        ("三色 LED", "绿/黄/红", "D25/D26/D27", "正常/预警/报警；每个 LED 串限流电阻。"),
        ("蜂鸣器", "信号/正极", "D33", "无源蜂鸣器使用 PWM 音调；有源模块需修改 BUZZER_ACTIVE_MODULE。"),
        ("风扇驱动板", "GPIO/GND/VCC", "D14/GND/5V", "GPIO 只控制驱动板，不能直接带电机。"),
        ("编码器", "CLK/DT/SW", "D35/D13/D18", "当前 ENCODER_ENABLED=false，没有编码器时不接。"),
    ], widths=[1900, 2200, 1950, 3310], font_size=8.7)
    add_callout(doc, "接线验收", "上电前先断开执行器负载，使用万用表确认 3.3V、5V 和 GND 没有短路；上电后先看 I2C scan、B-1 原始字节、INMP441 channel/status 和三个 IMU 状态，再接入风扇或报警负载。", LIGHT_RED)


def section_5(doc):
    add_heading(doc, "5 ESP32、牛身节点与 MaixCam 固件", 1)
    add_heading(doc, "5.1 现场综合演示节点", 2)
    add_paragraph(doc, "目录为 硬件代码/现有硬件演示节点，适配普通 ESP32 DevKit。PlatformIO 默认环境为 demo_esp32，历史测试端口曾出现 COM13、COM17、COM18、COM19，当前项目资料以设备枚举结果为准。该固件把环境采集、三位置运动采样、MAX30102、声音特征、B-1 UART、OLED、本地 LED/蜂鸣器和风扇控制集中在一块板上，适合台架演示和协议联调。")
    add_table(doc, ["任务", "实现方式", "当前周期或状态"], [
        ("环境采样", "SHT31 优先，DHT11 回退；BH1750/GY-302；MQ ADC；火焰 DO。", "综合遥测约 2 秒一帧；缺失模块显式标记。"),
        ("运动采样", "MPU 0x68、ADXL345 0x53、MPU 0x69。", "50 ms 采样，即 20 Hz；普通遥测输出特征。"),
        ("临床运动采集", "仅在平台创建 motion_capture 会话后输出 mcs NDJSON。", "限时 1 到 5 分钟；串口背压或传感器失败即终止。"),
        ("声音", "I2S DMA 16 kHz 采集，降采样到 8 kHz 提取 10 个特征。", "约 2 秒特征窗口；手动请求可留存 WAV。"),
        ("B-1", "HardwareSerial(2)，38400 8N1，主动请求和帧校验。", "约 1 秒请求；温度超时标记 stale。"),
        ("告警", "火焰或 MQ 超过报警阈值时红灯和蜂鸣器；预警时黄灯。", "蜂鸣器按 300 ms 节奏切换；实际声效取决于模块类型。"),
        ("控制命令", "串口 JSON 接收 fan、fan_auto、alarm、audio_capture、motion_capture。", "返回 command_ack；控制状态纳入遥测。"),
    ], widths=[1900, 4950, 2510], font_size=8.8)
    add_heading(doc, "5.2 牛身节点", 2)
    add_paragraph(doc, "目录为 硬件代码/牛身节点，默认环境 esp32_collar，适合独立绑在牛身上的节点。它使用 Preferences 保存 barn_id、cow_id、device_id、WiFi 和 MQTT 配置，支持通过串口命令写入参数。当前配置明确使用 I2C D21/D22、ADC D34 读取电池分压、状态灯 D2，并读取 ADXL345、MLX90614 和 MAX30102。")
    add_code_block(doc, "set wifi_ssid TP-LINK_94A5\nset wifi_pass your_password\nset mqtt_host 192.168.1.10\nset cow_id cow_001\nset device_id collar_001")
    add_paragraph(doc, "牛身节点的 cattleId 必须是实际耳标或管理编号，不能使用视觉追踪 ID。正式部署还需要固定传感器方向、记录安装姿态、验证电池续航、增加防水防尘和确认 WiFi/MQTT 断线恢复。")
    add_heading(doc, "5.3 MaixCam 固件", 2)
    optional_picture(doc, "deployment-layout.png", 16.0, "图 5-1 MaixCam 与控制箱现场部署点位建议")
    add_table(doc, ["功能", "代码实现", "生产注意"], [
        ("模型加载", "从 config.json 的 model_path 加载 YOLOv5/YOLOv8；模型缺失时仍可显示摄像头。", "模型必须登记版本、哈希、类别和端侧性能。"),
        ("目标检测", "从检测对象读取 label、score、bbox，绘制框并生成结构化结果。", "现场需要不同光照、遮挡、栏位和夜间样本。"),
        ("状态机", "卧倒持续时间、人员进入、可选步态/蹄部/口鼻异常类和事件冷却。", "正常卧躺不能直接等于跌倒；疾病类只作复核证据。"),
        ("证据留存", "异常截图保存到 snapshot_dir，事件含 edgeEventId、bootId 和模型信息。", "原始图片下载和临床访问必须受权限与审计保护。"),
        ("通信", "UART 通知 ESP32；MQTT 上报；backend_url 非空时 HTTP 上报。", "MaixCam 仅使用 ingest 角色密钥。"),
    ], widths=[1800, 5000, 2560], font_size=8.8)
    add_code_block(doc, "MaixCam -> ESP32: {\"type\":\"vision_event\",\"event\":\"fall_suspect\",\"score\":0.86}\nESP32 -> MaixCam: {\"type\":\"capture_request\",\"reason\":\"nh3_high\",\"durationMs\":3000}")


def section_6(doc):
    add_heading(doc, "6 通信协议、数据流与实时遥测", 1)
    optional_picture(doc, "mqtt-topic-map.png", 16.0, "图 6-1 MQTT Topic 与事件载荷设计")
    add_heading(doc, "6.1 遥测 JSON", 2)
    add_paragraph(doc, "综合演示节点每约 2 秒向串口输出一行 JSON。后端串口服务解析遥测、记录接收时间并通过 WebSocket 推送给前端。遥测同时包含数据值和质量状态，便于页面区分“没有数值”和“数值为 0”。")
    add_code_block(doc, "{\"type\":\"telemetry\",\"deviceId\":\"demo_esp32_01\",\"barnId\":\"barn_01\",\"cattleId\":\"demo_esp32_01\",\"temperature\":27.4,\"humidity\":70.2,\"lightLux\":230,\"mqRaw\":412,\"flame\":false,\"maxStatus\":\"no_finger\",\"behavior\":{\"state\":\"walking\"},\"microphone\":{\"status\":\"ok\"},\"b1Infrared\":{\"status\":\"valid\"}}")
    add_heading(doc, "6.2 三位置临床采集 NDJSON", 2)
    add_paragraph(doc, "三位置原始数据不是普通实时遥测的替代品，而是由临床页面发起、绑定牛只和视频引用的限时会话。固件以 20 Hz 输出 mcs 行，后端归档为 NDJSON 并计算 SHA-256。任何串口背压、传感器失败、连续性不足或临床签核缺失，都会阻止其进入模型发布清单。")
    add_code_block(doc, "{\"type\":\"mcs\",\"s\":\"motion-session-id\",\"d\":\"demo_esp32_01\",\"c\":\"cow_001\",\"b\":\"barn_01\",\"i\":120,\"m\":8450,\"r\":20,\"n\":[0.1,0.2,9.6,1.2,0.3,-0.4],\"u\":[0.0,0.1,9.7],\"l\":[0.2,0.3,9.5,2.1,0.5,-0.2]}")
    add_heading(doc, "6.3 MQTT Topic", 2)
    add_table(doc, ["方向", "Topic", "用途"], [
        ("设备上报", "cattle/{deviceId}/telemetry", "环境与设备运行状态。"),
        ("设备告警", "cattle/{deviceId}/alert", "火焰、MQ、高温高湿等即时事件。"),
        ("视觉上报", "cattle/{cameraId}/vision/event", "MaixCam 结构化事件和截图路径。"),
        ("视觉状态", "cattle/{cameraId}/vision/status", "FPS、模型是否加载、检测数量和连接状态。"),
        ("控制下发", "cattle/{deviceId}/cmd", "风扇、报警等命令；当前代码主要通过后端串口链路。"),
        ("视觉配置", "cattle/{cameraId}/vision/config", "阈值、ROI、模型配置。"),
    ], widths=[1600, 4500, 4260], font_size=8.8)
    add_heading(doc, "6.4 事件去重与质量", 2)
    add_paragraph(doc, "音频事件使用 deviceId、bootId、edgeEventId 组合去重；视觉事件使用 sourceKey/edgeEventId；运动会话使用 sessionId 唯一约束。设备重启会生成新的 bootId，避免重置序号后覆盖旧事件。后端将原始音频和 IMU 文件置于受控目录，下载响应不应进入共享缓存。")


def section_7(doc):
    add_heading(doc, "7 三位置 IMU 行为与跛行筛查", 1)
    optional_picture(doc, "risk-scoring-matrix.png", 16.0, "图 7-1 运动、视觉、环境和临床证据的风险组合矩阵")
    add_heading(doc, "7.1 当前行为模型事实", 2)
    report = load_json(BASE / "牛行为识别数据集" / "esp32_motion_model" / "training_report.json", {})
    metrics = report.get("metrics", {})
    add_paragraph(doc, "项目内置的 public-neck-rf-v1 是从公开 dataset_6.csv 训练的颈部单传感器基线。原始数据只有一个传感器，因此固件只把它用于颈部 MPU；背部 ADXL345 用姿态/活动规则，腿部 MPU 用活动趋势规则，最终通过 neck_ml + body_tilt + leg_activity 合成当前行为显示。")
    add_table(doc, ["指标", "当前值", "解释"], [
        ("模型版本", report.get("model", "public-neck-rf-v1"), "ESP32 头文件中的固定森林版本。"),
        ("类别数", "6", "grazing、lying_ruminating、lying_resting、standing_resting、walking、standing_ruminating。"),
        ("树数量/最大深度", f"{report.get('trees', 30)} / {report.get('max_depth', 10)}", "固定数组导出到 C++，端侧不需要 Python。"),
        ("训练/测试行数", f"{report.get('train_rows', 10476)} / {report.get('test_rows', 2612)}", "按连续标签段进行 80/20 切分。"),
        ("测试 accuracy", f"{metrics.get('accuracy', 0.6838):.4f}", "离线公开数据指标，不是现场三位置准确率。"),
        ("测试 macro-F1", f"{metrics.get('macro_f1', 0.5749):.4f}", "细分类之间表现不均衡，需真实牛只数据改进。"),
    ], widths=[2250, 2250, 4860], header_fill=LIGHT_TEAL)
    add_callout(doc, "不可夸大", "当前不能把 public-neck-rf-v1 宣传成“颈部、背部、腿部三位置训练模型”，也不能仅凭行为结果诊断跛行、蹄病或口蹄疫。", LIGHT_RED)
    add_heading(doc, "7.2 三位置特征", 2)
    add_table(doc, ["位置", "传感器", "当前特征", "生产含义"], [
        ("颈部", "MPU 0x68", "ax/ay/az、gx/gy/gz、窗口活动和公开行为模型。", "采食、反刍、静止和总活动趋势；易受项圈松动影响。"),
        ("背部", "ADXL345 0x53", "三轴加速度、姿态倾角、躺卧/起立变化。", "判断躯干姿态；不能直接推断病因。"),
        ("腿部", "MPU 0x69", "三轴加速度、三轴角速度、活动强度和变化统计。", "跛行候选的主要运动来源；必须结合步态视频和蹄部检查。"),
    ], widths=[1500, 1900, 3300, 2660], font_size=8.8)
    add_heading(doc, "7.3 生产跛行筛查路径", 2)
    optional_picture(doc, "ai-training-pipeline.png", 16.0, "图 7-2 三位置运动数据采集、训练和发布门禁")
    add_items(doc, [
        "在 /clinical 页面创建绑定真实 cattleId、操作人员、栏位和同步侧视/后视视频引用的 motion_capture 会话。",
        "ESP32 以 20 Hz 输出颈部、背部、腿部原始数据；平台校验样本完整度、连续索引、丢样、传感器状态和 SHA-256。",
        "评分员按统一步态评分体系记录 lamenessScore，蹄部检查人记录 hoofFinding，兽医填写临床证据和签核时间。",
        "按动物、牧场/栏舍和时间隔离训练、验证和外部测试，报告灵敏度、特异度、PPV、NPV、拒识率和每头牛每天误报量。",
        "训练器、模型登记工具和服务器登记事务逐条重新读取受保护会话血缘，任一字段变化均拒绝发布。",
        "即使模型获批，端侧候选也要与新鲜 MaixCam 步态/蹄部证据组合后才可形成 lameness_suspect，并要求人工步态和蹄部复核。",
    ])
    add_heading(doc, "7.4 当前模型状态", 2)
    add_table(doc, ["组件", "当前状态", "下一步"], [
        ("cattle_lameness_model.h", "kEnabled=false；版本 untrained-three-position-lameness-v1。", "采集多头牛、多栏位、不同地面和季节的合格会话。"),
        ("采集工具", "已实现 20 Hz、限时会话、质量状态和训练血缘接口。", "在现场完成视频同步、评分和兽医签核。"),
        ("风险融合", "缺少合格运动覆盖时返回 DATA_UNAVAILABLE；模型未批准时不升级跛行风险。", "完成外部验证后才配置批准版本白名单。"),
    ], widths=[2700, 3550, 3110])


def section_8(doc):
    add_heading(doc, "8 INMP441 声音健康风险筛查与论文依据", 1)
    optional_picture(doc, "ai-training-pipeline.png", 16.0, "图 8-1 声音从采集、审核到模型发布的生产链路")
    add_heading(doc, "8.1 端侧处理", 2)
    add_paragraph(doc, "INMP441 由 ESP32 通过 I2S DMA 采集。固件启动时同时观察两个 I2S 数据槽位，选择有信号的一侧，并将状态写入 microphone.channel 和 microphone.status。采样信号会进行直流偏置处理、能量计算、峰值、饱和率、过零率以及低/中/高频能量统计；手动 audio_capture 请求可形成 8 kHz、单声道、两秒 PCM/WAV 证据。")
    add_table(doc, ["状态", "含义", "处置"], [
        ("calibrating", "正在判断 I2S 槽位。", "等待校准完成，不做疾病判断。"),
        ("ok", "采样链路和信号质量基本有效。", "可用于特征采集或人工回放。"),
        ("signal_invalid", "数据线、L/R、时钟、供电或共地可能异常。", "先查线和电源，不得把无效数据送入训练。"),
        ("feature_only", "声音模型未获批准，只有特征或基础声学候选。", "不产生 cough_suspect/wheeze_suspect 疾病风险。"),
        ("unknown/rejected", "置信度或 OOD 距离未通过。", "安全拒识，保留事件供复核。"),
    ], widths=[1900, 4200, 3260], header_fill=LIGHT_TEAL)
    add_heading(doc, "8.2 当前离线基线", 2)
    audio_meta = load_json(BASE / "audio-training-data" / "artifacts" / "kaggle-asc24-v2" / "audio_model_metadata.json", {})
    validation = audio_meta.get("validation", {})
    audio_gate = audio_meta.get("releaseGate", {})
    add_table(doc, ["指标", "当前值", "工程解释"], [
        ("模型版本", audio_meta.get("modelVersion", "cattle-vocalization-baseline-v2"), "公开基础声学模型，不是疾病模型。"),
        ("数据", "322 段有效公开音频，639 个两秒窗口", "仅用于 cow_vocalization 与 non_cattle_audio 基线。"),
        ("验证分组/窗口", f"{audio_meta.get('validationGroups', 57)} / {audio_meta.get('validationSamples', 125)}", "按 group 隔离，避免同源片段跨分区。"),
        ("验证 accuracy", f"{validation.get('accuracy', 0.824):.4f}", "公开数据上的基础声学分类指标。"),
        ("验证 macro-F1", f"{validation.get('macroF1', 0.8179363):.4f}", "不能外推为牛舍临床声音准确率。"),
        ("发布门禁", "未通过", "required clinical label cough_suspect 缺失；生成头文件保持 kEnabled=false。"),
    ], widths=[2250, 2700, 4410], header_fill=LIGHT_TEAL)
    add_paragraph(doc, "当前模型的类别是 cow_vocalization 和 non_cattle_audio，不包含 cough_suspect 或 wheeze_suspect。它能证明数据清洗、特征、分组验证、拒识和头文件导出链路可以运行，但不能支持把公开牛叫声标成 BRD 或肺炎。")
    add_heading(doc, "8.3 论文理论支撑", 2)
    add_table(doc, ["文献", "支持的结论", "项目采用方式"], [
        ("Ferrari et al., 2010, DOI 10.1016/j.prevetmed.2010.06.013", "犊牛咳嗽声与呼吸道疾病临床情形有关，可作为记录和复核事件。", "标签使用 cough_suspect，不把声音直接命名为疾病确诊。"),
        ("Vandermeulen et al., 2016, DOI 10.1016/j.compag.2016.07.014", "连续咳嗽监测有 BRD 早期识别研究基础。", "按窗口计数、冷却重复告警并保留音频片段。"),
        ("Costa et al., 2021, DOI 10.3168/jds.2019-17885", "精准养殖健康监测需要连续记录和管理流程，单一传感器不能成为最终临床结论。", "声音与环境、行为、视觉和临床复核关联。"),
        ("Limede et al., 2025, DOI 10.1093/jas/skaf345", "音频、视觉和行为可以联合用于牛健康状态研究。", "只有多模态证据满足门禁时才升级 BRD 风险。"),
        ("Jobarteh et al., 2025, DOI 10.3389/fvets.2025.1704031", "牛发声分析需要上下文，不能仅凭单段音频判断健康状态。", "网页保留 WAV、标签、置信度、版本和现场说明。"),
        ("Schook et al., 2015, DOI 10.1016/j.compag.2015.08.028", "牛叫声的频谱与时序可用于福利/状态监测研究，但不等同疾病确诊。", "公开牛叫数据只作为基础声学基线。"),
    ], widths=[3200, 3250, 2910], font_size=8.4)
    add_heading(doc, "8.4 生产发布门禁", 2)
    add_items(doc, [
        "每条训练音频必须有平台归档 SHA-256、真实 animalId、recordingSessionId、兽医、临床证据和签核时间。",
        "normal、moo、barn_noise 也必须来自同一受控平台归档，不能把公开或手工替换音频混入临床疾病训练集。",
        "训练和验证按动物分组，外部测试按新动物、新栏舍和新日期隔离；每个风险标签至少 100 条只是最低起点。",
        "风险类 precision 至少 0.80、recall 至少 0.70、macro-F1 至少 0.75，并由临床负责人批准。",
        "端侧置信度和 OOD 距离任一不通过就返回 unknown；BRD 风险还需要温度、行为、视觉或人工检查等独立证据。",
    ])
    add_callout(doc, "当前结论", "声音模块已经具备生产数据链路和论文依据，但尚未具备临床疾病模型的训练条件。当前固件和平台保持 feature_only，蜂鸣器不会因公开牛叫基线自动报警。", LIGHT_YELLOW)


def section_9(doc):
    add_heading(doc, "9 多模态风险融合与疾病边界", 1)
    optional_picture(doc, "risk-scoring-matrix.png", 16.0, "图 9-1 多模态风险分层和独立证据门禁")
    add_heading(doc, "9.1 风险融合方法", 2)
    add_paragraph(doc, "后端 HealthScreeningService 以当前窗口、个体基线、视觉事件、临床检查和运动覆盖质量为输入。系统先检查三位置数据是否足够、基线是否已经学习完成，再根据采食/反刍下降、活动下降、卧躺增加、跛行候选、体表温度趋势、声音候选和视觉事件生成解释性风险。缺少覆盖或基线不足时，系统明确返回 DATA_UNAVAILABLE 或 BASELINE_LEARNING，不用零值伪装成正常。")
    add_table(doc, ["信号", "可提供的证据", "不能单独说明"], [
        ("环境", "温湿度、MQ 趋势、光照、烟雾、风扇状态。", "不能单独诊断 BRD、FMD 或代谢病。"),
        ("声音", "咳嗽/喘鸣候选、SNR、音频回放。", "不能单独确认肺炎病原或 BRD。"),
        ("运动", "活动、姿态、腿部冲击、三位置同步原始数据。", "不能单独确认跛行侧别、蹄病病灶或 FMD。"),
        ("B-1", "目标表面温度趋势和环境温度。", "不能替代接触式核心体温，更不能确诊任何疾病。"),
        ("MaixCam", "牛体、姿态、步态/蹄部/口鼻异常候选和截图。", "不能凭视觉模型宣布疾病阳性/阴性。"),
        ("临床记录", "接触式核心体温、步态评分、蹄部检查、兽医证据。", "平台保存和审计，最终诊断仍按兽医和实验室流程。"),
    ], widths=[1700, 4050, 3610], font_size=8.7)
    add_heading(doc, "9.2 具体疾病路径", 2)
    add_table(doc, ["临床实体", "平台最多输出", "必须的确认", "当前状态"], [
        ("跛行/蹄病", "lameness_suspect", "标准步态评分、蹄部检查、必要时兽医诊断。", "模型未批准；现阶段只采集和规则观察。"),
        ("牛呼吸道疾病 BRD", "brd_suspect、cough_suspect、wheeze_suspect", "临床呼吸评分、听诊/肺部超声、兽医判断和必要检测。", "声音疾病模型未批准。"),
        ("口蹄疫 FMD", "fmd_suspect_triage", "法定报告、兽医检查、官方实验室 PCR/抗原/血清学。", "只提供应急分诊路径，禁止阳性/阴性结论。"),
        ("乳房炎", "当前不输出；未来可考虑 mastitis_attention", "乳房检查、乳汁电导率、SCC、乳样培养/PCR和兽医判断。", "现有硬件缺少乳检输入。"),
        ("采食/代谢异常", "feeding_rumination_attention", "饲喂/反刍记录、临床和血液/乳汁检测。", "只能作为行为关注。"),
    ], widths=[1900, 2350, 3350, 1760], font_size=8.3)
    add_heading(doc, "9.3 FMD 应急分诊", 2)
    add_paragraph(doc, "口蹄疫属于应急动物疫病路径。平台可以把运动/跛行异常、MaixCam 或人工发现的口鼻/蹄部病灶候选、接触式核心体温异常和时间地点信息组织成 fmd_suspect_triage，但不能用声音、活动或 B-1 单独排除 FMD，也不能自动隔离、解除隔离或替代法定报告。")
    add_items(doc, [
        "锁定真实 cattleId、栏位、时间、图片/视频、检查人员和证据编号。",
        "立即创建人工交接，按当地动物防疫法规联系兽医和主管部门。",
        "采样、PCR/抗原/血清学检测以及隔离和解除措施由有资质人员决定。",
        "只有主管/官方引用加显式授权的 closed_by_authority 动作才能关闭平台交接记录；该状态仍不等同实验室阳性或阴性。",
    ])
    add_heading(doc, "9.4 乳房炎边界", 2)
    add_paragraph(doc, "B-1 是非接触体表温度模块，三位置 IMU、INMP441 和普通 MaixCam 也没有乳汁电导率、体细胞数、挤奶量或乳样输入。因此当前代码和界面不生成 mastitis_attention，不把体表温度、声音或行为标签伪装为乳房炎训练数据。未来至少需要按每头牛、每次挤奶、每个乳区同步记录乳检数据和兽医结局，并按牛只、牧场、季节/时间隔离验证。")
    add_callout(doc, "疾病结论", "所有疾病相关输出均为筛查/分诊线索，不是确诊；系统不提供药物、抗菌药或治疗方案。", LIGHT_RED)


def section_10(doc):
    add_heading(doc, "10 后端、数据库与 API", 1)
    optional_picture(doc, "api-map.png", 16.0, "图 10-1 Spring Boot 后端 REST API 功能地图")
    optional_picture(doc, "database-er.png", 16.0, "图 10-2 MySQL/H2 核心实体关系")
    add_heading(doc, "10.1 后端技术栈", 2)
    add_table(doc, ["组件", "项目实际版本/位置", "职责"], [
        ("Spring Boot", "3.3.5", "REST、配置、生命周期和生产 profile。"),
        ("Java", "17", "后端编译和运行基线。"),
        ("JPA", "spring-boot-starter-data-jpa", "实体、仓储和数据库访问。"),
        ("WebSocket", "TelemetryWebSocketConfig/Handler", "把串口遥测和状态实时推送给 Web。"),
        ("jSerialComm", "2.11.0", "后端读取 ESP32 串口并发送命令。"),
        ("H2/MySQL", "演示 H2；生产 MySQL", "本地演示和生产持久化。"),
        ("安全策略", "ApiKeyAccessPolicy 等", "viewer、ingest、operator、clinical、admin 角色隔离。"),
    ], widths=[1800, 3400, 4160], font_size=8.8)
    add_heading(doc, "10.2 主要 API", 2)
    add_table(doc, ["领域", "接口", "作用"], [
        ("总览/环境", "GET /api/dashboard；GET /api/environment/latest；GET /api/environment/trend；POST /api/environment", "驾驶舱、实时环境和趋势写入。"),
        ("设备控制", "GET /api/devices；POST /api/devices/command；GET /api/devices/commands", "设备状态、fan/alarm 命令、命令历史。"),
        ("视觉事件", "POST/GET /api/events/vision", "MaixCam 上报和临床角色读取视觉证据。"),
        ("声音事件", "GET /api/events/audio；PUT /api/events/audio/{id}/review", "音频回放、人工审核和训练血缘。"),
        ("临床检查", "POST/GET /api/clinical-checks", "核心体温、步态和病灶人工检查。"),
        ("运动会话", "POST /api/motion-captures；GET /api/motion-captures/{id}/raw；PUT .../clinical-review", "启动、归档、签核三位置原始数据。"),
        ("FMD 交接", "POST/GET /api/fmd-triage-cases；POST .../{id}/actions", "应急人工分诊和交接审计。"),
        ("模型发布", "GET/POST /api/model-releases；POST .../{id}/revoke", "管理员批准、幂等、撤回和血缘重验。"),
        ("实时通道", "GET /api/telemetry/snapshot；WS /ws/telemetry", "遥测快照和 WebSocket 推送。"),
    ], widths=[1600, 4350, 3410], font_size=8.2)
    add_heading(doc, "10.3 数据库核心表", 2)
    add_table(doc, ["表", "保存内容", "关键约束"], [
        ("environment_reading", "牛舍环境和执行器状态。", "barn_id + recorded_at 索引。"),
        ("vision_event", "视觉事件、source_key、截图和证据。", "source_key 唯一去重。"),
        ("audio_event / metadata / review", "声音事件、特征、WAV 哈希、审核和临床签核。", "事件、来源和审核关联唯一。"),
        ("motion_capture_session / clinical_review", "20 Hz 原始会话、完整度、SHA-256、视频、步态和蹄部签核。", "session_id 唯一；训练血缘只读重验。"),
        ("health_risk / alert_record", "风险、解释、建议、告警和状态。", "风险由服务生成，不提供伪造接口。"),
        ("model_release", "模型版本、数据/模型/固件哈希、血缘和批准/撤回。", "family + version 唯一且不可覆盖。"),
        ("audit_record", "操作人、对象、载荷和 hash 链。", "previous_hash -> entry_hash。"),
    ], widths=[2450, 4200, 2710], font_size=8.6)
    add_heading(doc, "10.4 生产 profile", 2)
    add_paragraph(doc, "生产启动使用 MySQL profile 和 production profile，要求数据库迁移先完成、ddl-auto 使用 validate、H2/演示数据关闭，并配置五个互不相同的角色密钥。MaixCam 只拿 ingest 密钥，临床原件和模型发布只开放给 clinical/admin。互联网部署不应把浏览器共享 API key 当作长期身份系统，应放在 TLS 反向代理或身份代理后。")


def section_11(doc):
    add_heading(doc, "11 Web、鸿蒙 APP 与微信小程序", 1)
    optional_picture(doc, "current-web-intro.png", 16.0, "图 11-1 当前 Web 项目首页截图")
    optional_picture(doc, "current-web-dashboard.png", 16.0, "图 11-2 当前 Web 总览驾驶舱截图")
    optional_picture(doc, "current-web-environment.png", 16.0, "图 11-3 当前 Web 环境监测截图")
    add_heading(doc, "11.1 Web 页面", 2)
    add_table(doc, ["路由", "页面职责", "当前实现"], [
        ("/", "项目介绍与技术路线。", "Vue3 首页和项目视觉资产。"),
        ("/dashboard", "存栏、在线设备、告警、推理 FPS 和 3D 牛舍态势。", "ECharts/Three.js/实时遥测。"),
        ("/environment", "温湿度、氨气、光照、烟雾、风扇和雾化状态。", "趋势图和状态卡片。"),
        ("/health", "健康风险、证据链、风险等级和限制说明。", "后端筛查结果展示。"),
        ("/clinical", "核心体温、步态/蹄部签核、FMD 交接、运动采集。", "临床工作流和 20 Hz 会话入口。"),
        ("/audio", "音频事件、WAV 回放、人工审核和筛查状态。", "下拉菜单已使用深色高对比样式。"),
        ("/behavior", "颈部/背部/腿部运动、行为状态、健康相关数据。", "实时遥测、趋势图和三位置传感器卡片。"),
        ("/devices", "设备状态、风扇和报警控制、命令历史。", "控制命令带状态回执。"),
        ("/models", "模型版本、指标、训练部署和发布状态。", "展示模型卡和生产门禁语义。"),
    ], widths=[1600, 3950, 3810], font_size=8.7)
    add_heading(doc, "11.2 鸿蒙 APP", 2)
    optional_picture(doc, "hm-app-contact-sheet.png", 16.0, "图 11-4 鸿蒙 APP 核心页面总览")
    add_table(doc, ["页面", "用途", "当前状态"], [
        ("总览", "查看牛舍概况、在线状态和风险摘要。", "交互原型，部分数据为本地示例。"),
        ("AI 识牛", "拍照或选择图片进行识别。", "识别流程原型，需替换为真实推理接口。"),
        ("识别记录", "查看历史识别和复核结果。", "本地/示例记录页面已具备。"),
        ("后台管理", "设备、告警、抓拍和模型同步入口。", "交互原型，生产需要权限和后端绑定。"),
        ("设备链路", "查看传感器和通信链路状态。", "页面已具备，真实设备接入待现场联调。"),
    ], widths=[2000, 4600, 2760])
    add_heading(doc, "11.3 微信小程序", 2)
    add_paragraph(doc, "wx/miniprogram 提供移动巡检、照片诊断、记录保存和管理入口。当前重点是验证移动端工作流和页面结构，正式落地需要补充登录、后端 API、文件上传、用户权限、网络失败重试和数据同步策略。")
    add_callout(doc, "前端验证边界", "Vue3 的 npm run build 已通过；此前 npm run smoke 受到旧服务端口和页面服务状态影响，不能把 smoke 记为通过。当前报告只把构建列为已验证，把浏览器全流程列为待服务启动后的专项验收。", LIGHT_YELLOW)


def section_12(doc):
    add_heading(doc, "12 数据治理、权限与审计", 1)
    optional_picture(doc, "data-governance-map.png", 16.0, "图 12-1 数据治理、临床证据和模型血缘")
    add_heading(doc, "12.1 数据分层", 2)
    add_table(doc, ["数据层", "示例", "治理要求"], [
        ("原始数据", "WAV、IMU NDJSON、图片、传感器原始值。", "受控目录、SHA-256、访问权限、备份和 no-store。"),
        ("特征数据", "RMS、频带能量、活动均值、倾角、SNR。", "记录采样率、窗口、版本和质量状态。"),
        ("事件数据", "audio_event、vision_event、motion_capture。", "唯一源键、设备/牛只/栏位/时间和证据关联。"),
        ("临床数据", "核心体温、步态评分、蹄部检查、兽医证据。", "clinical/admin 权限，临床签核不可由模型预填。"),
        ("模型数据", "清单哈希、模型卡、固件哈希、外部测试摘要。", "版本不可覆盖，审批和撤回独立审计。"),
    ], widths=[1900, 3650, 3810], font_size=8.8)
    add_heading(doc, "12.2 角色权限", 2)
    add_table(doc, ["角色", "允许", "禁止/限制"], [
        ("viewer", "总览、环境、健康风险、设备状态、WebSocket。", "不能读取原始音频/视觉/IMU，不能控制设备。"),
        ("ingest", "MaixCam POST /api/events/vision。", "不能临床复核、控制设备或发布模型。"),
        ("operator", "viewer 权限加风扇/报警命令。", "不能读取临床原件和模型发布。"),
        ("clinical", "临床检查、原始音频/IMU、复核、FMD 交接。", "不能绕过模型审批和管理员策略。"),
        ("admin", "所有权限、模型批准/撤回、审计。", "仍不得把平台筛查结果当作诊断。"),
    ], widths=[1700, 4200, 3460], font_size=8.7)
    add_heading(doc, "12.3 审计与回滚", 2)
    add_items(doc, [
        "每次模型发布记录训练清单哈希、模型版本、模型卡哈希、固件哈希、验证摘要、审批人、证据编号和源血缘指纹。",
        "服务器在模型登记事务中再次读取每条音频或 IMU 归档，重新计算哈希并核对临床签核，不信任客户端单独提交的摘要。",
        "同一 modelFamily + modelVersion 只能完全相同幂等重试；证据、哈希或血缘变化必须使用新版本。",
        "发生数据污染、传感器漂移或误报异常时，撤回版本并清空批准白名单，回到 feature_only 或上一批准版本。",
        "audit_record 通过 previous_hash 和 entry_hash 形成链式篡改发现能力，但不能替代数据库备份、最小权限和恢复演练。",
    ])


def section_13(doc):
    add_heading(doc, "13 测试验证与当前完成度", 1)
    optional_picture(doc, "testing-acceptance-matrix.png", 16.0, "图 13-1 自动化测试、硬件编译和现场验收矩阵")
    add_heading(doc, "13.1 本次已执行并通过", 2)
    add_table(doc, ["验证项", "命令/范围", "结果"], [
        ("普通 ESP32 综合演示节点", "PlatformIO demo_esp32 编译。", "通过；RAM 45,596 / 327,680，Flash 509,573 / 1,310,720。"),
        ("牛身节点", "PlatformIO esp32_collar 编译。", "通过；RAM 45,796 / 327,680，Flash 802,897 / 1,310,720。"),
        ("ESP32-S3 主环境", "PlatformIO esp32s3 编译。", "通过；已有构建产物和成功记录。"),
        ("后端", "smart-cattle-backend Maven test。", "通过；32 tests，Failures 0，Errors 0，Skipped 0。"),
        ("前端", "smart-cattle-frontend npm run build。", "通过；2215 modules transformed，Vite build 完成。"),
        ("Word 文件", "生成后执行 OOXML/XSD 结构、ZIP 完整性和 python-docx 打开检查。", "通过；All validations PASSED，ZIP 无坏项，python-docx 正常打开。"),
        ("PDF 页面转换", "尝试使用 LibreOffice/soffice 转换并抽查页面。", "未执行；当前环境未提供 LibreOffice，不能把 PDF 视觉转换写成已通过。"),
    ], widths=[2500, 3700, 3160], header_fill=LIGHT_TEAL, font_size=8.8)
    add_heading(doc, "13.2 尚不能由自动化替代的验收", 2)
    add_table(doc, ["项目", "当前判断", "必须补做"], [
        ("COM 串口实机", "代码支持串口采集和命令，但本报告不把编译当作传感器实测。", "确认实际 COM 端口，查看 I2C scan、三 IMU、B-1、INMP441、MAX30102 的真实日志。"),
        ("三位置绑缚", "固件有 20 Hz 会话和质量门禁。", "绑在颈、背、腿并固定方向，验证线长、供电、背压和同步视频。"),
        ("声音", "公开基线可运行，疾病模型未启用。", "现场采集并由兽医签核 cough/wheeze、normal、moo、barn_noise。"),
        ("MaixCam", "程序具备模型缺失时的安全启动。", "放入实际 .mud 模型，实测 FPS、温升、截图、UART/MQTT/HTTP。"),
        ("网络/MQTT", "协议和配置已写入项目。", "断网、重连、补传、身份认证和 broker 持续运行测试。"),
        ("长时间可靠性", "尚未形成现场 72 小时/7 天证据。", "实验室 72 小时、牛舍 7 天连续运行，记录复位和数据缺口。"),
        ("临床效能", "没有可发布的外部临床验证指标。", "按牛只/牧场/时间隔离，完成兽医、实验室和现场评估。"),
    ], widths=[2050, 3800, 3510], font_size=8.6)
    add_heading(doc, "13.3 测试数据记录模板", 2)
    add_table(doc, ["记录对象", "至少保存", "用途"], [
        ("环境", "原始值、滤波值、阈值、设备、时间、供电和传感器状态。", "分析漂移、异常趋势和控制策略。"),
        ("运动", "原始 NDJSON、采样索引、20 Hz、完整度、视频、安装方向、评分和签核。", "训练跛行筛查和定位采集质量问题。"),
        ("音频", "WAV、SHA-256、采样率、SNR、I2S 槽位、背景噪声、审核和临床证据。", "训练声音模型和复核误报。"),
        ("视觉", "图片、bbox、score、模型版本、ROI、FPS、真实 cattleId 关联。", "评估视觉模型和事件证据。"),
        ("处置", "告警、控制命令、执行回执、检查结论、处理人和时间。", "形成业务和安全审计闭环。"),
    ], widths=[1750, 4820, 2790], font_size=8.6)
    add_callout(doc, "完成度总评", "项目已经达到“可编译、可演示、可继续联调、数据和发布治理路径完整”的阶段；尚未达到“临床疾病模型生产上线”和“现场连续运行验收”阶段。", LIGHT_YELLOW)


def section_14(doc):
    add_heading(doc, "14 生产部署、运维与验收", 1)
    optional_picture(doc, "deployment-layout.png", 16.0, "图 14-1 牛舍现场部署布局建议")
    add_heading(doc, "14.1 部署步骤", 2)
    add_table(doc, ["阶段", "工作内容", "验收输出"], [
        ("现场勘测", "确认牛舍面积、栏位、通风、光照、网络、电源和巡检路线。", "点位图、供电图、网络图、设备 ID 清单。"),
        ("控制箱安装", "安装 ESP32、传感器端子、保险丝、DC-DC、继电器/MOSFET、手动急停。", "端子标签、接线记录、空载上电记录。"),
        ("牛身节点", "完成耳标配置、传感器方向固定、项圈/背部/腿部防护。", "安装照片、设备 ID、方向和电池记录。"),
        ("MaixCam", "安装支架、补光、防护窗，放置已登记模型。", "覆盖区域、FPS、截图和模型哈希。"),
        ("平台部署", "执行 MySQL 迁移，配置 production profile、TLS、角色密钥和持久化目录。", "服务启动日志、备份恢复记录、权限检查。"),
        ("联调试运行", "验证传感器、串口、MQTT/HTTP、WebSocket、控制回执和断网恢复。", "联调清单、故障单、7 天运行报告。"),
    ], widths=[1700, 4850, 2810], font_size=8.6)
    add_heading(doc, "14.2 运维要求", 2)
    add_table(doc, ["运维项", "建议频率", "检查内容"], [
        ("传感器和供电", "每周/每月", "端子、DC-DC 温升、3.3V/5V 电压、MQ 基线、B-1 同位置比对。"),
        ("镜头与麦克风", "每周或污染后", "清洁、防水、防风、安装方向和风扇噪声。"),
        ("网络和服务", "每日自动、每周人工", "心跳、重连、磁盘、归档目录、数据库备份和恢复抽检。"),
        ("模型回归", "每次发布前", "固定样本、拒识、误报、FPS、内存、温升和回滚。"),
        ("审计链", "每月", "导出 audit_record、校验 hash 链、核对模型白名单。"),
    ], widths=[2050, 1900, 5410], font_size=8.7)
    add_heading(doc, "14.3 现场验收门槛", 2)
    add_items(doc, [
        "所有电源和执行器在断电状态完成复核；负载启动不造成 ESP32 复位。",
        "I2C 扫描至少发现实际安装的 0x23/0x3C/0x44/0x53/0x57/0x68/0x69 中应有的地址。",
        "B-1 连续收到合法帧，rawHex、validFrames、invalidFrames 和温度状态可解释；无合法帧时页面必须显示等待/错误。",
        "INMP441 为 status=ok 且 rawMin/rawMax 有有效动态范围；signal_invalid 时不得训练。",
        "三位置 IMU 会话达到 accepted、完整度至少 95%、无传感器失败、原始哈希稳定并具备同步视频。",
        "Web、APP、小程序的风险和设备状态与后端一致；控制动作有 ack、命令历史和权限。",
        "疾病模型在临床数据、外部测试、审批和登记完成前保持 kEnabled=false。",
    ])
    add_heading(doc, "14.4 运行命令", 2)
    add_code_block(doc, "cd D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\npy -3.11 -m platformio run\npy -3.11 -m platformio device list\npy -3.11 -m platformio run -t upload --upload-port COM19\npy -3.11 -m platformio device monitor -p COM19 -b 115200\n\ncd D:\\table\\shumuzengxiao\\smart-cattle-backend\nmvn test\n\ncd D:\\table\\shumuzengxiao\\smart-cattle-frontend\nnpm run build")


def section_15(doc):
    add_heading(doc, "15 创新点与应用价值", 1)
    add_table(doc, ["创新点", "技术体现", "应用价值"], [
        ("端边云服一体化", "ESP32 本地采集/控制，MaixCam 本地视觉，后端融合，多端复核。", "降低带宽和设备门槛，形成可演示的完整闭环。"),
        ("三位置个体行为采集", "颈部、背部、腿部统一 20 Hz 临床会话，绑定视频和兽医签核。", "为从行为观察走向跛行筛查提供可审计数据基础。"),
        ("声音证据链", "I2S 槽位校准、信号质量、WAV、SHA-256、人工审核和临床发布门禁。", "避免把普通牛叫误判成疾病，支持后续本地样本训练。"),
        ("疾病边界内置", "BRD、跛行和 FMD 使用 suspect/triage 标签，乳房炎无输入则不输出。", "减少过度承诺，符合兽医和监管流程。"),
        ("模型发布可审计", "训练、登记、服务器事务三次重验源档案血缘，版本不可覆盖可撤回。", "支持生产环境的可追责、回滚和复盘。"),
        ("低成本渐进式部署", "原型版使用常见 ESP32 与模块，正式版预留工业 NH3、4G、IP65 和电源升级。", "适合先台架、再试点、后产品化。"),
    ], widths=[2250, 4400, 2710], font_size=8.6)
    add_heading(doc, "15.1 对养殖管理的直接价值", 2)
    add_items(doc, [
        "把环境异常从人工巡检变成持续记录和本地联动。",
        "把声音、运动和视觉从零散感受变成有时间、设备和证据引用的事件。",
        "把“先看哪头牛”转化为可解释的风险队列，减少无效巡栏。",
        "把临床复核结果回流为训练数据，形成可持续改进而不是一次性演示。",
        "把设备控制、模型版本和告警处置纳入审计，便于项目交接和规模化维护。",
    ])


def section_16(doc):
    add_heading(doc, "16 路线图与风险", 1)
    add_heading(doc, "16.1 分阶段路线与未来展望", 2)
    add_table(doc, ["阶段", "主要工作", "完成标志"], [
        ("阶段 1：台架闭环", "传感器接线、供电、I2C/UART/I2S 扫描，ESP32 编译和串口数据。", "每个模块状态可解释，蜂鸣器/LED/风扇动作可复现。"),
        ("阶段 2：平台联调", "COM 串口、后端 WebSocket、环境/设备/事件 API、页面实时展示。", "真实遥测进入 Web，命令有 ack 和历史。"),
        ("阶段 3：视觉试点", "MaixCam 放入本地 YOLO，采集现场光照/遮挡/夜间数据。", "事件、截图、模型版本和真实牛只身份可追溯。"),
        ("阶段 4：临床采集", "音频和三位置 IMU 采集，兽医审核，视频同步，数据治理。", "形成合格 training lineage 和外部测试集。"),
        ("阶段 5：受控发布", "通过指标门禁、模型登记、灰度、回滚和现场误报监控。", "批准版本写入白名单，仍只输出筛查结果。"),
        ("阶段 6：产品化", "IP65 外壳、工业气体传感器、4G、OTA、批量设备和告警通知。", "现场 7 天/更长运行，运维成本和用户流程可接受。"),
    ], widths=[1900, 4550, 2910], font_size=8.6)
    add_heading(doc, "16.2 主要风险与缓解", 2)
    add_table(doc, ["风险", "表现", "缓解"], [
        ("3.3V 供电不稳", "WiFi 峰值或风扇启动造成复位、传感器丢失。", "独立 DC-DC、分区供电、滤波、电源余量、示波/万用表记录。"),
        ("MQ 漂移", "原始 ADC 与湿度/预热相关，不能代表准确 ppm。", "只做趋势；正式版换工业 NH3/RS485 并标定。"),
        ("I2C 线过长", "三位置绑缚后总线波形和抗干扰变差。", "缩短线缆、降低速率、固定方向，必要时拆分本地节点或使用差分延长。"),
        ("MAX30102 无有效数据", "牛身毛发、接触和运动导致 no_finger 或估计值。", "固定接触结构、去除估计值用于临床结论，完成标准设备比对。"),
        ("声音误报", "风扇、人员、普通牛叫和混响。", "VAD/SNR、背景建模、临床标签、多模态独立证据和 OOD 拒识。"),
        ("行为误报跛行", "正常卧躺、绑缚松动、地面和方向改变。", "同步视频、标准步态评分、蹄检、按动物隔离验证。"),
        ("视觉误报", "遮挡、逆光、夜间、镜头污渍。", "补光、ROI、现场样本、镜头维护、事件冷却。"),
        ("监管风险", "把 FMD 或 BRD 自动写成确诊。", "使用 triage/suspect 标签，设置兽医和官方确认流程。"),
    ], widths=[1900, 3600, 3860], font_size=8.5)
    add_heading(doc, "16.3 下一轮最优先事项", 2)
    add_items(doc, [
        "在实际 COM 端口上完成一次带 I2C scan、B-1 合法帧、INMP441 动态范围和三 IMU 同时在线的日志归档。",
        "解决并记录 3.3V 供电、执行器隔离和牛身线束固定，完成空载/带载复位测试。",
        "启动真实牛只和真实栏舍的声音临床采集与三位置 IMU 会话采集，不用公开数据替代临床标签。",
        "在 MaixCam 上部署已确认格式的 YOLO 模型，完成本地 FPS、温升、截图和目标身份关联。",
        "启动独立动物、栏舍和时间外部测试后，再评估是否有条件批准任何疾病筛查模型。",
    ])
    add_heading(doc, "16.4 未来展望", 2)
    add_paragraph(doc, "未来建设应围绕“更可靠的现场数据、更低的部署成本和更可解释的健康筛查”推进。以下方向是基于当前代码和资料的产品化规划，不代表已经在本项目中完成或通过临床验证。")
    add_table(doc, ["方向", "规划内容", "预期收益", "前置条件"], [
        ("疾病专病模型", "先聚焦跛行/蹄部病变和 BRD 呼吸道风险，按真实耳标、牧场和时间隔离采集并做外部测试。", "从通用异常排序逐步走向可解释的专病筛查。", "兽医签核、足量阳性/阴性样本、独立动物外部测试。"),
        ("工业化硬件", "将 MQ 趋势模块升级为经标定的工业 NH3/环境传感器，完善 IP65、防水连接、独立电源和 4G/以太网。", "提升长期稳定性、可维护性和不同牛舍的迁移能力。", "现场电磁/温湿度测试、功耗预算、批量 BOM 和安全认证。"),
        ("边缘模型与运维", "引入量化模型、模型签名、OTA 灰度、设备证书、远程日志和自动回滚。", "降低带宽与维护成本，缩短故障恢复时间。", "设备身份体系、版本仓库、回滚演练和现场网络覆盖。"),
        ("多模态数字基线", "为每头牛建立活动、采食/反刍、声音和环境的个体基线，结合时间序列变化而非单点阈值。", "减少个体差异造成的误报，提升异常解释能力。", "连续数据质量、牛只身份稳定关联和跨季节数据。"),
        ("规模化业务闭环", "接入兽医工单、隔离区、免疫/用药记录、保险或追溯系统，并保留权限和审计边界。", "让筛查结果进入真实管理流程而不是停留在看板。", "业务方确认流程、数据授权、隐私和监管评估。"),
    ], widths=[1800, 3900, 1900, 1760], font_size=8.1, header_fill=LIGHT_TEAL)


def section_17(doc):
    add_heading(doc, "17 项目文件索引", 1)
    inventory, inventory_count, inventory_bytes = project_inventory()
    add_heading(doc, "17.1 扫描范围与资产统计", 2)
    add_paragraph(doc, f"本报告以 D:/table/shumuzengxiao 为根目录扫描生成。当前纳入统计的文件为 {inventory_count} 个，合计约 {inventory_bytes / (1024 * 1024):.2f} MB；目录名、文件数和大小来自本次生成时的实际文件系统状态。为避免把依赖和重复渲染物料误当作项目源资产，统计排除 .git、.pio、node_modules、target、dist、build、__pycache__、.playwright-cli、.run、output、outputs、report_rendered、report_pdf_pages 等缓存/构建目录；这些排除项不影响源代码、数据集、论文资料、数据库脚本、报告资产和文档的覆盖。")
    add_table(doc, ["顶层目录", "纳入文件数", "纳入大小"], inventory, widths=[5100, 1800, 2460], header_fill=LIGHT_TEAL, font_size=8.0)
    coverage = [
        ("硬件与固件", "硬件代码", "普通 ESP32、牛身节点、MaixCam、配置、训练工具和硬件说明。"),
        ("平台后端", "smart-cattle-backend", "Spring Boot 控制器、服务、实体、数据库迁移和后端测试。"),
        ("Web 前端", "smart-cattle-frontend", "Vue3 页面、实时遥测、图表、API 客户端和前端脚本。"),
        ("鸿蒙应用", "hm", "HarmonyOS/ArkTS 移动巡检工程和页面资源。"),
        ("微信小程序", "wx", "移动巡检小程序、类型定义和页面资源。"),
        ("行为数据与模型", "牛行为识别数据集", "公开行为数据、数据说明、训练脚本、导出头文件和训练报告。"),
        ("疾病生产落地", "疾病识别生产落地", "疾病路径、证据字典、临床采集、论文资料、发布和审计规范。"),
        ("声音/运动归档", "audio-training-data; audio-clips; motion-captures", "声音训练资产、音频片段和三位置 IMU 会话归档。"),
        ("数据库与报告", "database; report_assets; 文档; scripts", "初始化/迁移脚本、图表截图、文档生成和既有报告。"),
        ("B-1 官方资料", "【安服优】B-1 人体红外测温模组_V2.1", "规格书、通信协议和主机测试资料。"),
    ]
    coverage_rows = []
    for name, rel_path, purpose in coverage:
        count = 0
        total_bytes = 0
        for one_path in (part.strip() for part in rel_path.split(";")):
            one_count, one_bytes = scan_path_stats(BASE / one_path)
            count += one_count
            total_bytes += one_bytes
        coverage_rows.append((name, rel_path, count, f"{total_bytes / (1024 * 1024):.2f} MB", purpose))
    add_table(doc, ["覆盖域", "实际路径", "文件数", "大小", "内容"], coverage_rows, widths=[1550, 2850, 950, 1050, 2960], header_fill=LIGHT_GREEN, font_size=7.6)
    add_heading(doc, "17.2 关键路径索引", 2)
    add_table(doc, ["模块", "文件/目录", "说明"], [
        ("项目入口", "README.md; API.md; start-all.bat; start-backend.bat; start-frontend.bat", "启动、接口和生产边界说明。"),
        ("后端控制器", "smart-cattle-backend/src/main/java/.../controller", "dashboard、environment、devices、events、clinical、motion、FMD、models、audit。"),
        ("后端服务", "smart-cattle-backend/src/main/java/.../service", "遥测、音频、视觉、临床、健康风险、模型发布、审计。"),
        ("后端测试", "smart-cattle-backend/src/test/java", "ApiKey、Audio、FMD、Health、ModelRelease、Motion、Telemetry。"),
        ("Web", "smart-cattle-frontend/src/views; components; stores; api", "Vue 页面、趋势图、遥测 Pinia store 和 API client。"),
        ("现场综合节点", "硬件代码/现有硬件演示节点/src/main.cpp", "环境、三位置 IMU、声音、B-1、MAX30102、显示和控制。"),
        ("综合节点配置", "硬件代码/现有硬件演示节点/include/config.h", "引脚、I2C 地址、阈值、采样周期和模型开关。"),
        ("行为模型", "硬件代码/现有硬件演示节点/include/cattle_behavior_model.h", "public-neck-rf-v1 固定森林头文件。"),
        ("声音/跛行模型", "硬件代码/现有硬件演示节点/include/cattle_audio_model.h; cattle_lameness_model.h", "当前均为 kEnabled=false 安全占位。"),
        ("牛身节点", "硬件代码/牛身节点/src/main.cpp; include/config.h", "ADXL345、MLX90614、MAX30102、WiFi/MQTT、电池。"),
        ("MaixCam", "硬件代码/MaixCam节点/main.py; config.json", "YOLO、截图、状态机、UART、MQTT/HTTP。"),
        ("疾病路径", "疾病识别生产落地/疾病路径与生产发布规范.md", "BRD、跛行、FMD、乳房炎边界和发布门禁。"),
        ("证据字典", "疾病识别生产落地/疾病实体与证据字典.md", "疾病实体、平台标签、确认方式和禁止输出。"),
        ("部署审计", "疾病识别生产落地/生产部署与审计清单.md", "上线、运行、模型审批、回滚和访问角色。"),
        ("临床采集", "疾病识别生产落地/数据采集", "音频、IMU、FMD 字段和示例清单。"),
        ("论文索引", "疾病识别生产落地/论文资料/论文索引.json", "DOI、PMCID、许可证、本地文件和 SHA-256。"),
        ("行为训练", "牛行为识别数据集/esp32_motion_model", "训练脚本、README、training_report.json。"),
        ("声音训练", "硬件代码/现有硬件演示节点/tools; audio-training-data/artifacts", "音频清洗、训练、模型卡和发布门禁测试。"),
        ("数据库", "database/init.sql; database/migrate_existing_mysql.sql", "MySQL 初始化和幂等迁移。"),
        ("移动端", "hm/entry/src/main/ets; wx/miniprogram", "鸿蒙应用和微信小程序工程。"),
        ("报告资产", "report_assets", "架构、硬件、数据流、测试、部署和页面截图。"),
        ("报告脚本", "scripts/build_full_project_document.py", "本说明书生成脚本。"),
    ], widths=[1800, 4750, 2810], font_size=8.0)
    add_heading(doc, "17.3 关键文件校验摘要", 2)
    key_files = [
        BASE / "scripts" / "build_full_project_document.py",
        BASE / "硬件代码" / "现有硬件演示节点" / "include" / "config.h",
        BASE / "硬件代码" / "现有硬件演示节点" / "src" / "main.cpp",
        BASE / "硬件代码" / "牛身节点" / "src" / "main.cpp",
        BASE / "硬件代码" / "MaixCam节点" / "main.py",
        BASE / "疾病识别生产落地" / "论文资料" / "论文索引.json",
    ]
    rows = []
    for path in key_files:
        rows.append((str(path.relative_to(BASE)), path.stat().st_size if path.exists() else "missing", sha256(path) if path.exists() else "missing"))
    add_table(doc, ["文件", "字节数", "SHA-256"], rows, widths=[4500, 1300, 3560], header_fill=LIGHT_TEAL, font_size=7.5)
    add_callout(doc, "索引说明", "动态索引用于工程交接和复核，不代表将构建缓存、依赖包或所有二进制论文附件复制进本文。原始论文和模型文件仍以项目目录中的本地文件及论文索引为准。", LIGHT_GRAY)


def appendix(doc):
    add_heading(doc, "附录 A 接线速查表", 1)
    add_table(doc, ["模块", "供电", "信号", "地址/配置", "当前代码"], [
        ("MPU 颈部", "3V3/GND", "SDA D21; SCL D22", "0x68; AD0 GND", "MPU0_I2C_ADDR"),
        ("ADXL 背部", "3V3/GND", "SDA D21; SCL D22", "0x53; SDO GND", "ADXL345_I2C_ADDR"),
        ("MPU 腿部", "3V3/GND", "SDA D21; SCL D22", "0x69; AD0 3V3", "MPU1_I2C_ADDR"),
        ("GY-302", "3V3/GND", "SDA D21; SCL D22", "0x23/0x5C", "BH1750 自动兼容"),
        ("SHT31", "3V3/GND", "SDA D21; SCL D22", "0x44", "优先环境源"),
        ("MAX30102", "3V3/GND", "SDA D21; SCL D22", "0x57", "心率/血氧质量需实测"),
        ("INMP441", "VDD 3V3; GND", "SCK D5; WS D16; SD D17", "L/R GND", "I2S 槽位自动校准"),
        ("B-1", "VDD 3V3; GND", "TX -> D23; RX -> D19", "38400 8N1", "UART2"),
        ("火焰/MQ", "按模块规格", "DO D32; AO D34", "MQ AO 需分压", "火焰低有效"),
        ("LED/蜂鸣器", "按模块", "LED D25/D26/D27; buzzer D33", "红灯报警", "无源蜂鸣器 PWM"),
    ], widths=[1700, 1900, 3300, 2100, 2360], font_size=7.7)
    add_heading(doc, "附录 B 接口和模型命令速查", 1)
    add_code_block(doc, "# 后端\ncd D:\\table\\shumuzengxiao\\smart-cattle-backend\nmvn test\nmvn spring-boot:run\n\n# 前端\ncd D:\\table\\shumuzengxiao\\smart-cattle-frontend\nnpm run build\nnpm run dev\n\n# 现场 ESP32\ncd D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\npy -3.11 -m platformio run\npy -3.11 -m platformio device list\npy -3.11 -m platformio run -t upload --upload-port COM19\n\n# 生产模型：必须先完成平台临床签核和血缘验证\npython tools\\verify_clinical_audio_manifest.py ...\npython tools\\train_audio_model.py --release --clinical-api ...\npython tools\\verify_lameness_manifest.py ...\npython tools\\train_lameness_model.py --release --clinical-api ...")
    add_heading(doc, "附录 C 论文与本地资料索引", 1)
    index = load_json(BASE / "疾病识别生产落地" / "论文资料" / "论文索引.json", {})
    items = index.get("items", [])
    rows = []
    for item in items:
        rows.append((
            item.get("diseasePath", ""),
            f"{item.get('authors', '')}; {item.get('year', '')}",
            item.get("title", ""),
            item.get("doi", ""),
            item.get("localFile", ""),
        ))
    add_table(doc, ["路径", "作者/年份", "题名", "DOI", "本地文件"], rows, widths=[1600, 1900, 3100, 1700, 1060], font_size=6.9, header_fill=LIGHT_TEAL)
    add_paragraph(doc, "论文索引中的本地 SHA-256、PMCID、许可证和工程用途以 疾病识别生产落地/论文资料/论文索引.json 为准。论文支持的是筛查理论、数据治理和验证方法，不构成对本项目设备或任何牛只的诊断授权。")
    add_heading(doc, "附录 D 结论清单", 1)
    add_items(doc, [
        "硬件接线以当前 config.h 和现有硬件 README 为准；B-1 当前为 TX->D23、RX->D19、VDD->3V3、GND->GND。",
        "三位置运动传感器共用 D21/D22 I2C，但两个 MPU 必须使用 0x68/0x69 两个不同地址。",
        "普通牛叫基线不等于声音疾病模型；声音疾病模型和三位置跛行模型当前均未启用。",
        "行为模型当前是颈部公开数据基线，背部和腿部是规则融合，不能宣称三位置已训练。",
        "B-1 是体表温度趋势，不能替代接触式核心体温。",
        "BRD、跛行和 FMD 均采用 suspect/triage 筛查边界；FMD 必须走兽医、主管部门和实验室流程。",
        "后端 32 项测试、两套 ESP32 固件和前端生产构建已经通过；串口实机、网络、现场临床效能仍需单独验收。",
    ])


def build():
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    doc = Document()
    configure_document(doc)
    add_cover(doc)
    add_document_note(doc)
    section_1(doc)
    section_2(doc)
    section_3(doc)
    section_4(doc)
    section_5(doc)
    section_6(doc)
    section_7(doc)
    section_8(doc)
    section_9(doc)
    section_10(doc)
    section_11(doc)
    section_12(doc)
    section_13(doc)
    section_14(doc)
    section_15(doc)
    section_16(doc)
    section_17(doc)
    appendix(doc)
    doc.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    build()
