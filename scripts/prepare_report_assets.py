from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps


ASSET_DIR = Path("D:/table/shumuzengxiao/report_assets")
ASSET_DIR.mkdir(parents=True, exist_ok=True)

HM_SOURCE = [
    Path("C:/Users/q4984/AppData/Local/Temp/codex-clipboard-ede4fc85-29cf-4ade-a5ba-2b6ea84969a8.png"),
    Path("C:/Users/q4984/AppData/Local/Temp/codex-clipboard-92f1bb9e-e973-4e96-b5d3-d0009083dfa2.png"),
    Path("C:/Users/q4984/AppData/Local/Temp/codex-clipboard-99858131-b60d-4b22-bdfb-869cd651699a.png"),
    Path("C:/Users/q4984/AppData/Local/Temp/codex-clipboard-c711fec2-a45e-4f30-b940-9fa01879e889.png"),
    Path("C:/Users/q4984/AppData/Local/Temp/codex-clipboard-7040d9e4-7276-4e03-81b7-81aad44f35da.png"),
]

HM_LABELS = ["总览", "AI 识牛", "识别记录", "后台管理", "设备链路"]

FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
    "C:/Windows/Fonts/simsun.ttc",
]


def font(size: int, bold: bool = False):
    candidates = ["C:/Windows/Fonts/msyhbd.ttc"] + FONT_CANDIDATES if bold else FONT_CANDIDATES
    for p in candidates:
        if Path(p).exists():
            return ImageFont.truetype(p, size)
    return ImageFont.load_default()


def copy_hm_screens():
    out = []
    for idx, src in enumerate(HM_SOURCE, 1):
        im = Image.open(src).convert("RGB")
        path = ASSET_DIR / f"hm-app-{idx}.png"
        im.save(path)
        out.append(path)
    return out


def make_hm_contact_sheet(paths):
    thumbs = []
    target_h = 620
    for path in paths:
        im = Image.open(path).convert("RGB")
        ratio = target_h / im.height
        im = im.resize((int(im.width * ratio), target_h), Image.LANCZOS)
        thumbs.append(im)

    gap = 30
    top = 92
    bottom = 34
    label_h = 42
    width = sum(t.width for t in thumbs) + gap * (len(thumbs) + 1)
    height = top + target_h + label_h + bottom
    sheet = Image.new("RGB", (width, height), "#f6f8f4")
    draw = ImageDraw.Draw(sheet)
    draw.text((gap, 24), "鸿蒙 APP 核心界面", fill="#102216", font=font(34, True))
    draw.text((gap, 62), "移动端巡检、AI 识牛、记录归档、远程控制与设备状态", fill="#506052", font=font(18))

    x = gap
    for im, label in zip(thumbs, HM_LABELS):
        sheet.paste(im, (x, top))
        bbox = draw.textbbox((0, 0), label, font=font(18, True))
        draw.text((x + (im.width - (bbox[2] - bbox[0])) / 2, top + target_h + 12), label, fill="#102216", font=font(18, True))
        x += im.width + gap
    out = ASSET_DIR / "hm-app-contact-sheet.png"
    sheet.save(out, quality=95)
    return out


def rounded_rect(draw, xy, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw, box, text, fill, font_obj, max_width=None):
    lines = []
    current = ""
    for ch in text:
        test = current + ch
        if max_width and draw.textbbox((0, 0), test, font=font_obj)[2] > max_width and current:
            lines.append(current)
            current = ch
        else:
            current = test
    if current:
        lines.append(current)
    line_h = font_obj.size + 8
    total_h = len(lines) * line_h
    x1, y1, x2, y2 = box
    y = y1 + (y2 - y1 - total_h) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y), line, fill=fill, font=font_obj)
        y += line_h


def make_architecture_diagram():
    w, h = 1800, 1080
    im = Image.new("RGB", (w, h), "#f8faf7")
    draw = ImageDraw.Draw(im)
    title_font = font(46, True)
    sub_font = font(22)
    head_font = font(27, True)
    text_font = font(22)
    small_font = font(18)

    draw.text((70, 42), "数牧增效端边云服协同总体架构", fill="#0f2a19", font=title_font)
    draw.text((70, 98), "ESP32-S3 环境控制 + MaixCam 边缘视觉 + Spring Boot 云平台 + Web/鸿蒙/微信服务端协同", fill="#56645a", font=sub_font)

    columns = [
        ("端：牛舍采集与执行", 70, 175, 380, "#e8f6ec"),
        ("边：本地 AI 与规则", 500, 175, 380, "#edf5ff"),
        ("云：数据与融合服务", 930, 175, 380, "#fff5df"),
        ("服：多端应用与处置", 1360, 175, 370, "#f4eeff"),
    ]
    for title, x, y, cw, color in columns:
        rounded_rect(draw, (x, y, x + cw, 940), 24, color, "#b8c5ba", 2)
        draw.text((x + 26, y + 24), title, fill="#102216", font=head_font)

    boxes = [
        (100, 260, 420, 345, "环境传感器\n温湿度 / 氨气 / 光照 / 烟雾", "#ffffff"),
        (100, 400, 420, 485, "执行器\n风扇 / 雾化 / 声光报警 / 继电器", "#ffffff"),
        (100, 540, 420, 625, "本地显示与按键\nOLED / 状态提示 / 现场调试", "#ffffff"),
        (530, 260, 850, 345, "ESP32-S3 主控\n采集滤波 / 阈值规则 / MQTT", "#ffffff"),
        (530, 400, 850, 485, "MaixCam 视觉节点\nYOLO 推理 / 跟踪 / 截图留证", "#ffffff"),
        (530, 540, 850, 625, "声音识别节点\nI2S 麦克风 / VAD / Log-Mel 特征", "#ffffff"),
        (960, 260, 1280, 345, "Spring Boot API\n设备 / 环境 / 事件 / 告警接口", "#ffffff"),
        (960, 400, 1280, 485, "MySQL / H2 数据层\n趋势数据 / 事件证据 / 命令历史", "#ffffff"),
        (960, 540, 1280, 625, "多模态融合评分\n环境 + 视觉 + 声音 + 历史趋势", "#ffffff"),
        (1390, 260, 1700, 345, "Vue Web 驾驶舱\n3D 态势 / 趋势 / 设备控制", "#ffffff"),
        (1390, 400, 1700, 485, "鸿蒙 APP\n拍照识别 / 记录归档 / 远程控制", "#ffffff"),
        (1390, 540, 1700, 625, "微信小程序\n移动巡检 / 告警查看 / 轻量管理", "#ffffff"),
    ]
    for x1, y1, x2, y2, label, color in boxes:
        rounded_rect(draw, (x1, y1, x2, y2), 16, color, "#9eb2a4", 2)
        center_text(draw, (x1 + 12, y1 + 8, x2 - 12, y2 - 8), label, "#173520", text_font, x2 - x1 - 30)

    def arrow(x1, y1, x2, y2, text, label_y_offset=0):
        draw.line((x1, y1, x2, y2), fill="#2f6f46", width=5)
        # arrow head
        import math
        ang = math.atan2(y2-y1, x2-x1)
        size = 16
        pts = [
            (x2, y2),
            (x2 - size * math.cos(ang - 0.45), y2 - size * math.sin(ang - 0.45)),
            (x2 - size * math.cos(ang + 0.45), y2 - size * math.sin(ang + 0.45)),
        ]
        draw.polygon(pts, fill="#2f6f46")
        mx, my = (x1+x2)/2, (y1+y2)/2 + label_y_offset
        rounded_rect(draw, (mx - 88, my - 20, mx + 88, my + 20), 12, "#f8faf7", "#b7c8bd", 1)
        center_text(draw, (mx - 80, my - 16, mx + 80, my + 16), text, "#264632", small_font, 150)

    arrow(420, 375, 530, 375, "GPIO / I2C / ADC")
    arrow(850, 375, 960, 375, "MQTT / HTTP")
    arrow(1280, 375, 1390, 375, "REST / 推送")
    arrow(690, 345, 690, 400, "UART JSON", label_y_offset=0)
    arrow(690, 485, 690, 540, "事件触发", label_y_offset=0)

    rounded_rect(draw, (120, 735, 1660, 860), 22, "#102216", "#102216", 1)
    draw.text((155, 760), "闭环链路", fill="#72e38b", font=head_font)
    draw.text((155, 810), "采集感知 → 本地判断 → 事件上报 → 融合评分 → 多端告警 → 控制命令 → 现场执行 → 数据回流优化", fill="#f3f6ed", font=font(28, True))

    out = ASSET_DIR / "architecture-diagram.png"
    im.save(out, quality=95)
    return out


def make_dataflow_diagram():
    w, h = 1800, 980
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 44), "多模态健康风险识别数据流", fill="#102216", font=font(44, True))
    draw.text((70, 100), "环境趋势、声音事件、视觉行为与历史数据共同形成可复核的风险证据链", fill="#5b655d", font=font(22))

    stages = [
        ("1 现场采集", "温湿度、氨气、烟雾、光照\n咳嗽、喘鸣、异常叫声\n牛体、姿态、眼鼻皮肤截图", 80, 210, "#e8f6ec"),
        ("2 边缘预处理", "ESP32-S3 滤波与阈值规则\nMaixCam YOLO 推理与跟踪\nVAD + Log-Mel/MFCC 特征提取", 500, 210, "#eef6ff"),
        ("3 后端融合", "事件入库与时间对齐\n规则引擎 / Logistic / XGBoost\n同栏位、同牛只历史趋势校准", 920, 210, "#fff4df"),
        ("4 应用处置", "风险等级：正常 / 关注 / 告警 / 复核\n证据链：截图、音频、环境曲线\n风扇、雾化、报警、抓拍指令", 1340, 210, "#f2edff"),
    ]
    for title, body, x, y, color in stages:
        rounded_rect(draw, (x, y, x + 350, y + 390), 26, color, "#afbcaf", 2)
        draw.text((x + 28, y + 28), title, fill="#102216", font=font(30, True))
        draw.multiline_text((x + 28, y + 95), body, fill="#263c2f", font=font(24), spacing=15)

    for x in [430, 850, 1270]:
        draw.line((x, 405, x + 60, 405), fill="#2f6f46", width=6)
        draw.polygon([(x + 60, 405), (x + 38, 391), (x + 38, 419)], fill="#2f6f46")

    rounded_rect(draw, (180, 690, 1620, 820), 20, "#112619", "#112619", 1)
    draw.text((220, 720), "输出结果", fill="#72e38b", font=font(28, True))
    draw.text((220, 765), "系统不替代兽医诊断，而是给出“优先复核对象 + 异常证据 + 处置建议”，降低人工巡检漏检率。", fill="#f5f7ef", font=font(27, True))

    out = ASSET_DIR / "multimodal-dataflow.png"
    im.save(out, quality=95)
    return out


def make_website_contact_sheet():
    items = [
        ("项目首页", ASSET_DIR / "web-intro.png"),
        ("驾驶舱", ASSET_DIR / "web-dashboard.png"),
        ("健康风险", ASSET_DIR / "web-health.png"),
        ("设备控制", ASSET_DIR / "web-devices.png"),
    ]
    thumbs = []
    for label, path in items:
        im = Image.open(path).convert("RGB")
        im = ImageOps.fit(im, (760, 420), method=Image.LANCZOS, centering=(0.5, 0.08))
        thumbs.append((label, im))
    w, h = 1660, 1030
    sheet = Image.new("RGB", (w, h), "#f7faf6")
    draw = ImageDraw.Draw(sheet)
    draw.text((60, 36), "Web 平台运行界面", fill="#102216", font=font(38, True))
    draw.text((60, 82), "Vue3 + Three.js 驾驶舱、健康风险、设备控制与模型管理", fill="#56645a", font=font(20))
    positions = [(60, 145), (840, 145), (60, 610), (840, 610)]
    for (label, im), (x, y) in zip(thumbs, positions):
        rounded_rect(draw, (x - 8, y - 8, x + im.width + 8, y + im.height + 44), 18, "#ffffff", "#d4ded4", 2)
        sheet.paste(im, (x, y))
        draw.text((x + 8, y + im.height + 12), label, fill="#102216", font=font(20, True))
    out = ASSET_DIR / "web-contact-sheet.png"
    sheet.save(out, quality=95)
    return out


def make_node_card(draw, xy, title, body, fill="#ffffff", border="#9eb2a4"):
    x1, y1, x2, y2 = xy
    rounded_rect(draw, xy, 18, fill, border, 2)
    draw.text((x1 + 22, y1 + 18), title, fill="#102216", font=font(26, True))
    draw.multiline_text((x1 + 22, y1 + 62), body, fill="#2b4031", font=font(21), spacing=10)


def make_hardware_topology():
    w, h = 1800, 1080
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "现场硬件拓扑与接口分配", fill="#102216", font=font(44, True))
    draw.text((70, 96), "以 ESP32-S3 为主控网关，MaixCam 独立执行视觉推理，执行器侧通过继电器/MOSFET 隔离控制", fill="#5a665e", font=font(22))

    make_node_card(draw, (690, 220, 1110, 400), "ESP32-S3 环境控制箱", "WiFi / MQTT\nI2C / ADC / GPIO / PWM\n本地规则与执行器联动", "#e8f6ec")
    nodes = [
        ((80, 210, 430, 330), "SHT31 温湿度", "I2C\n高温高湿告警\n风扇/雾化联动", "#ffffff"),
        ((80, 380, 430, 500), "MQ-137 氨气", "ADC\n趋势告警\n预留工业 NH3/RS485", "#ffffff"),
        ((80, 550, 430, 670), "烟雾/火焰", "ADC/GPIO\n火情快速检测\n声光报警触发", "#ffffff"),
        ((80, 720, 430, 840), "BH1750 光照", "I2C\n夜间补光判断\n视觉曝光参考", "#ffffff"),
        ((1370, 210, 1720, 330), "风扇/雾化", "MOSFET / 继电器\n通风降温\n湿度调节", "#ffffff"),
        ((1370, 380, 1720, 500), "声光报警", "GPIO / 继电器\n现场提醒\n人工复核触发", "#ffffff"),
        ((1370, 550, 1720, 670), "OLED 本地屏", "I2C\n联网状态\n关键读数与告警", "#ffffff"),
        ((1370, 720, 1720, 840), "电源系统", "12V/24V 输入\n5V/3A + 3.3V/1A\n保险丝/TVS/共地", "#ffffff"),
    ]
    for xy, title, body, fill in nodes:
        make_node_card(draw, xy, title, body, fill)

    make_node_card(draw, (690, 580, 1110, 760), "MaixCam 视觉 AI 节点", "摄像头采集\nYOLO 推理与跟踪\n截图/事件 JSON/本地日志", "#eef6ff")
    make_node_card(draw, (690, 815, 1110, 955), "INMP441 声音节点", "I2S 采样\nVAD 过滤\nLog-Mel/MFCC 特征", "#fff6df")

    def link(x1, y1, x2, y2):
        draw.line((x1, y1, x2, y2), fill="#2f6f46", width=4)
        import math
        ang = math.atan2(y2-y1, x2-x1)
        size = 14
        draw.polygon([
            (x2, y2),
            (x2 - size * math.cos(ang - 0.45), y2 - size * math.sin(ang - 0.45)),
            (x2 - size * math.cos(ang + 0.45), y2 - size * math.sin(ang + 0.45)),
        ], fill="#2f6f46")

    for y in [270, 440, 610, 780]:
        link(430, y, 690, 310)
    for y in [270, 440, 610, 780]:
        link(1110, 310, 1370, y)
    link(870, 400, 870, 580)
    link(930, 400, 930, 815)
    rounded_rect(draw, (710, 475, 1070, 535), 14, "#ffffff", "#b7c8bd", 1)
    center_text(draw, (720, 482, 1060, 528), "下行控制：UART JSON / GPIO / PWM / I2C", "#264632", font(18), 330)
    out = ASSET_DIR / "hardware-topology.png"
    im.save(out, quality=95)
    return out


def make_mqtt_topic_map():
    w, h = 1800, 980
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "MQTT Topic 与载荷设计", fill="#102216", font=font(44, True))
    draw.text((70, 96), "现场节点只上传结构化事件和关键摘要，后端完成解析、入库和风险融合", fill="#5a665e", font=font(22))
    rows = [
        ("cattle/barn_01/env_01/telemetry", "ESP32-S3 → Broker", "温湿度、氨气、烟雾、光照、风扇/雾化状态"),
        ("cattle/barn_01/env_01/alert", "ESP32-S3 → Broker", "高温、氨气偏高、烟雾/火情、执行器联动结果"),
        ("cattle/barn_01/cam_01/vision/event", "MaixCam → Broker", "事件类型、置信度、targetId、截图路径、模型版本"),
        ("cattle/barn_01/mic_01/audio/event", "声音节点 → Broker", "咳嗽/喘鸣/异常叫声、时长、SNR、音频片段路径"),
        ("cattle/barn_01/relay_01/command", "平台 → ESP32-S3", "fan、atomizer、alarm、snapshot 等控制命令"),
        ("cattle/barn_01/device/heartbeat", "各节点 → Broker", "在线状态、电量、信号强度、最后心跳时间"),
    ]
    x, y = 80, 190
    col_w = [650, 330, 640]
    headers = ["Topic", "方向", "载荷摘要"]
    for i, htxt in enumerate(headers):
        rounded_rect(draw, (x + sum(col_w[:i]), y, x + sum(col_w[:i+1])-10, y+70), 12, "#102216", "#102216", 1)
        center_text(draw, (x + sum(col_w[:i])+8, y+8, x + sum(col_w[:i+1])-18, y+62), htxt, "#f6fff7", font(24, True), col_w[i]-30)
    y += 82
    for idx, row in enumerate(rows):
        fill = "#ffffff" if idx % 2 == 0 else "#f0f6ef"
        row_h = 98
        for i, value in enumerate(row):
            rounded_rect(draw, (x + sum(col_w[:i]), y, x + sum(col_w[:i+1])-10, y+row_h), 12, fill, "#bfd0c3", 1)
            center_text(draw, (x + sum(col_w[:i])+18, y+8, x + sum(col_w[:i+1])-28, y+row_h-8), value, "#173520", font(20, i == 0), col_w[i]-44)
        y += row_h + 10
    out = ASSET_DIR / "mqtt-topic-map.png"
    im.save(out, quality=95)
    return out


def make_database_er():
    w, h = 1800, 1080
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "后端数据库实体关系", fill="#102216", font=font(44, True))
    draw.text((70, 96), "围绕 barnId、deviceId、targetId 和时间戳组织环境、设备、事件、风险与命令记录", fill="#5a665e", font=font(22))
    cards = [
        ((80, 210, 470, 390), "EnvironmentReading", "barnId / deviceId\n温湿度 / 氨气 / 烟雾\n风扇 / 雾化状态\nrecordedAt"),
        ((80, 500, 470, 680), "Device", "deviceId\n名称 / 类型 / 状态\n电量 / 信号强度\nlastSeen"),
        ((705, 170, 1095, 350), "VisionEvent", "cameraId / barnId / targetId\n事件类型 / 级别 / 置信度\n截图路径 / 证据描述\nrecordedAt"),
        ((705, 410, 1095, 590), "AudioEvent", "deviceId / barnId\n事件类型 / 置信度\n时长 / SNR / 音频路径\nrecordedAt"),
        ((705, 650, 1095, 830), "HealthRisk", "barnId / targetId\n风险类型 / 等级 / 分数\n证据链 / 建议 / 状态\nrecordedAt"),
        ((1330, 260, 1720, 440), "AlertRecord", "barnId\n标题 / 级别 / 来源\n消息 / 状态\ncreatedAt"),
        ((1330, 560, 1720, 740), "ControlCommandRecord", "deviceId\n动作 / 目标状态\n队列状态\nqueuedAt"),
    ]
    for xy, title, body in cards:
        make_node_card(draw, xy, title, body, "#ffffff")
    rounded_rect(draw, (250, 880, 1550, 985), 18, "#102216", "#102216", 1)
    draw.text((285, 900), "核心关联字段", fill="#72e38b", font=font(24, True))
    draw.text((285, 940), "barnId 串联牛舍空间，deviceId 串联采集与控制设备，targetId 串联单牛/目标轨迹，时间戳用于事件对齐和趋势回溯。", fill="#f6fff7", font=font(23, True))
    # light relation lines routed around text blocks
    for line in [
        (470, 300, 705, 260), (470, 590, 705, 500), (1095, 260, 1330, 350),
        (1095, 500, 1330, 350), (1095, 740, 1330, 350), (470, 590, 1330, 650),
        (900, 350, 900, 410), (900, 590, 900, 650)
    ]:
        draw.line(line, fill="#c4d1c8", width=3)
    out = ASSET_DIR / "database-er.png"
    im.save(out, quality=95)
    return out


def make_api_map():
    w, h = 1800, 980
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "后端 REST API 功能地图", fill="#102216", font=font(44, True))
    draw.text((70, 96), "接口按总览、环境、设备、事件和模型分组，便于 Web/移动端与网关统一接入", fill="#5a665e", font=font(22))
    groups = [
        ("总览", "/api/dashboard\n最新环境 / 趋势 / 设备\n事件 / 风险 / 告警 / 指标", 90, 205, "#e8f6ec"),
        ("环境", "/api/environment/latest\n/api/environment/trend\nPOST /api/environment", 470, 205, "#eef6ff"),
        ("设备", "/api/devices\nPOST /api/devices/command\n/api/devices/commands", 850, 205, "#fff6df"),
        ("事件", "/api/events/vision\n/api/events/audio\n/api/events/health-risks\n/api/events/alerts", 1230, 205, "#f2edff"),
        ("模型", "/api/models\n模型版本 / 任务\nPrecision / Recall / 部署设备", 660, 600, "#ffffff"),
    ]
    for title, body, x, y, fill in groups:
        make_node_card(draw, (x, y, x+330, y+250), title, body, fill)
    draw.line((255,455,825,600), fill="#2f6f46", width=4)
    draw.line((635,455,825,600), fill="#2f6f46", width=4)
    draw.line((1015,455,825,600), fill="#2f6f46", width=4)
    draw.line((1395,455,825,600), fill="#2f6f46", width=4)
    rounded_rect(draw, (520, 860, 1280, 925), 18, "#102216", "#102216", 1)
    center_text(draw, (540, 870, 1260, 915), "统一返回 JSON，前端通过 Axios/Pinia 聚合到驾驶舱状态树", "#f6fff7", font(24, True), 720)
    out = ASSET_DIR / "api-map.png"
    im.save(out, quality=95)
    return out


def make_ai_training_pipeline():
    w, h = 1800, 1050
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "AI 训练、部署与回流优化流程", fill="#102216", font=font(44, True))
    draw.text((70, 96), "以开源轻量模型为基线，现场误报/漏报样本持续回流，逐步适配具体牛舍光照、遮挡与噪声", fill="#5a665e", font=font(22))
    steps = [
        ("1 数据采集", "环境曲线\n视觉截图/短视频\n声音片段\n人工复核结果"),
        ("2 标注清洗", "牛体框/姿态\n眼鼻皮肤区域\n咳嗽/喘鸣标签\n异常样本去重"),
        ("3 基线训练", "YOLO Nano\nMobileNet\n轻量 CNN\n规则融合模型"),
        ("4 量化部署", "INT8/FP16\n输入尺寸裁剪\nMaixCam 可加载模型\n后端模型版本登记"),
        ("5 现场验证", "FPS / 延迟\nPrecision / Recall\n误报/漏报记录\n风险阈值校准"),
        ("6 样本回流", "人工复核结论\n新场景样本\n夜间/遮挡/噪声\n版本迭代"),
    ]
    x0, y0 = 80, 250
    box_w, box_h, gap = 260, 240, 30
    for i, (title, body) in enumerate(steps):
        x = x0 + i * (box_w + gap)
        fill = ["#e8f6ec", "#eef6ff", "#fff6df", "#f2edff", "#ffffff", "#e8f6ec"][i]
        make_node_card(draw, (x, y0, x+box_w, y0+box_h), title, body, fill)
        if i < len(steps)-1:
            ax = x + box_w
            ay = y0 + box_h//2
            draw.line((ax, ay, ax+gap, ay), fill="#2f6f46", width=5)
            draw.polygon([(ax+gap, ay), (ax+gap-18, ay-12), (ax+gap-18, ay+12)], fill="#2f6f46")
    rounded_rect(draw, (210, 680, 1590, 830), 24, "#102216", "#102216", 1)
    draw.text((250, 715), "训练边界", fill="#72e38b", font=font(28, True))
    draw.text((250, 760), "系统输出“风险复核优先级”和“证据链”，不替代兽医诊断；模型指标必须结合现场人工复核持续校准。", fill="#f6fff7", font=font(26, True))
    out = ASSET_DIR / "ai-training-pipeline.png"
    im.save(out, quality=95)
    return out


def make_alarm_closed_loop():
    w, h = 1800, 980
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "异常告警与现场处置闭环", fill="#102216", font=font(44, True))
    draw.text((70, 96), "系统价值不止于展示数据，而是把异常发现、证据留存、命令下发和人工复核串成闭环", fill="#5a665e", font=font(22))
    points = [
        ("环境异常", "氨气偏高\n高温高湿\n烟雾/火情", 220, 240),
        ("边缘联动", "开启风扇\n触发雾化\n声光提醒", 620, 240),
        ("证据生成", "MaixCam 抓拍\n声音事件\n环境曲线", 1020, 240),
        ("平台融合", "风险等级\n证据链\n处置建议", 1420, 240),
        ("人工复核", "巡检记录\n兽医判断\n样本回流", 820, 640),
    ]
    for title, body, x, y in points:
        make_node_card(draw, (x-150, y-85, x+150, y+85), title, body, "#ffffff")
    def arr(a,b):
        x1,y1=a; x2,y2=b
        draw.line((x1,y1,x2,y2), fill="#2f6f46", width=5)
        import math
        ang=math.atan2(y2-y1,x2-x1); size=16
        draw.polygon([(x2,y2),(x2-size*math.cos(ang-.45),y2-size*math.sin(ang-.45)),(x2-size*math.cos(ang+.45),y2-size*math.sin(ang+.45))], fill="#2f6f46")
    arr((370,240),(470,240)); arr((770,240),(870,240)); arr((1170,240),(1270,240))
    arr((1420,325),(950,560)); arr((820,555),(290,325))
    rounded_rect(draw, (430, 850, 1370, 915), 18, "#102216", "#102216", 1)
    center_text(draw, (450, 860, 1350, 905), "闭环后的复核结果进入训练样本池，持续降低误报和漏报", "#f6fff7", font(24, True), 880)
    out = ASSET_DIR / "alarm-closed-loop.png"
    im.save(out, quality=95)
    return out


def make_deployment_layout():
    w, h = 1800, 1050
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "牛舍现场部署点位建议", fill="#102216", font=font(44, True))
    draw.text((70, 96), "传感器位置需要兼顾代表性、维护便利和安全隔离；视觉节点避免逆光和强遮挡", fill="#5a665e", font=font(22))
    rounded_rect(draw, (130, 220, 1670, 850), 28, "#eef6ff", "#b5c5bc", 3)
    # barn lanes
    for y in [330, 500, 670]:
        draw.line((220, y, 1580, y), fill="#8a9d90", width=8)
    for x in [420, 700, 980, 1260]:
        draw.line((x, 250, x, 820), fill="#c7d2c9", width=5)
    for i, (x, y) in enumerate([(310,410),(570,585),(850,410),(1130,585),(1390,410)]):
        rounded_rect(draw, (x-60,y-35,x+60,y+35), 20, "#b57737", "#80511f", 2)
    markers = [
        ("ESP32-S3 控制箱", 230, 245, "#72e38b"),
        ("MaixCam 视觉节点", 1500, 245, "#9ed2ff"),
        ("氨气传感器\n呼吸高度/粪污区上方", 250, 760, "#f6cf66"),
        ("温湿度/光照\n避开风口直吹", 850, 760, "#f6cf66"),
        ("风扇/雾化/报警\n执行器控制", 1450, 760, "#f05e49"),
    ]
    for text, x, y, color in markers:
        rounded_rect(draw, (x-130, y-55, x+130, y+55), 16, color, "#506052", 2)
        center_text(draw, (x-115,y-45,x+115,y+45), text, "#102216", font(19, True), 220)
    rounded_rect(draw, (250, 900, 1550, 970), 18, "#102216", "#102216", 1)
    center_text(draw, (270, 910, 1530, 960), "正式部署需增加防水盒、防尘滤网、线缆固定、接地保护和独立电源余量", "#f6fff7", font(24, True), 1200)
    out = ASSET_DIR / "deployment-layout.png"
    im.save(out, quality=95)
    return out


if __name__ == "__main__":
    hm = copy_hm_screens()
    print(make_hm_contact_sheet(hm))
    print(make_architecture_diagram())
    print(make_dataflow_diagram())
    print(make_website_contact_sheet())
    print(make_hardware_topology())
    print(make_mqtt_topic_map())
    print(make_database_er())
    print(make_api_map())
    print(make_ai_training_pipeline())
    print(make_alarm_closed_loop())
    print(make_deployment_layout())
