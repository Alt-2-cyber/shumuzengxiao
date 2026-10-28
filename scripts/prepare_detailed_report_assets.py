from pathlib import Path
from PIL import Image, ImageDraw, ImageFont


ASSET_DIR = Path("D:/table/shumuzengxiao/report_assets")
ASSET_DIR.mkdir(parents=True, exist_ok=True)


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


def rounded(draw, xy, radius=18, fill="#ffffff", outline="#b8c5ba", width=2):
    draw.rounded_rectangle(xy, radius=radius, fill=fill, outline=outline, width=width)


def center_text(draw, box, text, fill="#102216", font_obj=None, max_width=None, spacing=8):
    font_obj = font_obj or font(22)
    lines = []
    for raw in text.split("\n"):
        cur = ""
        for ch in raw:
            test = cur + ch
            if max_width and draw.textbbox((0, 0), test, font=font_obj)[2] > max_width and cur:
                lines.append(cur)
                cur = ch
            else:
                cur = test
        lines.append(cur)
    line_h = font_obj.size + spacing
    total_h = len(lines) * line_h
    x1, y1, x2, y2 = box
    y = y1 + (y2 - y1 - total_h) / 2
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font_obj)
        draw.text((x1 + (x2 - x1 - (bbox[2] - bbox[0])) / 2, y), line, fill=fill, font=font_obj)
        y += line_h


def arrow(draw, start, end, color="#2f6f46", width=5):
    import math

    x1, y1 = start
    x2, y2 = end
    draw.line((x1, y1, x2, y2), fill=color, width=width)
    ang = math.atan2(y2 - y1, x2 - x1)
    size = 17
    draw.polygon(
        [
            (x2, y2),
            (x2 - size * math.cos(ang - 0.45), y2 - size * math.sin(ang - 0.45)),
            (x2 - size * math.cos(ang + 0.45), y2 - size * math.sin(ang + 0.45)),
        ],
        fill=color,
    )


def make_edge_sequence_flow():
    w, h = 1800, 980
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "端边云服数据与控制时序链路", fill="#102216", font=font(44, True))
    draw.text((70, 96), "从环境采集、边缘事件、云端融合到多端处置和执行器反馈的完整闭环", fill="#5a665e", font=font(22))

    actors = [
        ("传感器/执行器", 120, "#e8f6ec"),
        ("ESP32-S3", 410, "#eef6ff"),
        ("MaixCam/声音节点", 700, "#fff6df"),
        ("MQTT/HTTP", 990, "#ffffff"),
        ("Spring Boot", 1280, "#f2edff"),
        ("Web/鸿蒙/小程序", 1570, "#e8f6ec"),
    ]
    top, bottom = 190, 820
    for name, x, fill in actors:
        rounded(draw, (x - 110, 170, x + 110, 240), 16, fill)
        center_text(draw, (x - 100, 178, x + 100, 232), name, font_obj=font(20, True), max_width=190)
        draw.line((x, 250, x, bottom), fill="#cad7ce", width=3)

    events = [
        (120, 410, "采样\n温湿度/氨气/烟雾"),
        (410, 410, "滤波与阈值\n本地联动"),
        (700, 410, "视觉/声音\n结构化事件"),
        (990, 410, "上报\ntelemetry/event"),
        (1280, 410, "入库融合\n风险评分"),
        (1570, 410, "告警展示\n人工复核"),
        (1280, 650, "命令队列\n状态机"),
        (990, 650, "下发\ncommand"),
        (410, 650, "执行控制\n风扇/雾化/报警"),
        (120, 650, "动作反馈\n现场状态"),
    ]
    for x, y, label in events:
        rounded(draw, (x - 115, y - 52, x + 115, y + 52), 14, "#ffffff")
        center_text(draw, (x - 100, y - 44, x + 100, y + 44), label, font_obj=font(19, True), max_width=185)

    for a, b in [
        ((235, 410), (295, 410)),
        ((525, 410), (585, 410)),
        ((815, 410), (875, 410)),
        ((1105, 410), (1165, 410)),
        ((1395, 410), (1455, 410)),
        ((1570, 465), (1395, 635)),
        ((1165, 650), (1105, 650)),
        ((875, 650), (525, 650)),
        ((295, 650), (235, 650)),
    ]:
        arrow(draw, a, b)

    rounded(draw, (260, 870, 1540, 935), 18, "#102216", "#102216", 1)
    center_text(draw, (280, 882, 1520, 923), "设计要点：高风险控制优先本地闭环，云端负责融合决策和跨端一致性，人工复核结果回流为模型迭代数据。", "#f6fff7", font(24, True), 1160)
    out = ASSET_DIR / "edge-sequence-flow.png"
    im.save(out, quality=95)
    return out


def make_risk_scoring_matrix():
    w, h = 1800, 1060
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "多模态风险评分矩阵", fill="#102216", font=font(44, True))
    draw.text((70, 96), "以可解释规则为原型，后续可替换为 Logistic / XGBoost / 轻量融合模型", fill="#5a665e", font=font(22))
    cols = ["信号来源", "关键指标", "权重建议", "触发逻辑", "证据形态"]
    col_w = [260, 430, 210, 430, 330]
    x0, y0 = 70, 180
    row_h = 112
    for i, c in enumerate(cols):
        x1 = x0 + sum(col_w[:i])
        rounded(draw, (x1, y0, x1 + col_w[i] - 10, y0 + 72), 12, "#102216", "#102216", 1)
        center_text(draw, (x1 + 8, y0 + 8, x1 + col_w[i] - 18, y0 + 64), c, "#f6fff7", font(22, True), col_w[i] - 24)
    rows = [
        ("环境", "温度、湿度、氨气、烟雾、光照", "30%", "连续超阈值或短时间突增", "曲线 + 阈值 + 时间戳"),
        ("视觉", "卧倒、跌倒、活动量下降、局部异常", "30%", "高置信事件或多帧持续", "截图 + 目标框 + 置信度"),
        ("声音", "咳嗽、喘鸣、异常叫声、背景噪声", "20%", "VAD 后有效声音事件", "音频片段 + SNR + 分类"),
        ("历史", "同栏位趋势、同牛只风险记录", "10%", "近期异常频次上升", "历史事件 + 复核结果"),
        ("人工复核", "巡检结论、兽医意见、处置结果", "10%", "人工确认或驳回", "复核表单 + 备注"),
    ]
    y = y0 + 84
    for idx, row in enumerate(rows):
        fill = "#ffffff" if idx % 2 == 0 else "#f0f6ef"
        for i, value in enumerate(row):
            x1 = x0 + sum(col_w[:i])
            rounded(draw, (x1, y, x1 + col_w[i] - 10, y + row_h), 12, fill, "#bfd0c3", 1)
            center_text(draw, (x1 + 12, y + 8, x1 + col_w[i] - 22, y + row_h - 8), value, "#173520", font(19, i == 0), col_w[i] - 34)
        y += row_h + 10
    rounded(draw, (150, 900, 1650, 975), 18, "#102216", "#102216", 1)
    center_text(draw, (170, 910, 1630, 965), "评分输出：正常 / 关注 / 告警 / 需复核。报告中只给风险复核优先级，不输出替代兽医诊断的结论。", "#f6fff7", font(24, True), 1400)
    out = ASSET_DIR / "risk-scoring-matrix.png"
    im.save(out, quality=95)
    return out


def make_data_governance_map():
    w, h = 1800, 980
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "数据治理与证据链管理地图", fill="#102216", font=font(44, True))
    draw.text((70, 96), "保证数据可追溯、可复核、可训练，避免只展示结果而无法解释原因", fill="#5a665e", font=font(22))
    lanes = [
        ("采集层", "原始读数\n图像/音频\n设备心跳", 110, "#e8f6ec"),
        ("标准化层", "统一时间戳\nbarnId/deviceId/targetId\n模型版本与置信度", 470, "#eef6ff"),
        ("业务层", "环境趋势\n视觉/声音事件\n健康风险/告警\n控制命令记录", 830, "#fff6df"),
        ("复核层", "人工确认\n处置结果\n误报/漏报\n样本标签", 1190, "#f2edff"),
        ("优化层", "阈值校准\n模型再训练\n版本发布\n效果评估", 1550, "#ffffff"),
    ]
    for title, body, x, fill in lanes:
        rounded(draw, (x - 145, 210, x + 145, 650), 24, fill)
        draw.text((x - 110, 245), title, fill="#102216", font=font(28, True))
        draw.multiline_text((x - 110, 315), body, fill="#263c2f", font=font(23), spacing=18)
    for x in [255, 615, 975, 1335]:
        arrow(draw, (x, 430), (x + 70, 430))
    rounded(draw, (240, 760, 1560, 870), 22, "#102216", "#102216", 1)
    draw.text((280, 785), "核心约束", fill="#72e38b", font=font(26, True))
    draw.text((280, 825), "任何告警都应能追溯到原始来源、时间窗口、模型版本、规则阈值和人工复核状态。", fill="#f6fff7", font=font(25, True))
    out = ASSET_DIR / "data-governance-map.png"
    im.save(out, quality=95)
    return out


def make_testing_acceptance_matrix():
    w, h = 1800, 1060
    im = Image.new("RGB", (w, h), "#fbfcfa")
    draw = ImageDraw.Draw(im)
    draw.text((70, 42), "测试验证与验收矩阵", fill="#102216", font=font(44, True))
    draw.text((70, 96), "围绕端侧稳定性、边缘 AI、平台接口、多端展示和现场处置闭环设计验收指标", fill="#5a665e", font=font(22))
    rows = [
        ("端侧采集", "连续运行、异常值过滤、断网缓存", "24h 稳定记录；恢复后补传关键事件"),
        ("边缘 AI", "视觉 FPS、延迟、误报/漏报、温升", "记录推理指标；高风险事件保留截图"),
        ("声音识别", "噪声背景下咳嗽/喘鸣检出", "有效声音进入事件库，低质量片段不触发高风险"),
        ("后端接口", "REST/MQTT 入库、查询、命令队列", "接口返回一致，命令有状态流转和历史记录"),
        ("多端展示", "Web、鸿蒙、小程序状态同步", "核心页面无错位，风险和设备状态一致"),
        ("现场闭环", "告警、处置、复核、样本回流", "每条告警可追溯证据和人工处理结论"),
    ]
    x0, y0 = 90, 185
    col_w = [300, 640, 670]
    headers = ["测试域", "测试内容", "验收口径"]
    for i, htxt in enumerate(headers):
        x1 = x0 + sum(col_w[:i])
        rounded(draw, (x1, y0, x1 + col_w[i] - 12, y0 + 74), 12, "#102216", "#102216", 1)
        center_text(draw, (x1 + 8, y0 + 8, x1 + col_w[i] - 20, y0 + 66), htxt, "#f6fff7", font(23, True), col_w[i] - 30)
    y = y0 + 86
    for idx, row in enumerate(rows):
        fill = "#ffffff" if idx % 2 == 0 else "#f0f6ef"
        for i, value in enumerate(row):
            x1 = x0 + sum(col_w[:i])
            rounded(draw, (x1, y, x1 + col_w[i] - 12, y + 103), 12, fill, "#bfd0c3", 1)
            center_text(draw, (x1 + 16, y + 8, x1 + col_w[i] - 28, y + 95), value, "#173520", font(20, i == 0), col_w[i] - 44)
        y += 115
    rounded(draw, (280, 925, 1520, 990), 18, "#102216", "#102216", 1)
    center_text(draw, (300, 935, 1500, 980), "验收优先级：先保证真实数据链路和闭环可靠，再逐步提高 AI 指标和自动化程度。", "#f6fff7", font(24, True), 1160)
    out = ASSET_DIR / "testing-acceptance-matrix.png"
    im.save(out, quality=95)
    return out


if __name__ == "__main__":
    for fn in [
        make_edge_sequence_flow,
        make_risk_scoring_matrix,
        make_data_governance_map,
        make_testing_acceptance_matrix,
    ]:
        print(fn())
