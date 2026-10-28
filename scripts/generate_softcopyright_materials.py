from __future__ import annotations

import html
import re
import textwrap
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Image, Paragraph, Table, TableStyle


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "软著材料"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FONT_REG = "Deng"
FONT_BOLD = "DengBold"
FONT_PATH = Path(r"C:\Windows\Fonts\Deng.ttf")
FONT_BOLD_PATH = Path(r"C:\Windows\Fonts\Dengb.ttf")
if not FONT_PATH.exists():
    FONT_PATH = Path(r"C:\Windows\Fonts\simhei.ttf")
if not FONT_BOLD_PATH.exists():
    FONT_BOLD_PATH = FONT_PATH
pdfmetrics.registerFont(TTFont(FONT_REG, str(FONT_PATH)))
pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONT_BOLD_PATH)))

PAGE_W, PAGE_H = A4
MARGIN_X = 18 * mm
MARGIN_TOP = 19 * mm
MARGIN_BOTTOM = 16 * mm
CONTENT_W = PAGE_W - 2 * MARGIN_X

TITLE_STYLE = ParagraphStyle(
    "doc-title",
    fontName=FONT_BOLD,
    fontSize=17,
    leading=23,
    textColor=colors.HexColor("#103B34"),
    alignment=TA_LEFT,
    spaceAfter=8,
)
SECTION_STYLE = ParagraphStyle(
    "section",
    fontName=FONT_BOLD,
    fontSize=11.5,
    leading=16,
    textColor=colors.HexColor("#1C6B5A"),
    spaceBefore=3,
    spaceAfter=6,
)
BODY_STYLE = ParagraphStyle(
    "body",
    fontName=FONT_REG,
    fontSize=9.6,
    leading=15.2,
    textColor=colors.HexColor("#25322F"),
    alignment=TA_LEFT,
    spaceAfter=7,
)
SMALL_STYLE = ParagraphStyle(
    "small",
    fontName=FONT_REG,
    fontSize=8,
    leading=11.5,
    textColor=colors.HexColor("#53645F"),
)
CODE_STYLE = ParagraphStyle(
    "code",
    fontName=FONT_REG,
    fontSize=8.3,
    leading=12,
    textColor=colors.HexColor("#25322F"),
    backColor=colors.HexColor("#F2F7F4"),
    borderColor=colors.HexColor("#D2E3DC"),
    borderWidth=0.5,
    borderPadding=6,
    spaceAfter=8,
)


def esc(value: str) -> str:
    return html.escape(value, quote=False)


def draw_header_footer(c: canvas.Canvas, page_no: int, total: int, label: str) -> None:
    c.setFillColor(colors.HexColor("#103B34"))
    c.rect(0, PAGE_H - 12 * mm, PAGE_W, 12 * mm, fill=1, stroke=0)
    c.setFillColor(colors.white)
    c.setFont(FONT_BOLD, 8.8)
    c.drawString(MARGIN_X, PAGE_H - 7.6 * mm, "牛舍多模态监测平台 V1.0")
    c.setFont(FONT_REG, 8.2)
    c.drawRightString(PAGE_W - MARGIN_X, PAGE_H - 7.6 * mm, label)
    c.setStrokeColor(colors.HexColor("#C9D8D2"))
    c.line(MARGIN_X, 12 * mm, PAGE_W - MARGIN_X, 12 * mm)
    c.setFillColor(colors.HexColor("#657872"))
    c.setFont(FONT_REG, 7.8)
    c.drawString(MARGIN_X, 7.2 * mm, "软件著作权鉴别材料｜申请软件：牛舍多模态监测平台 V1.0")
    c.drawRightString(PAGE_W - MARGIN_X, 7.2 * mm, f"第 {page_no:02d} 页 / 共 {total:02d} 页")


def draw_para(c: canvas.Canvas, text: str, style: ParagraphStyle, x: float, y: float, width: float) -> float:
    para = Paragraph(esc(text), style)
    _, h = para.wrap(width, PAGE_H)
    para.drawOn(c, x, y - h)
    return y - h


def draw_rich_para(c: canvas.Canvas, markup: str, style: ParagraphStyle, x: float, y: float, width: float) -> float:
    para = Paragraph(markup, style)
    _, h = para.wrap(width, PAGE_H)
    para.drawOn(c, x, y - h)
    return y - h


def draw_image(c: canvas.Canvas, path: Path, x: float, y: float, width: float, max_height: float) -> float:
    if not path.exists():
        return y
    image = Image(str(path))
    iw, ih = image.imageWidth, image.imageHeight
    scale = min(width / iw, max_height / ih)
    image.drawWidth = iw * scale
    image.drawHeight = ih * scale
    image.drawOn(c, x + (width - image.drawWidth) / 2, y - image.drawHeight)
    return y - image.drawHeight - 6


def code_line_is_secret(line: str) -> bool:
    pattern = re.compile(
        r"(?i)(password|passwd|api[_-]?key|client[_-]?secret|access[_-]?token|auth[_-]?token)\s*[=:]\s*['\"]\s*[^'\"]+['\"]"
    )
    return bool(pattern.search(line))


def sanitise_code_line(line: str) -> str:
    line = line.replace("\t", "    ").rstrip("\r\n")
    if code_line_is_secret(line):
        return "// [REDACTED FOR SUBMISSION: secret value removed]"
    if re.search(r"(?i)(?:private deployment value|wifi password|hotspot password|ssid)\s*[:=]", line):
        return "// [REDACTED FOR SUBMISSION: private deployment value removed]"
    return line


def collect_source_lines() -> tuple[list[str], int, list[str]]:
    roots = [
        ROOT / "smart-cattle-backend" / "src" / "main" / "java",
        ROOT / "smart-cattle-frontend" / "src",
    ]
    suffixes = {".java", ".vue", ".js", ".css"}
    files: list[Path] = []
    for source_root in roots:
        files.extend(
            sorted(
                p for p in source_root.rglob("*")
                if p.is_file() and p.suffix.lower() in suffixes
            )
        )
    records: list[str] = []
    raw_line_count = 0
    manifest: list[str] = []
    for path in files:
        relative = path.relative_to(ROOT).as_posix()
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        raw_line_count += len(lines)
        manifest.append(f"{relative}\t{len(lines)} lines")
        records.append(f"// ===== FILE: {relative} =====")
        for number, line in enumerate(lines, start=1):
            records.append(f"{number:04d} | {sanitise_code_line(line)}")
        records.append("")
    return records, raw_line_count, manifest


def wrap_code_records(records: list[str], width: int = 112) -> list[str]:
    output: list[str] = []
    for record in records:
        chunks = textwrap.wrap(
            record,
            width=width,
            replace_whitespace=False,
            drop_whitespace=False,
            break_long_words=True,
            break_on_hyphens=False,
        ) or [""]
        output.extend(chunks)
    return output


def build_source_pdf() -> tuple[Path, int, list[str]]:
    records, raw_line_count, manifest = collect_source_lines()
    wrapped = wrap_code_records(records)
    lines_per_page = 67
    all_pages = [wrapped[i:i + lines_per_page] for i in range(0, len(wrapped), lines_per_page)]
    if len(all_pages) < 60:
        all_pages.extend([[] for _ in range(60 - len(all_pages))])
    selected = all_pages[:30] + all_pages[-30:]
    output = OUT_DIR / "牛舍多模态监测平台V1.0-程序鉴别材料-前后30页.pdf"
    c = canvas.Canvas(str(output), pagesize=A4)
    c.setTitle("牛舍多模态监测平台 V1.0 程序鉴别材料")
    c.setAuthor("牛舍多模态监测平台项目组")
    for index, page_lines in enumerate(selected, start=1):
        part = "连续前30页" if index <= 30 else "连续后30页"
        draw_header_footer(c, index, 60, f"程序鉴别材料｜{part}")
        y = PAGE_H - MARGIN_TOP - 2 * mm
        c.setFillColor(colors.HexColor("#DCECE5"))
        c.rect(MARGIN_X, y - 4 * mm, CONTENT_W, 5 * mm, fill=1, stroke=0)
        c.setFillColor(colors.HexColor("#285C4F"))
        c.setFont(FONT_BOLD, 7.8)
        c.drawString(MARGIN_X + 3 * mm, y - 1.4 * mm, f"程序源代码鉴别材料｜{part}｜提交版本 V1.0")
        y -= 9 * mm
        c.setFillColor(colors.HexColor("#283631"))
        c.setFont(FONT_REG, 6.7)
        for line in page_lines:
            if y < MARGIN_BOTTOM + 9 * mm:
                break
            c.drawString(MARGIN_X, y, line[:150])
            y -= 3.55 * mm
        c.showPage()
    c.save()
    return output, raw_line_count, manifest


def P(title: str, paragraphs: list[str], bullets: list[str] | None = None, image: str | None = None, table: list[list[str]] | None = None) -> dict:
    return {
        "title": title,
        "paragraphs": paragraphs,
        "bullets": bullets or [],
        "image": image,
        "table": table,
    }


def build_document_pages() -> list[dict]:
    pages: list[dict] = []
    pages.append(P("软件设计说明书", [
        "牛舍多模态监测平台 V1.0 面向中小肉牛养殖场，提供环境、行为、视觉事件、声音事件和设备状态的统一管理。本文档用于说明软件的功能边界、系统结构、运行方式和维护方法。",
        "本软件由 Spring Boot 后端和 Vue Web 前端组成，通过 ESP32-S3、牛身节点和 MaixCam 接收现场数据。平台输出风险辅助筛查和异常候选，供养殖人员和兽医复核。",
    ], ["文档版本：V1.0", "申请软件：牛舍多模态监测平台", "材料类型：文档鉴别材料" ]))
    pages.append(P("文档修订与使用范围", [
        "本说明书以当前项目源代码和已实现接口为依据整理。后端源程序位于 smart-cattle-backend，前端源程序位于 smart-cattle-frontend，硬件节点作为外部数据源和控制端接入平台。",
        "文档适用于软件著作权鉴别材料、部署交接、功能演示和内部维护。申请材料中的软件名称、版本号、开发完成日期和权利人信息应与登记申请表保持一致。",
    ], ["版本：V1.0", "源程序统计：后台 Java 与 Web 前端共约 15460 行", "运行形态：浏览器访问 Web 平台" ]))
    pages.append(P("软件权利边界", [
        "本软件保护的是后台服务、Web 页面、数据处理、告警管理、设备命令管理和证据归档的程序表达。ESP32-S3 环境节点固件、牛身节点固件和 MaixCam 程序属于相邻但独立的软件边界。",
        "平台中的人工智能模型、传感器驱动和硬件结构遵循各自的权利和许可规则。软件页面使用模型版本和状态字段展示运行信息，但不会把尚未批准的疾病模型写成已批准能力。",
    ], ["软件名称：牛舍多模态监测平台", "软件分类：应用软件", "开发方式：单独开发" ]))
    pages.append(P("建设目标与适用场景", [
        "系统针对人工巡检不连续、环境异常发现晚、数据分散和处置记录不完整等问题，把牛舍采集、事件分析、告警处理和复盘记录组织为一个可查询的业务链。",
        "平台适用于中小肉牛场、智慧农业示范点、教学实训基地和现场试验环境。系统可以按牛舍和牛只编号组织数据，也可以在没有个体身份绑定时只保留设备级事件。",
    ], ["环境风险监测", "牛只行为趋势", "视觉和声音证据归档", "设备联动与告警复盘" ]))
    pages.append(P("用户使用对象", [
        "养殖管理人员通过总览和环境页面查看牛舍状态、趋势、设备在线情况和告警。巡检人员通过告警详情查看事件时间、证据来源和处置建议，并记录确认结果。",
        "技术维护人员关注串口、网络、设备命令回执、模型状态和审计日志。兽医或临床人员可以使用受保护的健康筛查证据和人工复核记录，但平台结论不替代临床诊断。",
    ], ["管理人员：看状态、看趋势、处理告警", "运维人员：查连接、查日志、查命令", "复核人员：查证据、记录人工判断" ]))
    pages.append(P("总体架构", [
        "系统采用端侧采集、边缘事件、后端服务和 Web 应用的分层结构。环境节点和牛身节点负责传感器采集与本地控制，MaixCam 负责摄像头采集和边缘视觉事件，后端负责接入、存储、筛查和权限管理。",
        "前端通过 HTTP 请求读取业务数据，通过 WebSocket 订阅实时遥测与命令回执。后端将设备数据转换为平台统一事件，保存原始输入、处理结果、模型版本和审计信息。",
    ], ["端侧：ESP32-S3、牛身节点、MaixCam", "服务侧：Spring Boot、MySQL/H2", "应用侧：Vue Web 驾驶舱" ], image="image8.png"))
    pages.append(P("数据流总览", [
        "数据从温湿度、气体、光照、加速度、红外、声音和摄像头进入边缘节点，节点完成采样、校验、特征和事件整理后，通过 USB 串口、UART、HTTP 或网络通道上报。",
        "后端收到数据后进行时间戳、设备、牛只编号和模型状态校验，再写入数据库并通过 WebSocket 推送到浏览器。健康筛查服务使用带质量标记的窗口数据生成风险候选。",
    ], ["采集：原始数据与设备状态", "处理：过滤、窗口、身份和新鲜度", "展示：趋势、证据、告警和命令回执" ]))
    pages.append(P("部署拓扑", [
        "开发部署时，Spring Boot 服务和 Vue 开发服务器可运行在 Windows 计算机上；生产部署可以将后端和数据库放在 Linux 服务器，浏览器通过内网访问。ESP32-S3 与服务器处于同一局域网或通过串口桥接。",
        "设备不应把 localhost 当作服务器地址。设备配置中的后端地址必须使用电脑或服务器在同一网络中的实际 IP，热点切换后需要重新确认网络地址。",
    ], ["后端端口：默认 8080", "数据库：MySQL 或 H2", "设备通信：COM5、COM9、HTTP、WebSocket" ]))
    pages.append(P("运行生命周期", [
        "后端启动时加载配置、创建数据库连接、恢复最近时间范围内的健康筛查观测，并启动串口读取线程。每个串口线程独立重连，端口不存在时进入等待状态，不影响其他端口的数据读取。",
        "前端启动后加载路由和状态仓库，先请求总览快照，再建立 WebSocket。连接断开时页面保留最近状态并显示连接提示，连接恢复后继续接收实时序号。",
    ], ["启动：配置、数据库、串口、WebSocket", "运行：接入、处理、推送、存储", "停止：释放串口、线程和连接资源" ]))
    pages.append(P("环境监测模块", [
        "环境模块用于管理牛舍温度、湿度、光照、气体趋势、烟雾和火焰状态。ESP32-S3 将采样值和执行器状态组成环境遥测，后端保存最新值和趋势记录，前端提供状态卡片和曲线。",
        "MQ 模块属于趋势型传感器，平台保留原始 ADC 值和换算趋势，避免把未预热、未标定的模拟信号直接当成精确浓度。异常阈值由设备规则和后端策略共同约束。",
    ], ["SHT31：温湿度", "GY-302/BH1750：光照", "MQ：气体趋势", "火焰模块：数字告警" ]))
    pages.append(P("环境趋势与数据质量", [
        "环境页面按照时间排序展示最近数据，支持温度、湿度、光照、氨气趋势和烟雾趋势等指标。页面同时显示采集时间、设备状态和数据是否新鲜，方便区分正常低值与传感器未接入。",
        "数据质量处理包括时间戳检查、缺失值保留、异常值标记和设备在线判断。平台不使用缺失值自动填充为正常值，避免断线时页面显示出误导性的稳定曲线。",
    ], ["最新值：当前设备状态", "趋势：一段时间内的变化", "质量：新鲜、缺失或等待数据" ]))
    pages.append(P("设备状态模块", [
        "设备模块展示环境节点、牛身节点、MaixCam 和关联执行器的在线情况、最后通信时间、固件或模型版本及错误状态。设备端口存在但没有帧时，状态应显示等待数据，而不是简单显示在线。",
        "维护人员可以依据设备状态定位供电、串口、WiFi、后端地址或传感器接线问题。平台把设备连接状态与数据新鲜度分开记录，便于审计。",
    ], ["连接状态", "最后接收时间", "设备版本", "错误和重连信息" ]))
    pages.append(P("遥测接入", [
        "后端通过串口读取线程接收 ESP32 JSON 行，也支持设备通过 HTTP 调用 telemetry ingest 接口。接入层根据设备编号和数据类型区分环境遥测、牛只遥测、状态帧、命令回执和声音事件。",
        "每次接入都会保留服务器接收时间，并将设备时间作为辅助字段。对于不能解析或超过行长度限制的数据，系统记录错误状态并继续读取后续帧。",
    ], ["串口：115200 波特率", "网络：HTTP JSON", "实时：WebSocket 推送" ]))
    pages.append(P("命令管理", [
        "设备命令页面可以向环境节点发送风扇开、关或自动模式，以及报警开、关或自动模式。后端先写入命令记录，再尝试通过当前设备链路发送，随后等待设备 ack 或超时结果。",
        "每条命令包含设备、动作、目标状态、创建时间、发送状态和回执信息。页面显示实际执行状态，避免把“已点击按钮”误当成“设备已经动作”。",
    ], ["fan：风扇控制", "fan_auto：恢复自动联动", "alarm：声光报警控制", "command_ack：执行回执" ]))
    pages.append(P("告警闭环", [
        "告警可以由环境阈值、火焰状态、设备错误、视觉事件或健康筛查候选触发。告警记录包含来源、级别、时间、对象、证据和当前处理状态。",
        "处理流程包括发现、确认、处置、解除和复盘。人工操作和设备回执都进入记录，以便后续查看响应时间、处置结果和误报来源。",
    ], ["发现：设备或模型产生候选", "确认：人员检查证据", "处置：下发命令或现场处理", "复盘：记录原因和改进项" ]))
    pages.append(P("Web 总览驾驶舱", [
        "总览页面把牛舍运行信息集中显示，包括环境核心指标、设备在线状态、健康筛查摘要、最新告警、48 小时趋势和系统统计。页面使用统一状态颜色区分正常、观察和告警。",
        "总览数据来自 dashboard 接口，实时变化来自 WebSocket。页面在后端没有返回有效数据时保留明确的空状态，不使用演示假数据覆盖设备缺失。",
    ], ["环境状态", "设备状态", "健康风险摘要", "告警统计", "趋势图表" ], image="image11.png"))
    pages.append(P("健康筛查概览", [
        "健康筛查服务以牛只编号为单位维护个体运动基线，并将当前窗口与基线进行比较。系统会综合行为、活动、体表温度、视觉、声音和人工记录，输出异常候选及证据来源。",
        "筛查结果是健康风险辅助信息，重点是帮助人员确定复核优先级。没有足够数据、模型未批准或证据过期时，系统会降低结论级别或标记为需要补采集。",
    ], ["个体基线", "当前窗口", "证据新鲜度", "模型批准状态", "人工复核提示" ]))
    pages.append(P("个体行为基线", [
        "后端按时间桶累计运动样本、行为状态、活动量和姿态信息。基线达到最小时间和样本条件后，系统才允许计算相对变化，避免用短时噪声形成健康风险。",
        "行为状态来源于牛身节点的姿态和活动特征。当前模型支持行为筛查和姿态筛查，跛行模型仍需要真实三位置 IMU、视频、步态评分和蹄部检查完成发布门禁。",
    ], ["基线保留：最近 7 天配置范围", "当前窗口：默认 30 分钟", "最低覆盖率：由配置和服务规则控制" ]))
    pages.append(P("证据质量门控", [
        "系统把证据质量作为筛查结果的一部分。数据必须有有效时间、有效对象和足够覆盖率，视觉和声音事件还必须处于有效时间窗口内，模型版本必须通过服务端批准。",
        "质量门控防止陈旧图片、无牛只编号的事件、没有真实数据的模型状态或传感器断线引发个体疾病风险。质量不足时，平台展示缺失原因而不是生成默认正常或异常。",
    ], ["身份：真实牛只或设备对象", "时间：事件在有效窗口内", "完整：采样覆盖满足要求", "模型：版本被批准" ]))
    pages.append(P("运动与姿态数据", [
        "牛身节点使用颈部、背部和腿部位置的加速度传感器采集运动变化。平台接收行为状态、姿态、活动量和模型置信度，并在行为页面展示趋势。",
        "多位置数据可以作为后续步态筛查的输入，但平台不会把单次活动下降直接写成跛行或蹄病。发布疾病模型必须通过真实动物分组、外部验证和临床证据门禁。",
    ], ["颈部：低头、抬头和采食活动线索", "背部：姿态和起卧变化线索", "腿部：步态节奏和活动不对称线索" ]))
    pages.append(P("声音事件模块", [
        "平台接收牛身节点上传的声音特征和声音事件，记录 RMS、峰值、频带、信噪比、持续时间、模型状态和证据地址。声音页面可以查看事件时间、标签和当前是否具备进入健康融合的条件。",
        "公开牛声数据只能作为非疾病声学基线。咳嗽、喘鸣和异常鸣叫进入疾病风险前必须有真实牛只、兽医标签、临床证据和批准模型版本。",
    ], ["声音特征：边缘侧提取", "声音证据：服务端归档", "疾病标签：需要审核和发布门禁" ]))
    pages.append(P("视觉事件模块", [
        "MaixCam 在边缘侧运行牛只检测模型，输出检测数量、置信度、边界框和事件时间。视觉事件通过 HTTP 上报，受限 JPEG 可以由后端归档，服务器重新计算图片哈希后再供页面展示。",
        "当前视觉模型的范围是 cow 目标检测。站立、卧倒、跛行、蹄部病灶或口蹄疫相关标签需要单独采集、标注、训练、验证和发布，普通牛只检测结果不能直接升级为疾病结论。",
    ], ["边缘推理：减少全量视频上传", "事件归档：保留元数据和图片哈希", "复核边界：只提供异常候选证据" ], image="image9.png"))
    pages.append(P("健康筛查页面", [
        "健康页面展示当前风险等级、模型版本、数据质量、证据来源和人工复核提示。页面可以区分活动关注、声音证据、视觉证据和多源融合结果，帮助人员按优先级检查牛只。",
        "风险类型包括环境压力、活动变化、呼吸道风险候选和口蹄疫疑似分诊候选等。所有疾病相关输出都标注为筛查、疑似或分诊，并要求兽医、主管部门和有资质实验室完成确认。",
    ], ["风险等级", "证据数量", "来源新鲜度", "复核建议", "临床确认状态" ]))
    pages.append(P("模型管理页面", [
        "模型页面展示视觉、声音、行为、跛行和多模态筛查模型的名称、版本、任务、设备范围、状态和指标。模型状态区分已部署、特征使用、未训练、研究状态和未批准。",
        "后端通过模型批准服务检查上报版本是否在服务端白名单中。模型发布记录保存数据血缘、模型卡、固件或设备哈希、验证摘要和批准人员，撤回后不能重新批准同一版本。",
    ], ["模型版本", "部署状态", "数据血缘", "验证摘要", "批准或撤回记录" ]))
    pages.append(P("证据归档与审计", [
        "平台对视觉图片、声音文件、运动采集和临床复核分别保存证据元数据。每类证据记录来源设备、真实对象、时间、审核状态、哈希和访问角色。",
        "审计记录用于追踪模型发布、临床复核、设备命令和关键配置变化。审计链可以帮助项目复盘数据是否被替换、事件是否被重复使用以及谁完成了人工确认。",
    ], ["原始证据哈希", "审核人员和时间", "访问角色", "操作链路" ]))
    pages.append(P("数据库总体设计", [
        "后端使用 Spring Data JPA 管理业务实体，MySQL 用于持久化部署，H2 用于本地开发和测试。数据库保存环境读数、告警、设备、命令、视觉事件、声音事件、运动采集、健康筛查观测和模型发布记录。",
        "业务数据通过对象编号、设备编号和接收时间关联。健康筛查观测保存用于重启恢复的摘要，不把未经授权的疾病结论写成临床诊断结果。",
    ], ["持久化：MySQL", "本地开发：H2", "业务关联：设备、牛只、时间、事件" ]))
    pages.append(P("核心数据表", [
        "环境数据表保存温度、湿度、光照、气体趋势、烟雾、执行器状态和采集时间。设备与命令表保存在线状态、设备端口、命令动作、发送状态和执行回执。",
        "视觉、声音和运动表保存事件元数据及证据地址。健康筛查观测表保存行为、活动、体表温度、声音和视觉摘要；模型发布表保存版本、来源血缘、批准证据和撤回状态。",
    ], ["environment_reading", "device / device_command", "vision_event / audio_event", "motion_capture", "health_screening_observation", "model_release" ]))
    pages.append(P("接口层概览", [
        "平台接口按环境、设备、事件、健康、模型和遥测分组。环境接口提供最新值和趋势，设备接口提供设备清单和命令，事件接口保存视觉或声音事件，模型接口提供运行版本和发布记录。",
        "接口输入经过字段长度、枚举、时间和身份检查。对于需要临床权限的原始音频、IMU 和视觉证据，接口根据角色密钥限制读取范围。",
    ], ["GET /api/dashboard", "GET /api/environment/latest", "GET /api/environment/trend", "POST /api/devices/command", "GET /api/models" ]))
    pages.append(P("实时通信接口", [
        "设备可以通过 POST /api/telemetry/ingest 上报一帧 JSON 遥测。浏览器通过 WS /ws/telemetry 订阅遥测和命令回执，前端状态仓库按照设备和事件类型更新页面。",
        "WebSocket 消息包含数据类型、设备、时间和序号。前端可以根据序号判断是否发生断帧，后端在连接异常时保持最新快照并等待重连。",
    ], ["HTTP：设备上报", "WebSocket：浏览器订阅", "序号：检测实时数据连续性" ]))
    pages.append(P("后台工程结构", [
        "smart-cattle-backend/src/main/java 下按 controller、service、domain、repository、dto、config 和 websocket 组织代码。Controller 负责接口参数和响应，Service 负责业务规则，Repository 负责数据访问。",
        "TelemetryService 负责串口和网络遥测接入，HealthScreeningService 负责个体筛查，ModelApprovalService 和 ModelReleaseService 负责模型门禁，AuditTrailService 负责审计记录。",
    ], ["controller：API 接口", "service：业务流程", "domain：数据实体", "repository：数据库访问", "websocket：实时推送" ]))
    pages.append(P("前端工程结构", [
        "smart-cattle-frontend/src 采用 Vue 单页应用结构。App.vue 管理整体布局，router/index.js 管理页面路由，stores 目录保存仪表盘和遥测状态，views 目录保存业务页面，components 目录保存图表和状态组件。",
        "前端通过 api/client.js 统一调用后端接口，通过 stores/telemetry.js 订阅 WebSocket。环境、行为、声音、视觉、健康、设备和模型页面共用格式化、状态和告警显示逻辑。",
    ], ["DashboardView：总览", "EnvironmentView：环境", "BehaviorView：行为", "AudioView：声音", "VisionView：视觉", "HealthView：健康", "DevicesView：设备", "ModelsView：模型" ]))
    pages.append(P("配置与隐私安全", [
        "生产配置中的数据库口令、WiFi 密码、MQTT 密钥、API key 和 SSH 密码不写入源程序鉴别 PDF。示例配置只保留变量名和空值或说明性占位符。",
        "部署时使用环境变量或设备安全配置注入密钥。MaixCam 使用 ingest 角色上报视觉事件，临床和管理接口使用独立角色密钥，不能共享一个全权限密钥。",
    ], ["提交材料：删除真实密钥", "生产部署：使用环境变量", "访问控制：按角色分离" ]))
    pages.append(P("错误处理策略", [
        "设备断线时，串口读线程按重连间隔重试，前端显示最后接收时间和等待状态。数据库短时不可用时，后端记录错误并通过启动检查提示配置问题。",
        "事件字段缺失时，接口返回校验错误；图片或声音归档失败时只保存可用元数据并标记证据未归档，不能把未保存的原件显示为已归档。",
    ], ["断线：等待和重连", "数据错误：校验并拒绝", "归档失败：保留失败状态" ]))
    pages.append(P("ESP32-S3 环境节点", [
        "环境节点通过 I2C 读取 SHT31 和 GY-302，使用 ADC 读取 MQ 趋势，使用数字输入读取火焰模块，并通过继电器或 MOSFET 控制风扇、雾化器和报警灯。",
        "节点在本地执行温度、湿度、气体和火焰规则，触发声光提示或向 MaixCam 发起抓拍请求；同时通过 HTTP、MQTT 或串口上报遥测。MQ 模块需要独立供电、分压、预热和标定。",
    ], ["I2C：SHT31、GY-302", "ADC：MQ 趋势", "GPIO：火焰和执行器", "UART：MaixCam 联动" ]))
    pages.append(P("牛身节点", [
        "牛身节点使用三块 ADXL345 采集颈部、背部和腿部运动，使用 INMP441 采集 I2S 声音，使用 MAX30102 采集光学信号，使用 B-1 UART 读取表面温度趋势。",
        "节点把运动、声音、心率血氧状态和体表温度以结构化 JSON 上报。MAX30102 在没有稳定贴合时保持无有效信号状态，B-1 只代表表面温度趋势，不能代替核心体温。",
    ], ["SPI：三块 ADXL345", "I2S：INMP441", "I2C：MAX30102", "UART：B-1" ]))
    pages.append(P("MaixCam 视觉节点", [
        "MaixCam 负责摄像头采集和边缘视觉推理，当前项目部署的 cattle-yolov8-coco-v1 范围为 cow detection only。程序可以保存关键帧、上报视觉状态和通过 UART 通知 ESP32。",
        "MaixCam 通过 HTTP 上报视觉事件时携带受大小限制的 JPEG Base64，后端重新计算 SHA-256 并写入 vision-snapshots。MQTT 只传事件元数据，避免图片撑大消息。",
    ], ["模型文件：.mud 与 .cvimodel", "当前范围：牛只目标检测", "事件范围：异常候选证据" ]))
    pages.append(P("设备通信联动", [
        "MaixCam TX 连接环境节点 RX，MaixCam RX 连接环境节点 TX，双方共地。环境节点可以发 capture_request 请求抓拍，MaixCam 可以发 vision_event 通知现场异常。",
        "设备联动采用 JSON 消息，消息包含类型、原因、设备、时间和可选分数。控制命令和视觉事件进入后端后，页面可以看到对应的接收、回执和归档状态。",
    ], ["UART：事件联动", "HTTP：后台归档", "WiFi：遥测和命令" ]))
    pages.append(P("端边云协同流程", [
        "环境节点先在端侧完成采样和阈值判断，MaixCam 在边缘侧完成关键帧和牛只检测，后端对多源数据做身份、时间、质量和模型状态校验。",
        "平台把低延迟的本地联动和可追溯的云端记录结合起来。风险候选会携带证据来源和复核状态，后续人工记录可以用于规则和模型改进。",
    ], ["端：采样和本地控制", "边：视觉与声音事件", "云：融合、归档、审计", "应用：展示和处置" ], image="image10.png"))
    pages.append(P("三位置运动工作流", [
        "三块 ADXL345 共用 SPI 时钟和数据线，每块使用独立 CS。固件按固定周期读取颈部、背部和腿部数据，并计算活动量、倾角和行为特征。",
        "平台保存位置标识和模型版本，避免把不同传感器位置的数据混淆。后续训练跛行筛查模型时，需要同步视频、标准步态评分、蹄部检查和真实耳标。",
    ], ["共享 SPI：SCK、MOSI、MISO", "独立片选：颈、背、腿", "上报：位置、时间、特征、状态" ]))
    pages.append(P("视觉事件工作流", [
        "摄像头采集图像后由 MaixCam 进行本地推理，程序判断牛只目标和事件条件，保存关键帧并发送事件元数据。后端收到事件后校验真实牛只编号、模型版本和图片哈希。",
        "当事件缺少真实牛只编号或图片归档失败时，平台仍可保留摄像头级事件，但不会把它加入某头牛的疾病风险融合。",
    ], ["采集：摄像头帧", "推理：边缘模型", "上报：事件元数据", "归档：服务器哈希" ], image="image8.png"))
    pages.append(P("报警与执行器工作流", [
        "环境异常或视觉事件可以触发告警候选。后台命令接口向设备发送动作，设备返回 ack，并在后续遥测中报告实际 fan、alarm 和模式状态。",
        "大功率风扇、雾化器和蜂鸣器必须经过独立电源和驱动模块。软件只负责输出控制意图和记录状态，不能把 GPIO 电平本身当作负载已经运行。",
    ], ["告警灯：现场状态", "蜂鸣器：现场提示", "风扇/雾化器：驱动模块控制", "回执：确认实际状态" ]))
    pages.append(P("安装前准备", [
        "安装前准备电脑、数据库、Java 17、Node.js、ESP32-S3 驱动、串口线和同一 WiFi。确认 COM5、COM9 设备对应关系，确认 MaixCam 供电和摄像头连接。",
        "硬件先单个模块上电测试，再接入全部执行器。传感器电压等级、继电器触发电平、MQ 分压和公共地必须在上电前检查。",
    ], ["软件：Java 17、Maven、Node.js", "设备：COM5、COM9、MaixCam", "网络：电脑和设备同一局域网" ]))
    pages.append(P("配置文件", [
        "后端配置文件位于 smart-cattle-backend/src/main/resources。环境变量可以覆盖串口开关、端口名称、数据库连接、API key 和运行 profile。生产环境应使用 mysql、production 配置组合。",
        "前端 API 地址和 WebSocket 地址应指向后端实际地址。设备配置中的 backend_url 不能使用电脑本机 localhost，热点更换后需要重新确认 IP。",
    ], ["后端：application.yml、application-mysql.yml", "前端：Vite API 配置", "设备：WiFi、后端地址、设备编号" ]))
    pages.append(P("启动流程", [
        "先启动 MySQL 或使用 H2 开发 profile，再启动 Spring Boot 后端，确认 8080 端口可访问。随后启动 Vue 前端开发服务器或部署构建产物。",
        "硬件上电后，后端串口线程自动连接 COM5 和 COM9。打开总览页面检查设备状态、最新帧时间、WebSocket 序号和环境数据，最后再进行执行器联动测试。",
    ], ["第一步：数据库", "第二步：后端", "第三步：前端", "第四步：设备", "第五步：页面验收" ]))
    pages.append(P("系统健康检查", [
        "健康检查应覆盖数据库、后端接口、前端构建、串口连接、数据新鲜度和模型状态。端口存在但没有收到数据时，检查结果应为 connected_waiting_data。",
        "现场验收应保存时间、设备、软件版本、最新帧、网络地址、传感器在线状态和告警回执。硬件无数据时不要用演示数据替代真实结果。",
    ], ["接口：/api/health 或总览接口", "数据：最近 7 秒是否有帧", "硬件：COM5、COM9 是否有 JSON", "模型：版本和状态是否匹配" ]))
    pages.append(P("测试清单", [
        "功能测试包括环境读取、趋势查询、设备清单、命令发送、视觉事件接入、声音事件归档、健康筛查、模型查询和 WebSocket 推送。每项测试记录输入、输出、时间和是否需要人工复核。",
        "异常测试包括设备断线、空字段、错误 JSON、过期证据、重复事件、图片过大、数据库不可用和模型未批准。系统应给出可解释的状态，而不是静默失败。",
    ], ["正常链路测试", "断线重连测试", "数据质量测试", "权限测试", "模型门禁测试" ]))
    pages.append(P("数据质量验收", [
        "数据质量验收重点检查时间戳、设备编号、牛只编号、采样频率、连续性、覆盖率、图片或音频哈希和模型版本。对于个体风险筛查，真实牛只编号和时间一致性是必要条件。",
        "验收记录中应区分“没有数据”“数据过期”“传感器异常”“模型未批准”和“人工未复核”。这些状态分别对应不同的现场动作。",
    ], ["完整性：是否缺帧", "新鲜度：是否过期", "身份：是否绑定真实牛只", "证据：是否可回放", "模型：是否通过批准" ]))
    pages.append(P("模型能力边界", [
        "当前 MaixCam 模型只做牛只目标检测，行为模型用于姿态和活动筛查，声音公开数据只作为非疾病基线，跛行和疾病模型需要真实临床数据后才能发布。",
        "平台可以保存研究模型和候选事件，但未批准模型不能进入生产疾病风险融合。口蹄疫、跛行和呼吸道疾病相关结果只能作为疑似分诊或复核候选。",
    ], ["cow detection：已部署范围", "行为/姿态：筛查范围", "声音/跛行/疾病：需要临床发布门禁" ]))
    pages.append(P("证据保留策略", [
        "环境趋势、设备状态和健康筛查摘要按数据库策略保存。视觉图片和声音文件保留来源、哈希、时间、设备、对象和审核状态，原始数据的访问受到角色限制。",
        "关键事件应同时保存业务记录和文件归档状态。归档失败时保留失败原因，后续补传或人工复核不能覆盖原始失败记录。",
    ], ["摘要：便于总览和趋势", "原件：用于人工复核", "哈希：用于完整性核对", "审计：用于过程追踪" ]))
    pages.append(P("备份与恢复", [
        "生产环境应定期备份 MySQL 数据库、vision-snapshots、audio-clips、motion-captures 和模型发布记录。备份文件应记录生成时间、版本和校验值。",
        "恢复演练应验证环境趋势、命令记录、视觉事件、音频血缘、健康筛查摘要和模型发布记录是否能够读取。恢复后重新检查设备上报和 WebSocket 推送。",
    ], ["数据库备份", "证据文件备份", "模型和配置备份", "恢复演练和校验" ]))
    pages.append(P("版本更新与回滚", [
        "更新前记录当前后端、前端、固件和模型版本，导出数据库备份，并保存运行状态。更新后先进行只读接口和总览验收，再开启设备命令和模型融合。",
        "发现数据解析、命令控制或模型状态异常时，回滚到最近一个验证版本，并保留更新失败原因。模型版本回滚不能删除原批准和撤回记录。",
    ], ["先备份", "再更新", "分阶段验证", "保留回滚包", "审计版本变化" ]))
    pages.append(P("现场操作流程", [
        "现场人员先查看总览和设备在线状态，再查看环境趋势和告警证据。确认异常后，按处置建议检查牛舍和牛只，必要时下发风扇或报警命令，并记录实际处置。",
        "涉及健康风险的事件需要拍摄或补采集证据，并由养殖人员或兽医复核。系统记录的是风险候选和处理过程，最终疾病判断按照现场兽医和法定流程执行。",
    ], ["看状态", "看证据", "做处置", "记结果", "做复盘" ]))
    pages.append(P("常见问题处理", [
        "页面没有数据时，先检查后端是否启动、数据库是否连接、COM5/COM9 是否存在以及设备是否持续输出 JSON。页面显示在线但时间不更新时，应优先检查网络和串口数据流。",
        "视觉没有图片时，检查 MaixCam 模型文件、摄像头、HTTP 地址、图片大小限制和服务器归档目录；图片归档成功后页面才显示真实缩略图。",
    ], ["无数据：查端口、线程和时间", "无图片：查模型、网络和归档", "命令不动作：查驱动、电源和回执" ]))
    pages.append(P("接口示例：环境上报", [
        "环境节点可以向 POST /api/environment 提交结构化数据。实际字段根据当前后端 DTO 和固件版本为准，提交时携带 barnId、deviceId、temperature、humidity、lightLux 和执行器状态。",
        "平台同时保留原始值和经过规则处理的状态。没有接入 MQ 时，氨气和烟雾字段可能为空，页面应显示传感器未接入或等待数据。",
    ], ["接口：POST /api/environment", "对象：barn_01 / env_01", "字段：温度、湿度、光照、气体、执行器" ]))
    pages.append(P("接口示例：设备命令", [
        "设备命令接口用于写入控制命令，例如 fan、fan_auto 和 alarm。后端会保存命令历史，并把发送状态和设备回执写回系统。",
        "生产环境开启 API key 后，命令操作需要 operator 或 admin 角色。前端按钮只表示发起请求，页面必须等待 command_ack 或后续遥测确认实际状态。",
    ], ["请求：deviceId、action、enabled", "返回：sent、failed 或 unsupported", "确认：command_ack 和后续遥测" ]))
    pages.append(P("接口示例：视觉事件", [
        "MaixCam 通过 POST /api/events/vision 上报视觉事件。请求应包含 cameraId、barnId、targetId、eventType、score、recordedAt、modelVersion 和 snapshot 信息。targetId 应为真实牛只编号，不能把视觉追踪编号当作牛只身份。",
        "视觉事件可以归档为摄像头证据，但只有经过真实身份、模型状态和证据新鲜度校验后，才可能参与个体健康筛查。",
    ], ["当前模型：cow detection only", "图片：服务器重新计算哈希", "疾病相关：仅候选和分诊" ]))
    pages.append(P("传感器与接口映射", [
        "环境节点使用 I2C GPIO8/GPIO9 连接 SHT31 和 GY-302；MQ-137 和 MQ-135 使用 ADC；火焰使用数字输入；风扇、雾化器和报警灯使用驱动输出。",
        "牛身节点三块 ADXL345 使用 SPI GPIO40/41/42 和独立 CS；INMP441 使用 GPIO5/6/7；MAX30102 使用 GPIO8/9；B-1 使用 38400 UART GPIO18/17。",
    ], ["环境：COM9", "牛身：COM5", "摄像头：MaixCam USB/UART/WiFi", "所有模块：按电压和公共地要求接线" ]))
    pages.append(P("文件清单", [
        "本软件主要源程序包括 smart-cattle-backend/src/main/java 下的 Java 后端，以及 smart-cattle-frontend/src 下的 Vue、JavaScript 和 CSS 前端。配置和数据库脚本用于部署支撑。",
        "项目中硬件代码、MaixCam 代码、模型文件、测试数据和疾病生产落地资料作为关联项目材料保存，不混入本项 Web 平台源程序 PDF。",
    ], ["后端：smart-cattle-backend", "前端：smart-cattle-frontend", "接口文档：API.md", "硬件：硬件代码/" ]))
    pages.append(P("提交材料核对", [
        "程序鉴别 PDF 应使用本软件源程序的前 30 页和后 30 页；文档鉴别 PDF 应使用本软件设计说明书或用户手册的前 30 页和后 30 页。两个 PDF 都应保留软件名称和 V1.0 版本号。",
        "申请表、程序页眉、文档封面、文档页眉和上传文件名称保持一致。著作权人、开发完成日期、发表状态、单独开发关系和合作协议情况必须由申请人最终核对。",
    ], ["名称一致", "版本一致", "页数一致", "权属一致", "内容不含真实密钥" ]))
    pages.append(P("说明书结束页", [
        "牛舍多模态监测平台 V1.0 通过环境数据、牛只行为、视觉事件、声音事件和设备控制形成统一的数字化管理链路。平台承担数据接入、风险辅助筛查、告警处置和证据追溯功能。",
        "本说明书与程序鉴别材料共同用于软件著作权登记。提交前请再次核对软件名称、版本、权利人、开发方式、完成日期、发表状态和上传文件。",
    ], ["软件名称：牛舍多模态监测平台", "版本号：V1.0", "材料：软件设计说明书", "结束" ]))
    assert len(pages) == 60, len(pages)
    return pages


def build_document_pdf() -> Path:
    pages = build_document_pages()
    output = OUT_DIR / "牛舍多模态监测平台V1.0-文档鉴别材料-软件设计说明书.pdf"
    c = canvas.Canvas(str(output), pagesize=A4)
    c.setTitle("牛舍多模态监测平台 V1.0 软件设计说明书")
    c.setAuthor("牛舍多模态监测平台项目组")
    image_dir = ROOT / "review_media"
    for page_no, page in enumerate(pages, start=1):
        draw_header_footer(c, page_no, 60, "软件设计说明书鉴别材料")
        y = PAGE_H - MARGIN_TOP - 2 * mm
        y = draw_para(c, f"{page_no:02d}｜{page['title']}", TITLE_STYLE, MARGIN_X, y, CONTENT_W)
        y -= 2 * mm
        if page.get("image"):
            image_path = image_dir / page["image"]
            y = draw_image(c, image_path, MARGIN_X, y, CONTENT_W, 78 * mm)
        if page.get("table"):
            table_data = [[Paragraph(esc(cell), SMALL_STYLE) for cell in row] for row in page["table"]]
            table = Table(table_data, colWidths=[CONTENT_W * 0.32, CONTENT_W * 0.68])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#DDECE5")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#B9CEC5")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 5),
                ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
            ]))
            _, h = table.wrap(CONTENT_W, PAGE_H)
            table.drawOn(c, MARGIN_X, y - h)
            y -= h + 6
        for paragraph in page["paragraphs"]:
            y = draw_para(c, paragraph, BODY_STYLE, MARGIN_X, y, CONTENT_W)
            y -= 1.5 * mm
        if page["bullets"]:
            for number, bullet in enumerate(page["bullets"], start=1):
                y = draw_rich_para(c, f"<b>{number}.</b> {esc(bullet)}", BODY_STYLE, MARGIN_X + 4 * mm, y, CONTENT_W - 4 * mm)
                y -= 1 * mm
        c.showPage()
    c.save()
    return output


def main() -> None:
    source_pdf, line_count, manifest = build_source_pdf()
    document_pdf = build_document_pdf()
    (OUT_DIR / "程序鉴别材料-源程序文件清单.txt").write_text(
        "牛舍多模态监测平台 V1.0\n"
        f"源程序总行数（后台 Java + Web 前端）：{line_count}\n"
        "以下为程序鉴别 PDF 纳入的项目源文件：\n"
        + "\n".join(manifest)
        + "\n\n已剔除：node_modules、target、编译产物、测试代码、第三方依赖和真实密钥。\n",
        encoding="utf-8",
    )
    (OUT_DIR / "生成说明.md").write_text(
        "# 软著材料生成说明\n\n"
        "本目录包含牛舍多模态监测平台 V1.0 的程序鉴别材料和文档鉴别材料。\n\n"
        f"- 程序源代码行数：{line_count}\n"
        "- 程序 PDF：前 30 页和后 30 页，共 60 页\n"
        "- 文档 PDF：软件设计说明书，共 60 页\n"
        "- 代码范围：smart-cattle-backend/src/main/java、smart-cattle-frontend/src\n"
        "- 提交前请核对著作权人、开发日期、发表状态和权属证明。\n",
        encoding="utf-8",
    )
    print(f"SOURCE_PDF={source_pdf}")
    print(f"DOCUMENT_PDF={document_pdf}")
    print(f"SOURCE_LINES={line_count}")


if __name__ == "__main__":
    main()
