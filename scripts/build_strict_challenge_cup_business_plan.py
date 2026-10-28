from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


ROOT = Path(r"D:\table\shumuzengxiao")
OUT = ROOT / "outputs"
WORK = OUT / "strict_template_work"
TEMPLATE = WORK / "challenge_template_strict_converted.docx"
POSTERS = OUT / "imagegen"

FINAL_ASCII = OUT / "muyunzhishe_challenge_cup_business_plan_strict_template.docx"
FINAL_CN = OUT / "牧云智舍-挑战杯商业计划书-严格模板版.docx"

FONT_EA = "宋体"
FONT_HEAD = "黑体"
FONT_LATIN = "Times New Roman"

BLUE = "1F4E79"
DARK_BLUE = "17365D"
LIGHT_BLUE = "EAF3F8"
LIGHT_GRAY = "F7F9FB"
MID_GRAY = "D9E2F3"
INK = "111111"
MUTED = "666666"
WHITE = "FFFFFF"
TABLE_WIDTH = 9360


def set_run_font(run, size: float | None = None, bold: bool | None = None, color: str | None = None,
                 ea: str = FONT_EA, latin: str = FONT_LATIN) -> None:
    run.font.name = latin
    if run._element.rPr is None:
        run._element.get_or_add_rPr()
    run._element.rPr.rFonts.set(qn("w:eastAsia"), ea)
    run._element.rPr.rFonts.set(qn("w:ascii"), latin)
    run._element.rPr.rFonts.set(qn("w:hAnsi"), latin)
    if size is not None:
        run.font.size = Pt(size)
    if bold is not None:
        run.bold = bold
    if color is not None:
        run.font.color.rgb = RGBColor.from_string(color)


def clear_body(doc: Document) -> None:
    body = doc._body._element
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)


def setup_styles(doc: Document) -> None:
    styles = doc.styles
    normal = styles["Normal"]
    normal.font.name = FONT_LATIN
    normal._element.rPr.rFonts.set(qn("w:eastAsia"), FONT_EA)
    normal._element.rPr.rFonts.set(qn("w:ascii"), FONT_LATIN)
    normal._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_LATIN)
    normal.font.size = Pt(11)
    normal.paragraph_format.line_spacing = 1.25
    normal.paragraph_format.space_after = Pt(6)

    style_tokens = {
        "Heading 1": (16, DARK_BLUE, 18, 10, FONT_HEAD),
        "Heading 2": (13, BLUE, 12, 6, FONT_HEAD),
        "Heading 3": (12, "2F5597", 8, 4, FONT_HEAD),
    }
    for name, (size, color, before, after, ea_font) in style_tokens.items():
        style = styles[name]
        style.font.name = FONT_LATIN
        style._element.rPr.rFonts.set(qn("w:eastAsia"), ea_font)
        style._element.rPr.rFonts.set(qn("w:ascii"), FONT_LATIN)
        style._element.rPr.rFonts.set(qn("w:hAnsi"), FONT_LATIN)
        style.font.size = Pt(size)
        style.font.bold = True
        style.font.color.rgb = RGBColor.from_string(color)
        style.paragraph_format.space_before = Pt(before)
        style.paragraph_format.space_after = Pt(after)
        style.paragraph_format.line_spacing = 1.25


def section_setup(doc: Document) -> None:
    for section in doc.sections:
        section.start_type = WD_SECTION_START.NEW_PAGE
        section.top_margin = Inches(0.72)
        section.bottom_margin = Inches(0.72)
        section.left_margin = Inches(0.9)
        section.right_margin = Inches(0.9)
        section.header_distance = Inches(0.42)
        section.footer_distance = Inches(0.42)

    section = doc.sections[0]
    section.header.is_linked_to_previous = False
    section.footer.is_linked_to_previous = False
    hp = section.header.paragraphs[0]
    hp.text = ""
    hp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    r = hp.add_run("牧云智舍｜挑战杯商业计划书")
    set_run_font(r, size=9, color=MUTED)

    fp = section.footer.paragraphs[0]
    fp.text = ""
    fp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r = fp.add_run("牧云智舍：多模态智能牛舍监测与闭环预警平台")
    set_run_font(r, size=9, color=MUTED)


def add_para(doc: Document, text: str = "", *, size: float = 11, bold: bool = False,
             color: str = INK, align=None, before: float = 0, after: float = 6,
             first_line: bool = True, style: str | None = None) -> None:
    p = doc.add_paragraph(style=style)
    p.paragraph_format.space_before = Pt(before)
    p.paragraph_format.space_after = Pt(after)
    p.paragraph_format.line_spacing = 1.25
    if first_line:
        p.paragraph_format.first_line_indent = Pt(22)
    if align is not None:
        p.alignment = align
    if text:
        r = p.add_run(text)
        set_run_font(r, size=size, bold=bold, color=color)


def add_heading(doc: Document, text: str, level: int = 1) -> None:
    p = doc.add_heading(text, level=level)
    for r in p.runs:
        set_run_font(
            r,
            size=16 if level == 1 else 13 if level == 2 else 12,
            bold=True,
            color=DARK_BLUE if level == 1 else BLUE if level == 2 else "2F5597",
            ea=FONT_HEAD,
        )


def set_cell_shading(cell, fill: str) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    shd = tc_pr.find(qn("w:shd"))
    if shd is None:
        shd = OxmlElement("w:shd")
        tc_pr.append(shd)
    shd.set(qn("w:fill"), fill)


def set_cell_width(cell, width: int) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_w = tc_pr.find(qn("w:tcW"))
    if tc_w is None:
        tc_w = OxmlElement("w:tcW")
        tc_pr.append(tc_w)
    tc_w.set(qn("w:w"), str(width))
    tc_w.set(qn("w:type"), "dxa")


def set_cell_margins(cell, top: int = 100, bottom: int = 100, start: int = 120, end: int = 120) -> None:
    tc_pr = cell._tc.get_or_add_tcPr()
    tc_mar = tc_pr.first_child_found_in("w:tcMar")
    if tc_mar is None:
        tc_mar = OxmlElement("w:tcMar")
        tc_pr.append(tc_mar)
    for name, value in (("top", top), ("bottom", bottom), ("start", start), ("end", end)):
        node = tc_mar.find(qn(f"w:{name}"))
        if node is None:
            node = OxmlElement(f"w:{name}")
            tc_mar.append(node)
        node.set(qn("w:w"), str(value))
        node.set(qn("w:type"), "dxa")


def set_table_geometry(table, widths: list[int]) -> None:
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    tbl = table._tbl
    tbl_pr = tbl.tblPr
    tbl_w = tbl_pr.find(qn("w:tblW"))
    if tbl_w is None:
        tbl_w = OxmlElement("w:tblW")
        tbl_pr.append(tbl_w)
    tbl_w.set(qn("w:w"), str(sum(widths)))
    tbl_w.set(qn("w:type"), "dxa")

    tbl_ind = tbl_pr.find(qn("w:tblInd"))
    if tbl_ind is None:
        tbl_ind = OxmlElement("w:tblInd")
        tbl_pr.append(tbl_ind)
    tbl_ind.set(qn("w:w"), "120")
    tbl_ind.set(qn("w:type"), "dxa")

    old_grid = tbl.tblGrid
    if old_grid is not None:
        tbl.remove(old_grid)
    grid = OxmlElement("w:tblGrid")
    for width in widths:
        col = OxmlElement("w:gridCol")
        col.set(qn("w:w"), str(width))
        grid.append(col)
    tbl.insert(1, grid)

    for row in table.rows:
        for idx, cell in enumerate(row.cells):
            if idx < len(widths):
                set_cell_width(cell, widths[idx])
            set_cell_margins(cell)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER


def set_cell_text(cell, text: str, *, bold: bool = False, color: str = INK,
                  fill: str | None = None, size: float = 9.5, align=None) -> None:
    cell.text = ""
    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.15
    if align is not None:
        p.alignment = align
    r = p.add_run(text)
    set_run_font(r, size=size, bold=bold, color=color)
    if fill is not None:
        set_cell_shading(cell, fill)


def add_table(doc: Document, headers: list[str], rows: list[list[str]], widths: list[int],
              *, font_size: float = 9.2, header_fill: str = BLUE, zebra: bool = True) -> None:
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    set_table_geometry(table, widths)
    for idx, header in enumerate(headers):
        set_cell_text(table.rows[0].cells[idx], header, bold=True, color=WHITE,
                      fill=header_fill, size=font_size, align=WD_ALIGN_PARAGRAPH.CENTER)
    for r_idx, row in enumerate(rows):
        cells = table.add_row().cells
        for c_idx, value in enumerate(row):
            fill = LIGHT_GRAY if zebra and r_idx % 2 == 0 else None
            align = WD_ALIGN_PARAGRAPH.CENTER if len(value) <= 12 else None
            set_cell_text(cells[c_idx], value, size=font_size, fill=fill, align=align)
    set_table_geometry(table, widths)
    add_para(doc, "", after=2, first_line=False)


def add_key_table(doc: Document, rows: list[tuple[str, str]]) -> None:
    add_table(
        doc,
        ["项目", "内容"],
        [[k, v] for k, v in rows],
        [2200, TABLE_WIDTH - 2200],
        font_size=9.2,
        header_fill=DARK_BLUE,
    )


def add_caption(doc: Document, text: str) -> None:
    add_para(doc, text, size=9, color=MUTED, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, after=8)


def add_image(doc: Document, path: Path, caption: str, width: float = 6.25) -> None:
    if not path.exists():
        return
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(2)
    p.add_run().add_picture(str(path), width=Inches(width))
    add_caption(doc, caption)


def add_toc_field(doc: Document) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run()

    fld_char = OxmlElement("w:fldChar")
    fld_char.set(qn("w:fldCharType"), "begin")
    run._r.append(fld_char)

    instr = OxmlElement("w:instrText")
    instr.set(qn("xml:space"), "preserve")
    instr.text = r'TOC \o "1-3" \h \z \u'
    run._r.append(instr)

    fld_char = OxmlElement("w:fldChar")
    fld_char.set(qn("w:fldCharType"), "separate")
    run._r.append(fld_char)

    t = OxmlElement("w:t")
    t.text = "目录将在 Word 中自动更新"
    run._r.append(t)

    fld_char = OxmlElement("w:fldChar")
    fld_char.set(qn("w:fldCharType"), "end")
    run._r.append(fld_char)


def add_cover_and_frontmatter(doc: Document) -> None:
    add_para(doc, "2026年“挑战杯”天津市大学生创业计划竞赛", size=18, bold=True,
             color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, before=4, after=8)
    add_para(doc, "商业计划书", size=24, bold=True, color=DARK_BLUE,
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, before=2, after=4)
    add_para(doc, "牧云智舍", size=30, bold=True, color=BLUE,
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, before=4, after=2)
    add_para(doc, "多模态智能牛舍监测与闭环预警平台", size=16.5, bold=True, color=INK,
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, after=4)
    add_para(doc, "低成本硬件 + 边缘 AI + 多端协同", size=11.5, color=MUTED,
             align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, after=6)

    add_image(doc, POSTERS / "01-cover.png", "图 0-1 牧云智舍端边云协同闭环场景示意", width=5.75)
    add_key_table(
        doc,
        [
            ("项目名称", "牧云智舍：多模态智能牛舍监测与闭环预警平台"),
            ("赛道方向", "乡村振兴和农业农村现代化 / 数字农业 / 智慧畜牧"),
            ("产品定位", "面向中小牛舍的低成本智能监测、风险预警与闭环处置平台"),
            ("核心技术", "ESP32-S3、MaixCam、INMP441、Spring Boot、Web/鸿蒙 APP/微信小程序"),
            ("应用场景", "环境监测、异常事件辅助识别、设备联动控制、巡检记录归档"),
        ],
    )

    doc.add_page_break()
    add_para(doc, "公司概况", size=16, bold=True, color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False)
    add_para(doc, "牧云智舍智慧畜牧科技项目团队拟以“低成本硬件、边缘 AI、多端协同”为核心，面向中小规模牛舍建设一套可部署、可追溯、可闭环的智能监测平台。团队依托现有软件原型、硬件方案和技术报告，已完成从现场感知、边缘推理、云端服务到 Web/鸿蒙 APP/微信小程序的完整产品雏形。")
    add_para(doc, "项目公司未来计划以高校创新创业成果转化为起点，在天津及周边肉牛养殖场景开展试点，逐步形成硬件节点销售、平台订阅、部署运维、模型迭代与数据服务相结合的经营模式。项目坚持工程可落地和合规审慎原则，将系统定位为辅助巡检与风险预警工具，不夸大为自动诊断系统。")
    add_para(doc, "项目介绍", size=16, bold=True, color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False)
    add_para(doc, "牧云智舍围绕牛舍“看不见、记不全、联动慢、复盘难”的现场痛点，构建端、边、云、服、应用闭环。端侧使用 ESP32-S3 采集温湿度、氨气、光照、烟雾和执行器状态，边缘侧使用 MaixCam 进行轻量视觉识别，声音节点采集咳嗽、喘鸣、异常叫声等事件线索，云端统一形成风险评分、证据链和处置建议。")
    add_para(doc, "系统支持 Web 驾驶舱、鸿蒙 APP 和微信小程序协同：管理人员可查看存栏、在线设备、环境趋势、风险告警和模型状态；巡检人员可在移动端查看告警证据、确认处置、下发风扇/雾化/声光报警/抓拍等命令，并形成闭环记录。")
    add_para(doc, "荣誉及证书", size=16, bold=True, color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False)
    add_para(doc, "当前项目已形成技术报告、系统代码原型、数据库脚本、Web 展示界面、鸿蒙 APP 原型、微信小程序原型和多组项目介绍海报。后续将围绕软件著作权、实用新型专利、外观/界面作品登记、试点合作证明和竞赛获奖材料进行归档。此处不虚构已获证书，正式提交前可替换为实际证书扫描件。")
    add_para(doc, "市场分析", size=16, bold=True, color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False)
    add_para(doc, "数字农业、智慧畜牧、动物疫病防控和绿色养殖共同推动养殖场基础设施升级。规模化养殖场具备较强信息化投入能力，但数量众多的中小牛舍仍面临人工巡检不连续、异常发现滞后、环境联动不足、数据记录分散和证据链缺失等问题。牧云智舍以低成本节点和渐进部署方式切入，具有较明确的市场缺口。")
    add_para(doc, "意向客户介绍", size=16, bold=True, color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False)
    add_para(doc, "项目早期客户以高校农业实训基地、中小肉牛养殖场、地方智慧农业示范点、畜牧设备经销商和农服机构为主。商业化验证路径为：先完成 3-5 个真实或半真实场景试点，形成可展示数据与案例；再通过设备渠道、农服机构和示范基地进行区域推广。")

    doc.add_page_break()
    add_para(doc, "目录", size=18, bold=True, color=DARK_BLUE, align=WD_ALIGN_PARAGRAPH.CENTER, first_line=False, after=12)
    add_toc_field(doc)
    doc.add_page_break()


def chapter_one(doc: Document) -> None:
    add_heading(doc, "一、执行摘要", 1)
    add_heading(doc, "1. 项目背景", 2)
    add_para(doc, "肉牛养殖正在从经验巡栏走向连续感知和数据驱动管理。传统牛舍依赖人工观察牛只精神状态、采食情况和环境变化，巡检频次有限，夜间、恶劣天气和人员不足时更容易出现盲区。温湿度、氨气、烟雾、通风状态等环境因素会影响牛只呼吸道健康和应激水平；卧倒时间、活动量、咳嗽、喘鸣、异常叫声等信号也需要与现场环境共同判断。")
    add_para(doc, "在中小牛舍场景中，高成本集中式视频监控和复杂工业控制系统往往部署门槛高、维护难度大。牧云智舍希望用可分阶段部署的低成本节点，将“连续采集、边缘初判、云端融合、多端处置、复盘迭代”连接为闭环，为养殖户提供可用、可解释、可追溯的巡检辅助工具。")
    add_heading(doc, "2. 产品概述", 2)
    add_para(doc, "牧云智舍由端侧采集、边缘推理、云端服务、业务应用和运维复盘五层组成。端侧以 ESP32-S3 为核心，连接温湿度、氨气、光照、烟雾等传感器，并控制风扇、雾化、声光报警和抓拍模块；边缘层以 MaixCam 和 INMP441 声音节点为代表，完成视觉事件、声音事件和断点缓存；云端使用 Spring Boot API、MySQL/H2、告警策略和模型版本管理；应用层提供 Web 驾驶舱、鸿蒙 APP 和微信小程序；闭环层完成告警确认、命令下发、处置回执和训练迭代。")
    add_table(
        doc,
        ["能力模块", "产品实现", "用户价值"],
        [
            ["连续环境监测", "温度、湿度、氨气、光照、烟雾、执行器状态持续采集", "减少人工巡检盲区，形成趋势记录"],
            ["边缘 AI 初判", "MaixCam 视觉事件、INMP441 声音事件、阈值判断和断点缓存", "降低带宽压力，提高现场响应速度"],
            ["风险预警", "多模态风险评分、告警等级、证据链和处置建议", "把异常转化为可复核任务"],
            ["闭环处置", "多端告警确认、控制命令下发、处置回执、复盘记录", "形成可追溯的管理闭环"],
        ],
        [1900, 4300, 3160],
    )
    add_heading(doc, "3. 产品优势与市场", 2)
    add_para(doc, "项目的核心优势在于把低成本硬件路线与边缘 AI、云端服务和多端应用结合，既能覆盖中小牛舍的预算约束，也能保留向规模化场区扩展的架构空间。相比单一摄像头或单点传感器方案，牧云智舍强调多模态互证：环境阈值、视觉事件、声音事件、历史趋势和人工复核共同参与风险判断，减少单一指标误报。")
    add_table(
        doc,
        ["优势", "具体表现", "市场意义"],
        [
            ["低成本可部署", "使用 ESP32-S3、MaixCam、常见环境传感器和移动端应用形成试点包", "适合中小牛舍渐进式数字化改造"],
            ["多模态融合", "环境、视觉、声音、趋势和人工复核共同构成风险评分", "提升告警可解释性和复核效率"],
            ["证据链追溯", "告警关联曲线、截图、音频片段、模型版本、处置记录", "便于复盘、培训、质控和责任界定"],
            ["多端协同", "Web 负责总览分析，APP/小程序负责现场巡检和处置", "贴合养殖场不同角色的使用习惯"],
        ],
        [1700, 3900, 3760],
    )
    add_heading(doc, "4. 商业模式", 2)
    add_para(doc, "项目采用“硬件节点包 + 平台部署 + SaaS 订阅 + 运维增值”的组合模式。早期以试点包销售和部署服务为主，解决真实场景接入和样本积累；中期通过平台订阅、模型升级、设备 OTA、数据报表和运维托管形成持续收入；后期与农服机构、畜牧设备渠道和示范基地合作，扩大区域推广能力。")
    add_heading(doc, "5. 财务与投资", 2)
    add_para(doc, "项目目前处于原型到试点阶段，资金主要用于硬件样机、传感器标定、真实牛舍部署、样本采集、模型训练、云服务和现场运维。财务预测采用保守口径，收入不以虚构订单为依据，而以试点转化、设备包销量、订阅场区数和运维服务为核心变量。拟融资资金将优先投入样机迭代、试点验证和可复制交付体系建设。")


def chapter_two(doc: Document) -> None:
    add_heading(doc, "二、产品介绍", 1)
    add_heading(doc, "1. 项目背景", 2)
    add_para(doc, "牛舍风险往往不是单一因素造成。高温高湿可能引起热应激，氨气偏高会增加呼吸道负担，烟雾或火情需要本地快速报警，异常咳嗽、喘鸣和持续叫声需要结合环境背景复核。人工巡检可以发现明显异常，但很难做到全天候连续记录，也难以在事后还原异常发生前后的数据变化。")
    add_para(doc, "牧云智舍的设计思路是把低成本感知节点布到现场，把较耗带宽的视觉和声音处理尽可能前移到边缘，把管理、复核和处置放到云端和多端应用中完成。该路线适合先从单栋牛舍或几个栏位开始验证，再按栏位、牛舍、场区逐步扩展。")
    add_image(doc, POSTERS / "02-background-pain-points.png", "图 2-1 背景与痛点：从人工巡检走向连续感知", width=6.1)
    add_heading(doc, "2. 产品概述", 2)
    add_heading(doc, "2.1 智能牛舍监测平台概述", 3)
    add_para(doc, "牧云智舍不是单一硬件，也不是单一 AI 模型，而是一套围绕牛舍日常巡检构建的端边云服协同平台。系统将环境采集、视觉识别、声音事件、设备控制、告警策略和巡检记录统一在同一业务链路中，重点解决“异常何时发生、依据是什么、谁来确认、如何处置、处置后如何复盘”的问题。")
    add_image(doc, POSTERS / "03-architecture-loop.png", "图 2-2 总体架构：端、边、云、服、应用闭环", width=6.1)
    add_table(
        doc,
        ["层级", "核心组成", "主要功能"],
        [
            ["端侧采集", "ESP32-S3、环境传感器、继电器、风扇、雾化、声光报警", "采集环境和设备状态，执行本地控制"],
            ["边缘推理", "MaixCam、INMP441、轻量模型、断点缓存", "生成视觉/声音事件，减少原始数据上传"],
            ["云端服务", "Spring Boot API、MySQL/H2、告警策略、模型版本", "数据持久化、风险融合、接口服务"],
            ["业务应用", "Web 驾驶舱、鸿蒙 APP、微信小程序", "总览分析、巡检、告警处置和设备控制"],
            ["闭环复盘", "告警确认、命令下发、处置回执、训练迭代", "把每次异常转化为可复盘样本"],
        ],
        [1500, 4000, 3860],
    )
    add_heading(doc, "2.2 产品实施流程", 3)
    add_para(doc, "产品交付流程分为场景勘察、点位设计、硬件安装、通信联调、阈值标定、模型部署、账号配置、巡检培训和试运行复盘。与一次性采购设备不同，牧云智舍的价值来自长期数据积累和闭环流程落地，因此早期部署必须保留人工复核和现场反馈机制。")
    add_table(
        doc,
        ["阶段", "工作内容", "交付物"],
        [
            ["1. 现场勘察", "确认牛舍面积、栏位数量、通风方式、网络条件和电源位置", "部署点位图、风险点清单"],
            ["2. 硬件安装", "安装环境节点、MaixCam、声音节点、执行器控制箱和防护外壳", "硬件接线表、设备编码表"],
            ["3. 联调标定", "传感器校准、MQTT/HTTP 联调、阈值策略设置、断网补传测试", "联调记录、阈值配置"],
            ["4. 试运行", "连续记录环境、视觉、声音和人工复核结果，分析误报漏报", "试运行报告、模型迭代计划"],
            ["5. 正式运行", "形成告警确认、处置回执、巡检日报和设备维护制度", "运行看板、闭环记录"],
        ],
        [1500, 4800, 3060],
    )
    add_heading(doc, "2.3 产品优势", 3)
    add_para(doc, "1. 低成本工程路线。系统使用通用 MCU、边缘摄像头、I2S 麦克风和常见环境传感器完成原型验证，正式部署时预留工业传感器和 RS485/4G 等接口升级空间。")
    add_para(doc, "2. 数据前移与边缘留证。MaixCam 在本地完成视觉初判，只上传结构化事件、置信度和截图路径，声音节点先进行有效声音筛选，再把事件摘要和片段索引上传云端，降低网络和存储压力。")
    add_para(doc, "3. 告警可解释。系统不直接给出兽医诊断结论，而是围绕环境曲线、声音片段、视觉截图、历史趋势和人工复核生成证据链，让巡检人员知道为什么需要关注。")
    add_para(doc, "4. 多端协同落地。Web 面向管理者，移动端面向现场人员，小程序面向轻量协作，三端共享同一后端数据，避免纸质记录和微信群消息造成的信息分散。")
    add_image(doc, POSTERS / "04-hardware-multimodal-ai.png", "图 2-3 硬件与多模态 AI：低成本节点支撑主动预警", width=6.1)


def chapter_three(doc: Document) -> None:
    add_heading(doc, "三、行业与市场分析", 1)
    add_heading(doc, "1. 市场现状", 2)
    add_heading(doc, "1.1 社会背景", 3)
    add_para(doc, "农业农村现代化、绿色养殖、动物疫病防控和数字乡村建设共同推动养殖业基础设施升级。养殖主体对降本增效、风险早筛、过程留痕和管理标准化的需求持续提升。对于肉牛养殖而言，环境、行为、声音和巡检记录共同构成健康管理和生产管理的基础数据。")
    add_heading(doc, "1.2 智慧畜牧行业发展情况", 3)
    add_para(doc, "当前智慧畜牧产品主要集中在规模化猪场、奶牛场和大型牧场，常见能力包括环境监测、视频监控、饲喂管理、耳标定位、繁育管理和生产报表。肉牛中小养殖场的信息化程度相对分散，既需要低成本部署，也需要产品足够简单，能够被现场人员持续使用。")
    add_heading(doc, "1.3 智能牛舍监测产品现状", 3)
    add_para(doc, "市场上已有单点环境监测器、普通摄像头、智能环控设备和部分 AI 视频识别方案，但它们往往存在数据孤岛、证据链不足、移动端闭环弱、设备联动不足或成本偏高等问题。牧云智舍把多个轻量能力组合起来，形成针对中小牛舍的可部署方案。")
    add_heading(doc, "1.4 市场现有产品分析", 3)
    add_table(
        doc,
        ["方案类型", "典型能力", "主要不足", "牧云智舍切入点"],
        [
            ["单点传感器", "温湿度、氨气等指标采集", "只能看数值，缺少事件和处置闭环", "接入执行器、告警和证据链"],
            ["普通视频监控", "远程查看牛舍画面", "依赖人工盯屏，带宽和存储压力较大", "边缘视觉只上传事件和截图"],
            ["工业环控系统", "风机、水帘、通风等自动控制", "成本较高，AI 与移动巡检弱", "低成本节点先试点，保留升级接口"],
            ["单一 AI 识别", "行为或图像分类", "误报难复核，缺少环境背景", "环境、声音、视觉和人工复核融合"],
        ],
        [1700, 2500, 2600, 2560],
    )
    add_heading(doc, "2. 市场环境分析", 2)
    add_heading(doc, "2.1 经济环境变化对智慧畜牧监测市场的影响", 3)
    add_para(doc, "人工成本上升、养殖收益波动和设备投入约束，使养殖户更关注“投入产出比明确”的数字化产品。能够分阶段部署、先解决高频痛点、后续扩展增值服务的产品更容易被接受。牧云智舍的早期产品包以较低硬件成本和可演示价值切入，适合试点验证。")
    add_heading(doc, "2.2 社会环境变化对智慧畜牧监测市场的影响", 3)
    add_para(doc, "食品安全、动物福利、疫病防控和绿色养殖意识提高，推动养殖过程从经验记录走向数据留痕。养殖户、合作社、学校实训基地和示范园区需要更直观的可视化工具展示养殖管理能力，也需要可追溯记录支撑教学、管理和复盘。")
    add_heading(doc, "2.3 政策环境变化对智慧畜牧监测市场的影响", 3)
    add_para(doc, "农业数字化、智慧农业基础设施、畜禽粪污与环境管理、动物疫病防控等政策方向为项目提供了应用背景。商业计划书中不引用未经核实的具体政策文件名称，而以政策方向和市场趋势作为判断依据，避免把政策支持夸大为确定订单。")
    add_table(
        doc,
        ["驱动方向", "对市场的影响", "项目响应"],
        [
            ["数字农业", "推动农业生产过程采集、分析和展示", "构建牛舍数据看板和 API 服务"],
            ["智慧畜牧", "提升养殖设施智能化和管理标准化", "提供端边云服协同监测平台"],
            ["疫病防控", "需要更早发现异常和留存过程证据", "建立声音/视觉/环境证据链"],
            ["绿色养殖", "强调环境控制和资源效率", "通过风扇、雾化、报警等联动减少异常持续时间"],
            ["教学实训", "需要可演示、可拆解、可复现的系统案例", "提供完整技术路线和多端原型"],
        ],
        [1800, 3800, 3760],
    )
    add_heading(doc, "3. 市场竞争优势", 2)
    add_heading(doc, "3.1 已有智慧畜牧监测方案", 3)
    add_para(doc, "已有方案通常在单个维度较强，例如视频监控便于查看现场画面，环控系统便于自动控制，传感器网关便于采集环境数据。但中小牛舍需要的是把风险发现、证据复核和现场处置串起来的轻量系统。牧云智舍强调“辅助巡检”的实际定位，降低用户对复杂 AI 系统的理解和使用门槛。")
    add_heading(doc, "3.2 竞争优势总结", 3)
    add_table(
        doc,
        ["竞争维度", "传统方案常见问题", "牧云智舍优势"],
        [
            ["部署成本", "一次性建设成本高，扩展依赖专业施工", "节点化部署，先从重点栏位试点"],
            ["数据闭环", "采集、告警、处置和复盘分散", "同一平台完成告警确认、命令下发和回执"],
            ["AI 落地", "模型脱离现场数据，误报难解释", "保留截图、音频、曲线和人工复核"],
            ["多端协同", "PC 与现场移动端割裂", "Web、鸿蒙 APP、小程序共享后端"],
            ["可扩展性", "单一设备难接入新模态", "预留传感器、模型、OTA 和数据服务扩展"],
        ],
        [1600, 3900, 3860],
    )
    add_heading(doc, "4. 市场需求", 2)
    add_heading(doc, "4.1 中小牛舍巡检场景", 3)
    add_para(doc, "中小牛舍最直接的需求是减少人工巡检盲区并留下异常证据。系统可以优先覆盖温湿度、氨气、烟雾、风扇和雾化状态，在异常时推送移动端告警并触发抓拍。用户不需要一次性建设完整智慧牧场，可先用基础节点完成风险可视化。")
    add_heading(doc, "4.2 规模化场区监测场景", 3)
    add_para(doc, "规模化场区更关注多栏位、多设备、多角色协同和运维效率。牧云智舍可按牛舍或栏位复制节点，通过 Web 驾驶舱集中展示环境趋势、风险队列、设备在线状态和模型版本，帮助管理者进行分区复盘。")
    add_heading(doc, "4.3 应用前景", 3)
    add_para(doc, "项目可拓展到教学实训、示范基地展示、农服机构巡检包、畜牧设备渠道增值服务等场景。随着真实样本积累，视觉、声音和多模态风险评分可逐步迭代，平台也可扩展到羊舍、猪舍等相近养殖场景。")
    add_heading(doc, "5. 市场预测", 2)
    add_heading(doc, "5.1 市场规模", 3)
    add_para(doc, "本计划书采用自下而上的试点预测口径：第一阶段验证 3-5 个试点场景；第二阶段在区域内复制到 20-50 个栏位或点位；第三阶段通过渠道合作形成标准化产品包。由于项目尚未取得正式商业订单，所有预测均作为经营目标和测算假设，不作为已实现业绩。")
    add_heading(doc, "5.2 上中下游市场概况", 3)
    add_table(
        doc,
        ["环节", "主体", "机会"],
        [
            ["上游", "传感器、摄像头、MCU、外壳、电源、通信模块供应商", "通过标准化 BOM 降低硬件成本"],
            ["中游", "系统集成、软件平台、模型训练、现场运维团队", "形成产品包和服务包"],
            ["下游", "养殖场、合作社、教学实训基地、示范园区、农服机构", "获得风险预警、巡检闭环和展示能力"],
        ],
        [1300, 4200, 3860],
    )
    add_heading(doc, "5.3 市场分布", 3)
    add_para(doc, "早期重点面向学校所在地及周边具备合作条件的牛舍、农牧实训基地和示范点，减少跨区域运维成本。中期通过天津、河北、山东、河南等肉牛养殖和农业示范资源较集中的区域开展渠道合作。长期可根据设备适配和样本积累向更多畜禽养殖场景延伸。")


def chapter_four(doc: Document) -> None:
    add_heading(doc, "四、商业模式", 1)
    add_heading(doc, "1. 产品策略", 2)
    add_heading(doc, "1.1 产品定位", 3)
    add_para(doc, "牧云智舍定位为“中小牛舍低成本智能巡检与风险预警平台”。它不是替代兽医的诊断软件，而是将现场数据连续化、异常事件结构化、处置过程闭环化的管理工具。产品重点服务预算有限但希望提升管理效率的养殖主体。")
    add_heading(doc, "1.2 价值载体", 3)
    add_table(
        doc,
        ["价值载体", "内容", "商业化方式"],
        [
            ["硬件节点包", "环境节点、视觉节点、声音节点、执行器控制模块", "设备销售或租赁"],
            ["平台软件", "后端服务、Web 驾驶舱、移动端、小程序", "部署服务和订阅"],
            ["模型服务", "视觉/声音模型训练、版本管理、阈值调优", "年度服务或增值包"],
            ["运维服务", "安装调试、传感器标定、故障排查、报表复盘", "项目服务费或托管费"],
            ["数据报告", "巡检日报、风险月报、设备在线率、处置闭环率", "按场区/设备收费"],
        ],
        [1700, 4500, 3160],
    )
    add_heading(doc, "1.3 目标客户", 3)
    add_para(doc, "目标客户包括中小肉牛养殖场、家庭牧场、农业实训基地、智慧农业示范园区、畜牧设备经销商、农服机构和地方数字农业项目实施方。早期优先选择愿意配合采集数据并共同打磨流程的试点客户。")
    add_heading(doc, "2. 价格策略", 2)
    add_heading(doc, "2.1 定价原则", 3)
    add_para(doc, "定价遵循“低门槛试点、按需扩展、服务持续”的原则。基础版先覆盖环境监测和移动端告警，增强版增加视觉/声音事件和证据链，高级版支持多栏位、多设备、模型管理和运维报表。")
    add_para(doc, "1. 分层定价体系。基础版满足单栋牛舍基础监测，增强版满足多模态预警，高级版满足规模化管理。")
    add_para(doc, "2. 试点优惠机制。对教学实训基地和首批合作牛舍提供试点价格，换取真实数据、反馈和案例授权。")
    add_para(doc, "3. 动态成本监控。根据硬件 BOM、安装人工、云服务和售后成本调整报价，避免低价试点无法持续。")
    add_para(doc, "4. 长期协议激励。对年度订阅、区域合作和渠道伙伴提供阶梯折扣。")
    add_heading(doc, "2.2 定价策略及方法", 3)
    add_table(
        doc,
        ["产品包", "包含内容", "建议收费口径"],
        [
            ["基础监测包", "ESP32-S3 环境节点、温湿度/氨气/烟雾/光照、移动端告警", "硬件成本加部署服务，平台低价订阅"],
            ["AI 增强包", "MaixCam 视觉节点、INMP441 声音节点、风险证据链", "硬件包加模型服务费"],
            ["闭环管理包", "Web 驾驶舱、设备控制、处置回执、报表复盘", "按场区或设备数订阅"],
            ["运维托管包", "传感器标定、设备巡检、模型迭代、OTA 升级", "年度服务费"],
        ],
        [1700, 4700, 2960],
    )
    add_heading(doc, "3. 促销策略", 2)
    add_table(
        doc,
        ["促销方式", "目标对象", "执行方式", "预期效果"],
        [
            ["试点示范", "养殖场、学校实训基地", "提供样机和短周期试运行", "形成真实案例和反馈"],
            ["路演展示", "竞赛评委、合作机构、渠道商", "用 Web/移动端和硬件模型展示闭环", "提升项目可信度"],
            ["渠道联合", "畜牧设备商、农服机构", "与现有设备销售和维保服务绑定", "降低获客成本"],
            ["内容传播", "项目海报、技术报告、演示视频", "展示端边云架构和场景价值", "提升认知和转介绍"],
        ],
        [1500, 2300, 3300, 2260],
    )
    add_heading(doc, "4. 推广策略", 2)
    add_para(doc, "推广采取“样机展示—试点落地—案例复盘—区域复制”的路径。第一阶段通过挑战杯、校内外创新创业平台、农业实训基地展示产品完整度；第二阶段选择真实牛舍进行连续运行，积累传感器标定、模型误报、现场维护等经验；第三阶段将试点材料转化为标准化交付手册、报价包和渠道培训资料。")
    add_table(
        doc,
        ["阶段", "推广重点", "关键指标"],
        [
            ["原型展示期", "完整演示端边云闭环和多端应用", "演示稳定性、评审反馈、合作意向"],
            ["试点验证期", "接入真实牛舍数据，完成连续运行", "在线率、告警闭环率、误报复核率"],
            ["区域复制期", "形成标准化硬件包和部署流程", "部署周期、售后成本、续费意愿"],
            ["平台运营期", "提供模型迭代、OTA、数据报告", "订阅收入、客户留存、渠道转化"],
        ],
        [1500, 5000, 2860],
    )
    add_heading(doc, "5. 渠道策略", 2)
    add_heading(doc, "5.1 销售渠道选择", 3)
    add_table(
        doc,
        ["渠道", "适合阶段", "优势", "风险控制"],
        [
            ["高校/实训基地", "早期", "便于演示、数据采集和教学转化", "明确试点边界和数据权限"],
            ["畜牧设备经销商", "中期", "已有客户资源和安装经验", "建立标准报价和售后分工"],
            ["农服机构", "中期", "接近中小养殖户，便于区域服务", "提供培训和运维规范"],
            ["示范园区/政府项目实施方", "中后期", "展示价值强，利于形成样板", "不将政策方向等同于确定订单"],
        ],
        [1700, 1700, 3200, 2760],
    )
    add_heading(doc, "5.2 销售渠道建立", 3)
    add_para(doc, "渠道建设以产品可交付为前提，先完成标准化硬件清单、安装手册、平台部署手册、售后维护清单和试点验收指标。对渠道伙伴提供产品培训、演示账号、报价模板和常见问题手册，避免渠道销售承诺超过系统真实能力。")
    add_image(doc, POSTERS / "05-software-results.png", "图 4-1 软件成果展示：Web、鸿蒙 APP、小程序协同", width=6.1)


def chapter_five(doc: Document) -> None:
    add_heading(doc, "五、成员简介", 1)
    add_heading(doc, "1. 核心团队", 2)
    add_heading(doc, "1.1核心成员", 3)
    add_para(doc, "由于用户未提供真实成员姓名和证书信息，本计划书采用岗位制团队描述，正式提交前可将“姓名待填”替换为实际姓名、学院专业、分工、获奖和证明材料。岗位设置依据项目当前技术栈和商业化路径设计。")
    add_table(
        doc,
        ["岗位", "姓名", "主要职责", "能力要求"],
        [
            ["项目负责人", "待填", "统筹产品定位、竞赛材料、试点合作、资源协调", "商业计划、项目管理、畜牧场景理解"],
            ["硬件负责人", "待填", "ESP32-S3、传感器、继电器、执行器、电源和外壳", "嵌入式开发、弱电安全、现场调试"],
            ["AI 算法负责人", "待填", "MaixCam 视觉、声音事件、多模态风险评分、样本标注", "计算机视觉、音频特征、模型评估"],
            ["后端负责人", "待填", "Spring Boot API、数据库、告警策略、模型版本管理", "Java、数据库、接口设计"],
            ["Web/移动端负责人", "待填", "Vue Web、鸿蒙 APP、微信小程序、多端交互", "前端工程、移动开发、用户体验"],
            ["运营与试点负责人", "待填", "客户调研、试点部署、培训、售后和渠道对接", "市场调研、沟通执行、服务交付"],
        ],
        [1450, 1050, 4300, 2560],
        font_size=8.8,
    )
    add_heading(doc, "1.2团队管理", 3)
    add_para(doc, "团队采用“产品负责人牵引、模块负责人交付、周迭代复盘”的管理方式。每周围绕硬件联调、后端接口、前端交互、模型训练、试点反馈和商业材料进行同步；每个版本形成演示记录、问题清单、责任人和下一步交付。")
    add_table(
        doc,
        ["管理机制", "执行方式"],
        [
            ["版本节奏", "两周一个小版本，明确演示目标和可验证功能"],
            ["质量控制", "硬件通信、接口返回、前端页面、移动端流程和文档同步验收"],
            ["数据治理", "样本来源、标注人员、模型版本和人工复核结果统一归档"],
            ["风险管理", "对硬件安全、模型误报、用户隐私和兽医诊断边界建立红线"],
            ["外部协作", "与指导教师、养殖场、农服机构和设备供应商建立定期沟通"],
        ],
        [2200, 7160],
    )


def chapter_six(doc: Document) -> None:
    add_heading(doc, "六、财务预测", 1)
    add_heading(doc, "1. 财务假设", 2)
    add_para(doc, "财务预测以三年为周期，采用保守试点口径。第一年以样机、试点和示范场景为主；第二年开始形成小批量硬件交付和平台订阅；第三年通过渠道合作和运维服务提高复购与续费。由于项目尚未形成正式销售合同，以下数值仅用于商业计划测算。")
    add_heading(doc, "1.1会计主体假设", 3)
    add_para(doc, "假设项目在完成试点验证后成立“牧云智舍智慧畜牧科技有限公司（暂定名）”作为经营主体，收入和成本均按该主体进行测算。")
    add_heading(doc, "1.2持续经营假设", 3)
    add_para(doc, "假设项目能够持续获得试点客户反馈、硬件供应链支持和平台维护能力，在三年内保持产品迭代和服务交付。")
    add_heading(doc, "1.3会计分期假设", 3)
    add_para(doc, "财务预测按年度分期，收入确认以硬件交付、部署验收、订阅服务周期和运维合同为依据。")
    add_heading(doc, "1.4货币计量假设", 3)
    add_para(doc, "本计划书财务测算以人民币万元为单位，未考虑重大汇率波动、不可抗力和突发公共卫生事件等影响。")
    add_heading(doc, "2.融资与股权", 2)
    add_heading(doc, "2.1融资需求", 3)
    add_para(doc, "项目拟在原型到试点阶段融资 80 万元，用于硬件样机、小批量试制、真实牛舍试点、传感器标定、样本采集、模型训练、平台部署、知识产权申请和市场验证。融资额度可根据竞赛孵化资金、校企合作资金和试点客户共建资源进行调整。")
    add_heading(doc, "2.2资金筹措方案", 3)
    add_table(
        doc,
        ["资金来源", "金额（万元）", "用途"],
        [
            ["团队自筹及竞赛孵化", "10", "样机材料、演示设备和基础云服务"],
            ["校企合作/试点共建", "20", "真实牛舍部署、传感器标定和现场维护"],
            ["天使投资或产业伙伴", "50", "小批量试制、模型样本扩充、渠道建设"],
        ],
        [2600, 1600, 5160],
    )
    add_heading(doc, "2.3资金来源", 3)
    add_para(doc, "资金来源优先考虑非稀释性竞赛孵化资金、学校创新创业支持、农业实训基地共建经费和试点项目款；在验证产品可交付和付费意愿后，再引入产业资本或天使投资。")
    add_heading(doc, "2.4股权结构", 3)
    add_table(
        doc,
        ["股东类别", "规划比例", "说明"],
        [
            ["创始团队", "70%", "保持技术和产品控制权"],
            ["指导教师/顾问激励池", "5%", "用于技术、畜牧和产业顾问长期支持"],
            ["员工期权池", "10%", "用于吸引硬件、算法、销售和运维人才"],
            ["外部投资人", "15%", "以试点验证后估值为基础引入"],
        ],
        [2600, 1600, 5160],
    )
    add_heading(doc, "3. 财务预算", 2)
    add_heading(doc, "3.1 制造成本预测", 3)
    add_table(
        doc,
        ["项目", "第一年", "第二年", "第三年", "说明"],
        [
            ["环境节点", "8", "28", "80", "ESP32-S3、传感器、外壳、电源和安装材料"],
            ["视觉节点", "6", "22", "60", "MaixCam、支架、防护件和通信模块"],
            ["声音节点", "2", "8", "25", "INMP441、采集板和防护件"],
            ["执行器控制", "4", "15", "45", "继电器、风扇/雾化/报警接口和安全隔离"],
            ["合计", "20", "73", "210", "按小批量试制和复制部署测算"],
        ],
        [2100, 1200, 1200, 1200, 3660],
        font_size=8.8,
    )
    add_heading(doc, "3.2 期间费用预测", 3)
    add_table(
        doc,
        ["费用项目", "第一年", "第二年", "第三年", "说明"],
        [
            ["研发费用", "28", "45", "70", "硬件迭代、模型训练、平台开发"],
            ["销售费用", "8", "20", "45", "试点拓展、路演材料、渠道培训"],
            ["管理费用", "10", "18", "32", "办公、财务、法务、知识产权"],
            ["云服务与运维", "4", "12", "30", "服务器、日志、远程维护、设备 OTA"],
            ["合计", "50", "95", "177", "随客户和设备规模增长"],
        ],
        [2100, 1200, 1200, 1200, 3660],
        font_size=8.8,
    )
    add_heading(doc, "3.3 销售收入预测", 3)
    add_table(
        doc,
        ["收入类别", "第一年", "第二年", "第三年", "测算逻辑"],
        [
            ["硬件节点包", "18", "85", "260", "按试点包和小批量设备包交付测算"],
            ["平台部署服务", "12", "45", "120", "按场区部署和联调验收测算"],
            ["SaaS 订阅", "3", "36", "150", "按场区/设备数年度订阅测算"],
            ["运维与模型服务", "2", "24", "110", "按传感器标定、模型迭代和报表服务测算"],
            ["合计", "35", "190", "640", "预测口径，非已签订单"],
        ],
        [2100, 1200, 1200, 1200, 3660],
        font_size=8.8,
    )
    add_heading(doc, "3.4预测资产负债表", 3)
    add_table(
        doc,
        ["项目", "第一年", "第二年", "第三年", "说明"],
        [
            ["流动资产", "42", "120", "320", "现金、应收账款、存货"],
            ["固定资产", "18", "35", "60", "测试设备、演示设备、工具"],
            ["无形资产", "8", "18", "35", "软件著作权、专利申请、模型资产"],
            ["资产合计", "68", "173", "415", "预测值"],
            ["流动负债", "15", "36", "90", "供应商款、应付服务费用"],
            ["长期负债", "0", "0", "0", "暂不规划银行长期借款"],
            ["所有者权益", "53", "137", "325", "融资和留存收益形成"],
        ],
        [2300, 1200, 1200, 1200, 3460],
        font_size=8.8,
    )
    add_heading(doc, "3.5预测利润表", 3)
    add_table(
        doc,
        ["项目", "第一年", "第二年", "第三年", "说明"],
        [
            ["营业收入", "35", "190", "640", "硬件、部署、订阅、运维"],
            ["营业成本", "24", "105", "300", "硬件制造、部署人工、云服务"],
            ["毛利", "11", "85", "340", "随软件订阅占比提升而改善"],
            ["期间费用", "50", "95", "177", "研发、销售、管理、运维"],
            ["净利润", "-39", "-10", "163", "第三年进入盈利预测"],
        ],
        [2300, 1200, 1200, 1200, 3460],
        font_size=8.8,
    )
    add_heading(doc, "3.6预测现金流量表", 3)
    add_table(
        doc,
        ["项目", "第一年", "第二年", "第三年", "说明"],
        [
            ["经营现金流", "-45", "-8", "145", "前两年研发和试点投入较高"],
            ["投资现金流", "-18", "-25", "-35", "测试设备、样机和工具投入"],
            ["筹资现金流", "80", "30", "0", "融资和试点共建资金"],
            ["期末现金余额", "17", "14", "124", "预测值"],
        ],
        [2300, 1200, 1200, 1200, 3460],
        font_size=8.8,
    )
    add_heading(doc, "4财务能力分析", 2)
    add_heading(doc, "4.1 盈利能力分析", 3)
    add_para(doc, "项目第一、二年处于研发和试点投入期，利润承压；第三年随着标准化硬件包、平台订阅和运维服务占比提升，毛利率和净利率改善。盈利能力的关键在于降低单场部署成本、提高订阅续费率和控制售后维护成本。")
    add_heading(doc, "4.2 营运能力分析", 3)
    add_para(doc, "营运效率主要取决于硬件 BOM 标准化、安装周期、远程运维能力和渠道伙伴培训效果。若能将部署流程拆解为标准点位设计、设备编码、联调验收和培训交接，项目可降低复制成本。")
    add_heading(doc, "4.3偿债能力分析", 3)
    add_para(doc, "计划期内不依赖长期债务融资，主要通过股权、试点共建和经营现金流支持发展。短期负债主要来自供应商账期和应付服务费用，应通过订单验收节点和预付款机制降低现金压力。")
    add_heading(doc, "4.4 发展能力分析", 3)
    add_para(doc, "项目发展能力来自四类资产：一是可复制的硬件节点包；二是逐步积累的本地牛舍图像和声音样本；三是多端应用和告警闭环流程；四是试点案例和渠道合作关系。")
    add_heading(doc, "4.5 综合分析结论", 3)
    add_para(doc, "牧云智舍短期不是高利润项目，而是需要通过真实试点验证产品价值、完善交付流程和积累样本数据的工程型项目。只要能控制硬件成本、提高告警闭环价值并形成续费服务，项目具备从竞赛原型走向区域试点的商业可行性。")
    add_heading(doc, "5风险资本退出", 2)
    add_para(doc, "投资退出路径包括：在项目形成稳定客户和订阅收入后进行下一轮融资，由新投资人承接部分股权；与畜牧设备企业、农服平台或智慧农业集成商进行战略合作或并购；在区域市场达到一定规模后通过创始团队回购或利润分红实现退出。")


def chapter_seven(doc: Document) -> None:
    add_heading(doc, "七、教育维度", 1)
    add_heading(doc, "1. 带动就业", 2)
    add_heading(doc, "1.1 直接带动就业", 3)
    add_para(doc, "项目商业化后可直接形成嵌入式硬件工程师、AI 算法工程师、后端工程师、前端/移动端工程师、现场运维工程师、客户成功、销售和数据标注等岗位。早期团队规模预计 6-10 人，中期随试点扩展增加运维和渠道岗位。")
    add_heading(doc, "1.2 间接带动就业", 3)
    add_para(doc, "项目可带动传感器供应、弱电安装、畜牧设备维护、区域农服、数据标注、示范基地讲解和职业教育培训等间接岗位。对于农业院校和职业学校，系统可作为智慧畜牧实训平台，帮助学生获得跨学科项目经验。")
    add_heading(doc, "2. 引领教育", 2)
    add_heading(doc, "2.1 技能提升", 3)
    add_para(doc, "牧云智舍覆盖嵌入式、物联网、计算机视觉、音频处理、后端服务、数据库、Web 前端、移动应用、产品设计和商业计划等技能模块。学生可以围绕真实牛舍场景完成需求调研、原型开发、数据采集、模型评估和商业验证。")
    add_heading(doc, "2.2 多学科交叉", 3)
    add_para(doc, "项目连接信息技术、畜牧兽医、农业工程、环境控制、创新创业和市场营销。技术团队必须理解养殖现场的电源、网络、粉尘、湿度、动物行为和人员流程，畜牧方向学生也能通过平台理解数据化管理方法。")
    add_heading(doc, "2.3 产学研协同创新", 3)
    add_para(doc, "项目适合与农业院校、实训基地、养殖企业和地方农服机构共建试点。学校提供技术研发和学生团队，企业提供真实场景和反馈，农服机构提供渠道和维护能力，共同推动智慧畜牧成果转化。")
    add_table(
        doc,
        ["协同主体", "参与方式", "预期成果"],
        [
            ["高校团队", "技术研发、样本标注、模型训练、竞赛材料", "形成软件原型、技术报告、知识产权"],
            ["养殖场/实训基地", "提供场景、数据、试点反馈和验收意见", "形成真实案例和运行记录"],
            ["设备供应商", "提供传感器、摄像头、外壳、电源和安装支持", "降低硬件成本和维护难度"],
            ["农服机构", "参与区域推广、培训和售后", "形成可复制服务网络"],
        ],
        [1800, 4100, 3460],
    )


def chapter_eight(doc: Document) -> None:
    add_heading(doc, "八、附件-版权成果证明", 1)
    add_para(doc, "本章按模板保留附件结构。当前项目已有技术报告、项目代码、Web/鸿蒙 APP/微信小程序原型、数据库脚本和项目海报等材料；正式提交前应补充真实证书、软著受理通知、专利受理通知、试点证明、合作意向书或演示视频二维码。以下不虚构证书编号，仅列出拟归档材料。")
    add_heading(doc, "1. 发明专利", 2)
    add_table(
        doc,
        ["拟申报方向", "技术要点", "当前状态"],
        [
            ["多模态牛舍风险预警方法", "融合环境阈值、视觉事件、声音事件、历史趋势和人工复核生成风险评分", "拟申报/待检索"],
            ["边缘侧事件留证与断点补传方法", "在弱网环境下保存关键事件摘要、截图索引和回执记录", "拟申报/待检索"],
        ],
        [2500, 4700, 2160],
    )
    add_heading(doc, "2. 实用新型专利", 2)
    add_table(
        doc,
        ["拟申报方向", "结构组成", "当前状态"],
        [
            ["低成本牛舍环境与执行器联动节点", "ESP32-S3、传感器接口、继电器隔离、电源和防护外壳", "拟申报"],
            ["牛舍视觉与声音边缘采集装置", "MaixCam、I2S 麦克风、支架、防护罩和通信接口", "拟申报"],
        ],
        [2500, 4700, 2160],
    )
    add_heading(doc, "3. 作品著作权", 2)
    add_table(
        doc,
        ["软件/作品名称", "内容", "状态"],
        [
            ["牧云智舍智能牛舍监测平台 Web 系统", "Vue3、ECharts、Three.js、设备控制和风险看板", "拟登记软著"],
            ["牧云智舍智能牛舍监测平台后端系统", "Spring Boot API、数据库、告警策略、模型版本管理", "拟登记软著"],
            ["牧云智舍移动巡检 APP", "鸿蒙 APP 巡检、告警、识别记录和设备链路", "拟登记软著"],
            ["牧云智舍微信小程序", "移动端总览、照片诊断、历史记录和管理入口", "拟登记软著"],
        ],
        [2800, 4300, 2260],
    )
    add_heading(doc, "4. 区块链登记证书", 2)
    add_para(doc, "项目可将关键版本的技术报告、界面设计、项目海报、算法流程图、数据库设计和演示视频进行时间戳或区块链存证，用于证明作品形成时间和版本演进。正式材料应附登记证书截图、哈希值、登记时间和对应文件清单。")
    add_table(
        doc,
        ["材料类型", "建议存证内容", "备注"],
        [
            ["技术报告", "《数牧增效智能牛舍监测平台技术报告》及后续更名版", "用于证明系统设计形成时间"],
            ["软件代码", "后端、Web、鸿蒙 APP、小程序关键版本压缩包", "用于软著和版本留存"],
            ["项目视觉材料", "海报、PPT、架构图、演示视频", "用于竞赛展示材料归档"],
            ["试点数据", "脱敏后的运行记录、告警闭环记录和验收材料", "需注意数据合规和客户授权"],
        ],
        [2200, 5000, 2160],
    )
    add_image(doc, POSTERS / "06-innovation-plan.png", "图 8-1 创新应用与计划：从原型到试点部署", width=6.1)


def add_update_fields_setting(doc: Document) -> None:
    settings = doc.settings._element
    existing = settings.find(qn("w:updateFields"))
    if existing is None:
        update = OxmlElement("w:updateFields")
        update.set(qn("w:val"), "true")
        settings.append(update)
    else:
        existing.set(qn("w:val"), "true")


def build() -> Path:
    if not TEMPLATE.exists():
        raise FileNotFoundError(f"Template not found: {TEMPLATE}")

    doc = Document(str(TEMPLATE))
    clear_body(doc)
    setup_styles(doc)
    section_setup(doc)

    add_cover_and_frontmatter(doc)
    chapter_one(doc)
    chapter_two(doc)
    chapter_three(doc)
    chapter_four(doc)
    chapter_five(doc)
    chapter_six(doc)
    chapter_seven(doc)
    chapter_eight(doc)
    add_update_fields_setting(doc)

    doc.save(str(FINAL_ASCII))
    FINAL_CN.write_bytes(FINAL_ASCII.read_bytes())
    return FINAL_CN


if __name__ == "__main__":
    path = build()
    print(path)
