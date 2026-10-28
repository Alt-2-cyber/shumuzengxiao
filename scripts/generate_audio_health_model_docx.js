const fs = require("fs");
const path = require("path");
const {
  AlignmentType,
  BorderStyle,
  Document,
  ExternalHyperlink,
  Footer,
  Header,
  HeadingLevel,
  LevelFormat,
  Packer,
  PageBreak,
  PageNumber,
  Paragraph,
  ShadingType,
  Table,
  TableCell,
  TableOfContents,
  TableRow,
  TextRun,
  UnderlineType,
  VerticalAlign,
  WidthType,
} = require("docx");

const root = path.resolve(__dirname, "..");
const output = path.join(root, "数牧增效-牛声音健康风险筛查模型详细说明书.docx");

const COLORS = {
  ink: "20312A",
  muted: "5E6E67",
  forest: "1F5E46",
  leaf: "2E7D5B",
  paleGreen: "E7F2EC",
  paleBlue: "EAF2F8",
  paleGold: "FFF4D8",
  paleRed: "FCEAEA",
  header: "DDEBE3",
  grid: "B8C9C0",
  code: "F3F5F4",
  white: "FFFFFF",
};

const PAGE_WIDTH = 11906;
const PAGE_HEIGHT = 16838;
const MARGIN_LEFT = 1134;
const MARGIN_RIGHT = 1134;
const CONTENT_WIDTH = PAGE_WIDTH - MARGIN_LEFT - MARGIN_RIGHT;

const border = { style: BorderStyle.SINGLE, size: 6, color: COLORS.grid };
const tableBorders = { top: border, bottom: border, left: border, right: border, insideHorizontal: border, insideVertical: border };

function run(text, options = {}) {
  return new TextRun({
    text,
    font: options.font || "Microsoft YaHei",
    size: options.size || 21,
    color: options.color || COLORS.ink,
    bold: options.bold,
    italics: options.italics,
    underline: options.underline,
    break: options.break,
    allCaps: options.allCaps,
  });
}

function link(text, url) {
  return new ExternalHyperlink({
    link: url,
    children: [new TextRun({
      text,
      font: "Microsoft YaHei",
      size: 20,
      color: "0563C1",
      underline: { type: UnderlineType.SINGLE },
    })],
  });
}

function paragraph(children, options = {}) {
  return new Paragraph({
    children: Array.isArray(children) ? children : [run(children)],
    alignment: options.alignment || AlignmentType.JUSTIFIED,
    spacing: {
      before: options.before === undefined ? 0 : options.before,
      after: options.after === undefined ? 130 : options.after,
      line: options.line || 360,
    },
    indent: options.indent,
    keepNext: options.keepNext,
    pageBreakBefore: options.pageBreakBefore,
    border: options.border,
    shading: options.shading,
  });
}

function heading(text, level, options = {}) {
  const levelMap = {
    1: HeadingLevel.HEADING_1,
    2: HeadingLevel.HEADING_2,
    3: HeadingLevel.HEADING_3,
  };
  return new Paragraph({
    heading: levelMap[level],
    children: [run(text, {
      bold: true,
      color: level === 1 ? COLORS.forest : COLORS.ink,
      size: level === 1 ? 30 : level === 2 ? 26 : 23,
    })],
    pageBreakBefore: options.pageBreakBefore,
    spacing: { before: level === 1 ? 300 : 220, after: 120, line: 360 },
    keepNext: true,
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "bullets", level },
    children: [run(text)],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 90, line: 330 },
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: "numbers", level },
    children: [run(text)],
    alignment: AlignmentType.JUSTIFIED,
    spacing: { after: 90, line: 330 },
  });
}

function codeLine(text) {
  return new Paragraph({
    children: [new TextRun({ text, font: "Consolas", size: 17, color: "253B32" })],
    shading: { type: ShadingType.CLEAR, fill: COLORS.code },
    spacing: { before: 0, after: 0, line: 270 },
    indent: { left: 180, right: 180 },
  });
}

function cell(content, width, options = {}) {
  const children = Array.isArray(content)
    ? content
    : content instanceof Paragraph
      ? [content]
    : [paragraph(typeof content === "string" ? [run(content, { bold: options.bold, size: options.size || 19 })] : content, {
      after: 0,
      line: options.line || 300,
      alignment: options.alignment || AlignmentType.LEFT,
    })];
  return new TableCell({
    children,
    width: { size: width, type: WidthType.DXA },
    borders: tableBorders,
    shading: options.shading ? { type: ShadingType.CLEAR, fill: options.shading } : undefined,
    margins: { top: 90, bottom: 90, left: 120, right: 120 },
    verticalAlign: options.verticalAlign || VerticalAlign.CENTER,
  });
}

function table(headers, rows, widths, options = {}) {
  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((value, index) => cell(value, widths[index], {
      bold: true,
      size: 19,
      alignment: AlignmentType.CENTER,
      shading: options.headerColor || COLORS.header,
    })),
  });
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: [headerRow, ...rows.map((row, rowIndex) => new TableRow({
      children: row.map((value, index) => cell(value, widths[index], {
        size: 18,
        shading: options.alternate && rowIndex % 2 === 1 ? options.alternate : undefined,
        alignment: options.alignments && options.alignments[index] ? options.alignments[index] : AlignmentType.LEFT,
      })),
    }))],
  });
}

function keyValueTable(rows) {
  const widths = [2350, CONTENT_WIDTH - 2350];
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    rows: rows.map(([key, value], index) => new TableRow({
      children: [
        cell(key, widths[0], { bold: true, size: 19, shading: index % 2 === 0 ? COLORS.paleGreen : COLORS.header }),
        cell(value, widths[1], { size: 19 }),
      ],
    })),
  });
}

function callout(title, text, color = COLORS.paleGreen) {
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: [CONTENT_WIDTH],
    rows: [new TableRow({
      children: [cell([
        paragraph([run(title, { bold: true, color: COLORS.forest, size: 21 })], { after: 50, line: 300 }),
        paragraph([run(text, { size: 19 })], { after: 0, line: 320 }),
      ], CONTENT_WIDTH, { shading: color })],
    })],
  });
}

function spacer(height = 120) {
  return new Paragraph({ children: [], spacing: { before: 0, after: height } });
}

function sectionDivider() {
  return new Paragraph({
    children: [],
    spacing: { before: 0, after: 150 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: COLORS.leaf, space: 1 } },
  });
}

function modelStateTable() {
  return table(
    ["事项", "当前状态", "可作出的结论"],
    [
      ["公开数据训练", "已完成", "已得到牛声/非牛声二分类基线。"],
      ["当前生成的可部署头文件", "禁用", "include/cattle_audio_model.h 保持 kEnabled=false。"],
      ["呼吸事件模型", "未获批准", "没有兽医签核的 cough_suspect 或 wheeze_suspect 样本，不得发布。"],
      ["ESP32 在线功能", "feature_only", "继续上传声学特征与可回放 WAV 证据，不输出疾病结论。"],
      ["临床处置", "人工/兽医决策", "模型只提供复核线索，不能自动用药、隔离或诊断。"],
    ],
    [2500, 1800, CONTENT_WIDTH - 4300],
    { alternate: "F7FAF8" },
  );
}

function architectureTable() {
  const widths = [1700, 1700, 1700, 1700, CONTENT_WIDTH - 6800];
  return table(
    ["采集层", "边缘处理", "事件证据", "人工签核", "训练与发布"],
    [[
      "INMP441 以 I2S 采音；ESP32 同步获取温度、行为、环境等上下文。",
      "16 kHz 采样后降至 8 kHz；每 2 秒提取质量指标和 10 维特征。",
      "候选事件带 bootId、edgeEventId、特征、分数和可选 WAV 上传平台。",
      "审核员回放音频；兽医填写动物、会话、证据和临床确认字段。",
      "按动物/分组隔离验证；满足门禁后导出 C++ 头文件并重新烧录。",
    ]],
    widths,
    { headerColor: COLORS.forest, alternate: "F7FAF8", alignments: [AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT, AlignmentType.LEFT] },
  );
}

const children = [];

// Cover
children.push(spacer(700));
children.push(new Paragraph({
  children: [run("数牧增效", { bold: true, size: 38, color: COLORS.forest })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 100 },
}));
children.push(sectionDivider());
children.push(new Paragraph({
  children: [run("牛声音健康风险筛查模型", { bold: true, size: 48, color: COLORS.ink })],
  alignment: AlignmentType.CENTER,
  spacing: { before: 220, after: 120, line: 520 },
}));
children.push(new Paragraph({
  children: [run("详细技术说明书", { size: 31, color: COLORS.leaf })],
  alignment: AlignmentType.CENTER,
  spacing: { after: 430 },
}));
children.push(callout(
  "文件定位",
  "本文说明已实现的 ESP32 声学事件筛查链路、公开基线训练结果、临床数据发布门禁与试点验证方法。它不是兽医诊断报告，也不授权系统自动治疗。",
  COLORS.paleGold,
));
children.push(spacer(360));
children.push(keyValueTable([
  ["项目", "数牧增效多模态智能牛舍监测平台"],
  ["对象", "INMP441 + ESP32 声学采集、平台复核、临床标注、轻量模型部署链路"],
  ["文档版本", "V1.0"],
  ["生成日期", "2026-07-19"],
  ["当前模型状态", "公开数据基线已训练；疾病风险模型未发布；设备端保持 feature_only。"],
  ["适用范围", "现场声学事件留存、健康风险线索筛查、临床数据采集和后续模型发布。"],
]));
children.push(new Paragraph({ children: [new PageBreak()] }));

// Control page and summary
children.push(heading("文档控制与阅读摘要", 1));
children.push(paragraph("本说明书以当前工程代码、数据准备记录和模型元数据为准。本文中的“疾病风险”“呼吸风险”“咳嗽疑似”等术语均表示需要回放和复核的筛查候选，不表示疾病已经被确诊。"));
children.push(callout(
  "最重要的结论",
  "当前可复现的公开基线模型只能识别 cow_vocalization（牛声）与 non_cattle_audio（非牛声）。它的训练数据没有咳嗽、喘鸣或兽医临床标签，因此模型头文件被设计为默认禁用。任何将普通牛叫声直接解释为肺炎、呼吸道疾病或其他疾病的做法都不符合本项目的代码门禁和论文证据。",
  COLORS.paleRed,
));
children.push(spacer());
children.push(heading("读者可据此完成的工作", 2));
[
  "核验 INMP441 的接线、I2S 槽位校准状态、采样质量和平台遥测字段。",
  "复现 CC0 公开数据的牛声/非牛声基线训练与验证。",
  "组织试点牛场采集临床相关声音，完成兽医签核、动物分组和数据审计。",
  "执行发布门禁，只有全部条件通过后才把新模型编译进 ESP32。",
  "用声音、红外体温、行为、视觉和环境趋势联合形成复核工作流。",
].forEach((item) => children.push(bullet(item)));
children.push(spacer());
children.push(heading("目录", 1));
children.push(new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }));
children.push(new Paragraph({ children: [new PageBreak()] }));

// 1
children.push(heading("1. 项目目标与模型边界", 1));
children.push(paragraph("项目在牛舍现场持续采集声音，把疑似异常声学事件保存为可回放证据，并将其与体温、行为、视觉和环境数据关联。模型的正确定位是“由低成本边缘设备发现值得复核的声音线索”，而不是“仅用一段声音确诊疾病”。"));
children.push(heading("1.1 目标问题", 2));
children.push(table(
  ["层级", "问题", "系统输出", "禁止的输出"],
  [
    ["采集", "麦克风是否工作、现场是否有有效声音？", "status、RMS、dBFS、饱和率、SNR、频带能量。", "把电气噪声当成动物声音。"],
    ["事件", "是否出现值得留存的声学事件？", "音频事件、时间、WAV、候选标签、分数。", "单个事件直接触发疾病结论。"],
    ["风险", "是否存在需要进一步查验的呼吸相关候选？", "cough_suspect / wheeze_suspect 的筛查候选，仅在已批准模型下输出。", "输出肺炎、感染、药物建议等诊断或治疗。"],
    ["决策", "是否应安排人工巡栏或兽医检查？", "多模态证据包、优先级、复核队列。", "设备自动隔离、自动用药或替代兽医检查。"],
  ],
  [1100, 2050, 3000, CONTENT_WIDTH - 6150],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("1.2 当前真实状态", 2));
children.push(modelStateTable());
children.push(spacer());
children.push(heading("1.3 核心术语", 2));
children.push(table(
  ["术语", "本项目中的严格含义"],
  [
    ["声学事件", "在固定窗口内采集到可用声音，并生成质量特征或证据音频。"],
    ["牛声基线", "在公开物种标签数据上训练的 cow_vocalization 与 non_cattle_audio 区分器。"],
    ["cough_suspect", "由兽医审核的声音事件标签，表示咳嗽疑似，仍需结合临床证据。"],
    ["wheeze_suspect", "由兽医审核的声音事件标签，表示喘鸣或呼吸音异常疑似。"],
    ["unknown", "置信度不足或偏离训练分布时的拒识结果；它优先于强制分类。"],
    ["feature_only", "设备只上报特征，不启用分类候选。当前在线系统应处于该状态。"],
  ],
  [2500, CONTENT_WIDTH - 2500],
  { alternate: "F7FAF8" },
));

// 2
children.push(heading("2. 论文依据与可作出的工程主张", 1));
children.push(paragraph("论文证据支持将咳嗽、呼吸异常声和牛叫声作为健康或福利监测的潜在线索，但不支持以普通牛声数据替代临床标注，更不支持把声学分类器包装为疾病确诊器。项目的流程以“事件发现、证据留存、多模态复核、人工处置”为证据链。"));
children.push(heading("2.1 从论文到工程的逻辑", 2));
children.push(architectureTable());
children.push(spacer());
children.push(heading("2.2 主要文献与工程映射", 2));
children.push(table(
  ["文献", "可支持的结论", "工程对应"],
  [
    [paragraph([run("Ferrari 等，2010；"), link("DOI: 10.1016/j.prevetmed.2010.06.013", "https://doi.org/10.1016/j.prevetmed.2010.06.013")], { after: 0, line: 300, alignment: AlignmentType.LEFT }), "犊牛咳嗽声与呼吸道疾病临床情形有关，咳嗽是值得记录的声学事件。", "标签使用 cough_suspect，保留回放和临床复核。"],
    [paragraph([run("Vandermeulen 等，2016；"), link("DOI: 10.1016/j.compag.2016.07.014", "https://doi.org/10.1016/j.compag.2016.07.014")], { after: 0, line: 300, alignment: AlignmentType.LEFT }), "连续咳嗽声音监测有早期发现呼吸风险的研究基础。", "每 2 秒输出分析结果；候选事件限频并可保存 WAV。"],
    [paragraph([run("Costa 等，2021；"), link("DOI: 10.3168/jds.2019-17885", "https://doi.org/10.3168/jds.2019-17885")], { after: 0, line: 300, alignment: AlignmentType.LEFT }), "精准养殖健康监测应依赖连续记录与管理流程，单一传感器不足以完成临床判断。", "平台保留声音、红外体温、行为、环境和视觉上下文。"],
    [paragraph([run("Limede 等，2025；"), link("DOI: 10.1093/jas/skaf345", "https://doi.org/10.1093/jas/skaf345")], { after: 0, line: 300, alignment: AlignmentType.LEFT }), "牛健康状态可通过音频、视觉和行为的联合数据来解释。", "只在多模态证据共同支持时提高人工巡检优先级。"],
    [paragraph([run("Jobarteh 等，2025；"), link("DOI: 10.3389/fvets.2025.1704031", "https://doi.org/10.3389/fvets.2025.1704031")], { after: 0, line: 300, alignment: AlignmentType.LEFT }), "牛叫声分析需要结合现场上下文，不能仅凭短音频下健康结论。", "网页端展示音频、审核标签、模型版本和现场指标。"],
    [paragraph([run("Schook 等，2015；"), link("DOI: 10.1016/j.compag.2015.08.028", "https://doi.org/10.1016/j.compag.2015.08.028")], { after: 0, line: 300, alignment: AlignmentType.LEFT }), "声学频谱与时序特征可用于牛福利/状态研究，但并不等价于疾病诊断。", "公开牛声只用于物种/声音存在基线，不映射为疾病标签。"],
  ],
  [2700, 3550, CONTENT_WIDTH - 6250],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("2.3 证据边界", 2));
[
  "论文支持声音作为连续、非接触式风险线索；它不保证每一段咳嗽都对应疾病，也不保证每个患病个体都会被声音捕获。",
  "同一声学模式可能由不同来源产生，例如风机、碰撞、其他动物、人员、饲喂设备和牛自身发声。",
  "模型的临床有效性必须在目标牛场、目标麦克风安装位置、目标动物群和明确参考标准下重新验证。",
  "任何健康风险评分都必须显示音频证据、模型版本、置信度、质量状态和人工复核入口。",
].forEach((item) => children.push(bullet(item)));

// 3
children.push(heading("3. 端侧硬件、采样与通信架构", 1));
children.push(paragraph("声学模块使用六针 INMP441 数字 MEMS 麦克风。ESP32 不通过模拟口读取声音，而是使用 I2S0 接收 32 位数字帧；固件在启动时读取两个 I2S 槽位并选择信号更健康的一路，从而避免 L/R 接错或浮空导致的伪有效数据。"));
children.push(heading("3.1 INMP441 接线与关键参数", 2));
children.push(table(
  ["INMP441 引脚", "ESP32 引脚", "用途与说明"],
  [
    ["VDD", "3V3", "只使用稳定的 3.3 V 供电，不接 5 V。"],
    ["GND", "GND", "与 ESP32 和所有传感器共地。"],
    ["SCK", "D5 / GPIO5", "I2S 位时钟 BCLK。"],
    ["WS", "D16 / GPIO16", "I2S 左右声道时钟 LRCL / WS。"],
    ["SD", "D17 / GPIO17", "I2S 数字数据输入。不要将其当作模拟 AO。"],
    ["L/R", "GND", "选择通道；固件仍会检查两个时隙并报告 slot0 或 slot1。"],
  ],
  [1900, 1900, CONTENT_WIDTH - 3800],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("3.2 固件声学时序", 2));
children.push(table(
  ["阶段", "实现参数", "目的"],
  [
    ["I2S 原始采样", "16 kHz、32-bit、DMA 8 缓冲区，每缓冲 256 样本。", "获得 INMP441 的数字原始样本，并降低主循环阻塞风险。"],
    ["槽位校准", "启动后累计 4,096 帧；默认自动选择更健康时隙。", "发现 L/R、电平、单边无信号等接线问题。"],
    ["确定性抽取", "2:1 降采样到 8 kHz。", "将特征、训练和证据音频统一到同一采样率。"],
    ["分析窗口", "2 秒；每窗 16,000 个 8 kHz 样本。", "与训练器的 window_seconds=2.0 对齐。"],
    ["频谱帧", "128 样本；每帧约 16 ms。", "以固定成本计算 Goertzel 频带能量。"],
    ["证据采集", "2 秒、8 kHz、单声道、8-bit PCM，增益 8.0。", "通过串口 Base64 上传并在后端保存 WAV 供回放。"],
  ],
  [1900, 3000, CONTENT_WIDTH - 4900],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("3.3 端侧质量状态", 2));
children.push(table(
  ["状态", "触发条件", "现场处理"],
  [
    ["calibrating", "刚启动，尚未完成 I2S 槽位选择。", "等待约 1 秒；不要据此判断麦克风故障。"],
    ["signal_invalid", "无有效槽位，或 RMS >= 0.250，或饱和比例 >= 0.08。", "检查供电、地线、L/R、SD、麦克风位置和强电磁干扰。"],
    ["no_samples", "I2S 初始化成功但当前窗口没有样本。", "检查 I2S 时钟、任务执行和设备负载。"],
    ["ok", "槽位可用且信号未触发失真门限。", "允许上报特征；只有已批准模型才允许分类。"],
  ],
  [2000, 3500, CONTENT_WIDTH - 5500],
  { alternate: "F7FAF8" },
));

// 4
children.push(heading("4. 数据资产、来源审计与临床标注", 1));
children.push(paragraph("模型训练数据被视为与固件同等重要的交付物。工程不允许从下载文件夹直接把任意 WAV 送入训练；每条录音都需要可追溯来源、许可、哈希、质量统计、标签来源和分组信息。"));
children.push(heading("4.1 已使用的公开数据", 2));
children.push(keyValueTable([
  ["数据源", "Animal Sounds Classification (ASC24)，Kaggle，CC0-1.0。"],
  ["归档哈希", "651b58457d66a96ff0ced2139926935242d816f6396a31cab83c745c0df34670"],
  ["原始类别", "Cow 114 段、Dog 156 段、Frog 104 段，共 374 段。"],
  ["规范化格式", "8 kHz、单声道、16-bit PCM WAV。"],
  ["质量剔除", "18 段过短、4 段饱和、30 段规范化后精确重复，总计保留 322 段。"],
  ["许可用途", "仅允许训练 cow_vocalization 与 non_cattle_audio 基线；不得映射为咳嗽、喘鸣、疾病或诊断。"],
  ["明确禁止的数据", "SINC grazing jaw movements 仓库未声明许可，已登记为 blocked_license_unverified，不下载、不训练、不再分发。"],
]));
children.push(spacer());
children.push(heading("4.2 数据准备质量门", 2));
[
  "校验下载归档 SHA-256，哈希与来源注册表不一致时立即拒绝。",
  "使用 ffmpeg 统一转码为 8 kHz、单声道、16-bit PCM，确保训练与设备输入可比较。",
  "剔除时长小于 0.5 秒或大于 10 秒、RMS 低于 -60 dBFS、饱和比例超过 2% 的录音。",
  "按规范化 WAV 的 SHA-256 去除完全重复内容；如同一内容处于不同标签，训练流程直接报错。",
  "以 sourceId、来源类别和原始文件名构造 groupId，使同一来源的关联 A/B 片段不会跨训练/验证集。",
].forEach((item) => children.push(numbered(item)));
children.push(spacer());
children.push(heading("4.3 生产临床数据必须具备的字段", 2));
children.push(table(
  ["字段", "作用", "为什么不能省略"],
  [
    ["sourceEventId", "与平台中的音频事件和 WAV 一一对应。", "保证训练样本可回放、可追责、可删除。"],
    ["label", "例如 cough_suspect、wheeze_suspect、normal、moo、barn_noise。", "标签必须与兽医签核表一致。"],
    ["animalId", "耳标或稳定的个体标识。", "用于按动物分组，防止同一头牛泄漏到训练与验证两侧。"],
    ["recordingSessionId", "同一栏位、时段和采集会话标识。", "便于识别批次与环境泄漏。"],
    ["veterinarian", "完成临床确认的兽医或签核主体。", "风险标签必须有责任来源。"],
    ["evidenceReference", "病例号、检查记录、视频或其他临床证据索引。", "声音标签不能脱离临床参考标准。"],
    ["verifiedAt", "签核时间。", "支持版本追溯、撤销和再训练审计。"],
  ],
  [2100, 2500, CONTENT_WIDTH - 4600],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(codeLine("sourceEventId,label,animalId,recordingSessionId,veterinarian,evidenceReference,verifiedAt"));
children.push(codeLine("101,cough_suspect,cattle-017,session-20260719-am,vet-case-20260719-017,case-file-or-video-reference,2026-07-19T10:30:00Z"));
children.push(spacer());
children.push(paragraph("临床签核工具会把上述字段写回清单，并设置 clinicalVerified=true、allowForDiseaseLabels=true、labelProvenance=veterinarian_verified_audio_event。普通网页审核不等于临床签核，不能绕过这一步。"));

// 5
children.push(heading("5. 特征工程与端云一致性", 1));
children.push(paragraph("本模型选择 10 维可解释特征和线性 Softmax 分类器，而不是在当前规模下部署大型神经网络。该设计的重点是让 ESP32、训练脚本和现场审计使用同一特征定义，以降低训练端高分但设备端表现不一致的风险。"));
children.push(heading("5.1 10 维特征定义", 2));
children.push(table(
  ["索引", "特征", "计算方式", "反映的声学性质"],
  [
    ["f0", "log RMS", "log(max(RMS, 1e-5))", "总体能量与响度。"],
    ["f1", "过零率 ZCR", "符号翻转次数 / 样本数", "粗略频率和噪声变化程度。"],
    ["f2", "峰均比", "min(10, peak / max(RMS, 1e-5))", "瞬态、冲击和尖锐程度。"],
    ["f3-f8", "6 个相对频带能量", "log(max(Ek / sum(E), 1e-6))", "频谱分布，使用 Goertzel 计算。"],
    ["f9", "差分粗糙度", "log(sqrt(sum((x[t]-x[t-1])^2) / sum(x[t]^2)))", "波形快速变化与纹理。"],
  ],
  [700, 1700, 3550, CONTENT_WIDTH - 5950],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("5.2 Goertzel 频带", 2));
children.push(paragraph("每个 128 样本帧在 8 kHz 下对应约 16 ms。Goertzel bin 的中心频率由 f = k x 8000 / 128 计算。模型使用相对能量而不是绝对能量，因此对整体音量变化有一定稳健性，但它不能替代现场增益和安装位置的校准。"));
children.push(table(
  ["bin k", "中心频率", "特征位置", "说明"],
  [
    ["2", "125 Hz", "f3", "低频成分。"],
    ["4", "250 Hz", "f4", "低频成分。"],
    ["8", "500 Hz", "f5", "中低频成分。"],
    ["16", "1,000 Hz", "f6", "中频成分。"],
    ["32", "2,000 Hz", "f7", "中高频成分。"],
    ["48", "3,000 Hz", "f8", "高频成分。"],
  ],
  [1100, 1750, 1450, CONTENT_WIDTH - 4300],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("5.3 端侧和训练器对齐机制", 2));
children.push(table(
  ["一致性点", "ESP32 固件", "Python 训练器", "风险控制"],
  [
    ["采样率", "16 kHz I2S 后 2:1 降采样到 8 kHz。", "输入 WAV 重采样到 8 kHz。", "避免同名特征对应不同频率。"],
    ["窗口", "每 2 秒累积一个推理窗口。", "window_seconds=2.0，window_hop_seconds=2.0。", "训练和现场长度相同。"],
    ["频谱", "128 点帧、bins 2/4/8/16/32/48。", "相同帧长和 Goertzel bins。", "消除频带位置漂移。"],
    ["特征公式", "C++ 中完成 RMS、ZCR、峰均比、频带比与差分项。", "extract_features 使用相同公式。", "导出头文件前可做抽样比对。"],
  ],
  [1400, 2850, 2850, CONTENT_WIDTH - 7100],
  { alternate: "F7FAF8" },
));

// 6
children.push(heading("6. 模型结构、推理与拒识策略", 1));
children.push(paragraph("当前训练器输出的是标准化后的多类线性 Softmax 模型。它将 10 维特征标准化，计算每类线性得分，再归一化为概率。选择轻量模型的原因是：模型参数直接导出为 C++ 常量数组，ESP32 无需额外推理框架，推理路径可审计且适合持续小窗口运行。"));
children.push(heading("6.1 数学形式", 2));
children.push(codeLine("z = (x - mean) / scale"));
children.push(codeLine("score_c = bias_c + sum_i(z_i * weight_c,i)"));
children.push(codeLine("p_c = exp(score_c - max(score)) / sum_j exp(score_j - max(score))"));
children.push(paragraph("预测类别为最大 p_c 对应的类别，但最大概率不是唯一门槛。为了避免现场出现训练集未覆盖的风机、碰撞、人员或动物声音时被强制归入某类，模型还计算特征到预测类中心的欧氏距离。"));
children.push(heading("6.2 双重拒识", 2));
children.push(table(
  ["门槛", "做法", "结果"],
  [
    ["Softmax 置信度", "若最大类别概率小于训练后校准得到的 minimumConfidence，则拒识。", "返回 unknown，不进入呼吸风险候选。"],
    ["类中心距离", "若标准化特征到预测类别中心的距离超过该类 distanceLimit，则拒识。", "防止 OOD 声音被高置信度误分。"],
    ["设备风险分数", "即使类别是呼吸风险标签，prediction.score 还必须 >= 0.72。", "降低低分候选的自动事件频率。"],
  ],
  [2100, 4100, CONTENT_WIDTH - 6200],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("6.3 固件运行状态机", 2));
children.push(table(
  ["顺序", "条件", "动作"],
  [
    ["1", "麦克风初始化与槽位校准完成", "开始累积 2 秒质量与特征数据。"],
    ["2", "槽位无信号、RMS 过高或饱和过多", "标记 signal_invalid，跳过事件和推理。"],
    ["3", "RMS >= 0.010，且模型 kEnabled=true", "生成 10 维向量并调用 cattle_audio_model::predict。"],
    ["4", "预测标签为风险标签且分数 >= 0.72", "生成 audio_event，最小 30 秒间隔。"],
    ["5", "距离上次证据采集 >= 60 秒且允许自动采集", "保留两秒 PCM，上传平台转换成 WAV。"],
    ["6", "模型未批准", "modelStatus=feature_only，只上报特征和手动采样证据。"],
  ],
  [700, 4200, CONTENT_WIDTH - 4900],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("6.4 头文件契约", 2));
children.push(paragraph("训练器把模型权重、偏置、标准化均值/尺度、各类特征中心、距离阈值、标签、模型版本和验证指标导出到 include/cattle_audio_model.h。该文件是部署产物，不应手工改写权重或把 kEnabled 从 false 强行改为 true。"));
children.push(codeLine("constexpr bool kEnabled = false;  // 当前工程中的占位模型，刻意禁用"));
children.push(codeLine("constexpr const char *kVersion = \"untrained-audio-profile\";"));

// 7
children.push(heading("7. 当前基线的训练、验证与局限", 1));
children.push(paragraph("当前可复现产物为 cattle-vocalization-baseline-v2-bedc334739f4。它证明了数据审计、特征提取、分组切分、模型导出、端侧头文件编译和拒识链路可以运行。由于数据没有临床风险标签，该产物仅可作为技术基线，不可发布为疾病风险模型。"));
children.push(heading("7.1 基线数据与切分", 2));
children.push(table(
  ["项目", "数值"],
  [
    ["来源音频数", "322 段，均来自已注册的 kaggle-asc24-v1 公开 CC0 数据。"],
    ["生成的 2 秒样本窗口", "639 个。"],
    ["训练窗口", "514 个。"],
    ["验证窗口", "125 个。"],
    ["训练独立分组", "231 个。"],
    ["验证独立分组", "57 个。"],
    ["标签", "cow_vocalization、non_cattle_audio。"],
    ["数据指纹", "bedc334739f48710bae70aa904909c1918ca523e9fb892e83945ba89137edabf"],
  ],
  [2700, CONTENT_WIDTH - 2700],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("7.2 验证结果", 2));
children.push(table(
  ["类别", "验证支持数", "Precision", "Recall", "F1"],
  [
    ["cow_vocalization", "32", "0.815", "0.688", "0.746"],
    ["non_cattle_audio", "93", "0.910", "0.871", "0.890"],
    ["Macro 平均", "125", "-", "-", "0.818"],
  ],
  [2750, 1500, 1500, 1500, CONTENT_WIDTH - 7250],
  { alternate: "F7FAF8", alignments: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER] },
));
children.push(spacer());
children.push(table(
  ["真实类别 \\ 预测", "cow_vocalization", "non_cattle_audio", "unknown"],
  [
    ["cow_vocalization", "22", "8", "2"],
    ["non_cattle_audio", "5", "81", "7"],
  ],
  [2850, 2200, 2200, CONTENT_WIDTH - 7250],
  { alternate: "F7FAF8", alignments: [AlignmentType.LEFT, AlignmentType.CENTER, AlignmentType.CENTER, AlignmentType.CENTER] },
));
children.push(spacer());
children.push(keyValueTable([
  ["总体准确率", "0.824"],
  ["Macro-F1", "0.8179363009871484"],
  ["置信度阈值", "0.625"],
  ["拒识率", "0.072"],
  ["部署状态", "disabled；releaseGate.approved=false。"],
  ["禁用原因", "未请求 --release；缺少 cough_suspect 临床标签。"],
]));
children.push(spacer());
children.push(heading("7.3 如何正确解释这些分数", 2));
[
  "0.818 的 Macro-F1 只描述这两个公开类别在当前分组验证集上的表现，不能外推为咳嗽、喘鸣或疾病识别准确率。",
  "验证分组已避免同一关联原始录音在训练和验证间泄漏，但仍不等价于跨牛场、跨设备、跨季节的外部验证。",
  "拒识率 0.072 表明部分窗口被主动标记为 unknown；在健康风险场景中，适度拒识比错误的强制分类更安全。",
  "该结果可作为后续临床数据模型的工程起点和回归基线，而不是上线疾病报警阈值的依据。",
].forEach((item) => children.push(bullet(item)));

// 8
children.push(heading("8. 生产发布门禁与多模态复核", 1));
children.push(paragraph("模型发布被设计为显式的、可审计的动作。只有训练命令包含 --release，且所有临床数据、独立分组和验证指标均达到阈值时，生成的头文件才会写入 kEnabled=true。否则代码会生成可检查但禁用的产物。"));
children.push(heading("8.1 默认发布门槛", 2));
children.push(table(
  ["门槛", "默认值", "实现目的"],
  [
    ["训练发布开关", "必须显式传入 --release。", "防止测试模型被误烧录为生产模型。"],
    ["风险标签", "required-clinical-labels 默认 cough_suspect，可扩展 wheeze_suspect。", "只允许明确的临床风险事件触发风险候选。"],
    ["每个风险标签临床文件数", ">= 100", "避免仅凭少数个案发布。"],
    ["验证独立动物组", ">= 3", "避免样本重复导致虚高。生产试点应提高这一门槛。"],
    ["风险类 Precision", ">= 0.80", "控制假阳性带来的无效巡检。"],
    ["风险类 Recall", ">= 0.70", "控制大量风险事件漏检。"],
    ["Macro-F1", ">= 0.75", "保证整体类别平衡表现。"],
    ["临床可追溯性", "每个风险样本均要有兽医、动物、会话、证据和允许疾病训练标记。", "保证模型的标签来源可审计。"],
  ],
  [2650, 2050, CONTENT_WIDTH - 4700],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("8.2 事件去重与证据留存", 2));
children.push(paragraph("ESP32 在每次启动时产生 bootId；事件以 deviceId + bootId + edgeEventId 组合去重。这样串口重传不会在后端生成多条相同事件，设备重启后新事件也不会被旧序号覆盖。呼吸风险候选最短 30 秒产生一次事件，自动证据采集最短 60 秒一次。"));
children.push(table(
  ["字段", "用途"],
  [
    ["deviceId / barnId / cattleId", "定位设备、牛舍和受监测个体。现场部署前必须把 cattleId 改为真实耳标或管理编号。"],
    ["bootId / edgeEventId", "实现跨串口重传的幂等性。"],
    ["eventLabel / eventScore", "记录模型候选和分数，供人复核而非直接处置。"],
    ["rms / dbfs / ZCR / band ratios / saturationRatio", "记录事件质量和可解释特征。"],
    ["modelVersion / modelStatus", "区分 feature_only、已批准模型以及不同模型版本。"],
    ["PCM/WAV", "保存可以试听的原始证据，用于审核、纠错、再训练和争议处理。"],
  ],
  [3300, CONTENT_WIDTH - 3300],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("8.3 多模态复核建议", 2));
children.push(table(
  ["证据来源", "与声学候选的关系", "建议操作"],
  [
    ["B-1 红外体温", "体温趋势异常可提高声学候选的复核优先级。", "检查测量距离、环境影响和重复读数，不把单次读数当作诊断。"],
    ["三处 IMU 行为", "活动降低、躺卧异常、采食相关活动变化是可能的补充线索。", "查看颈、背、腿传感器质量与行为时间序列。"],
    ["MaixCam 视觉", "姿态、咳嗽动作、采食和群体行为可提供现场上下文。", "保留相关时间段画面，人工复核。"],
    ["温湿度、氨气、光照", "环境恶化可能解释声音变化，也可能是风险因素。", "检查通风、饲喂、栏舍清洁和传感器漂移。"],
    ["人工巡检/兽医", "构成最终临床参考标准。", "根据证据包做检查、记录和处置，不依据模型直接用药。"],
  ],
  [2400, 3200, CONTENT_WIDTH - 5600],
  { alternate: "F7FAF8" },
));

// 9
children.push(heading("9. 训练、导出、烧录与回归验证", 1));
children.push(paragraph("本节给出工程中的可复现工作流。实际发布前应在新的版本化输出目录中执行，并保存命令、输入清单、模型卡和训练元数据。不要将临床数据、公开数据、临时 WAV 和最终模型混放。"));
children.push(heading("9.1 准备公开基线数据", 2));
children.push(codeLine("cd D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点"));
children.push(codeLine("$python = 'C:\\Users\\q4984\\AppData\\Local\\Programs\\Python\\Python311\\python.exe'"));
children.push(codeLine("& $python tools\\prepare_audio_dataset.py --source-id kaggle-asc24-v1 --archive D:\\table\\shumuzengxiao\\audio-training-data\\raw\\kaggle-asc24-sounds-of-animals-v1.zip --output D:\\table\\shumuzengxiao\\audio-training-data\\prepared\\kaggle-asc24-v3 --ffmpeg C:\\path\\to\\ffmpeg.exe"));
children.push(spacer());
children.push(heading("9.2 训练公开基线", 2));
children.push(codeLine("& $python tools\\train_audio_model.py --manifest D:\\table\\shumuzengxiao\\audio-training-data\\prepared\\kaggle-asc24-v3\\manifest.jsonl --output D:\\table\\shumuzengxiao\\audio-training-data\\artifacts\\kaggle-asc24-v3\\cattle_vocalization_baseline.h --metadata D:\\table\\shumuzengxiao\\audio-training-data\\artifacts\\kaggle-asc24-v3\\audio_model_metadata.json --model-card D:\\table\\shumuzengxiao\\audio-training-data\\artifacts\\kaggle-asc24-v3\\audio_model_card.md"));
children.push(paragraph("该命令不传入 --release，因此即使验证分数较好，导出的头文件也将保持禁用。它用于检查训练与导出链路，不用于触发疾病候选。"));
children.push(heading("9.3 导出经兽医签核的临床清单", 2));
children.push(codeLine("& $python tools\\export_reviewed_audio_dataset.py --api http://localhost:8080 --output D:\\table\\shumuzengxiao\\audio-training-data\\reviewed\\batch-001"));
children.push(codeLine("& $python tools\\verify_clinical_audio_manifest.py --manifest D:\\table\\shumuzengxiao\\audio-training-data\\reviewed\\batch-001\\reviewed_manifest.jsonl --annotations D:\\table\\shumuzengxiao\\audio-training-data\\reviewed\\batch-001\\clinical_annotations.csv --output D:\\table\\shumuzengxiao\\audio-training-data\\reviewed\\batch-001\\clinical_manifest.jsonl"));
children.push(heading("9.4 申请临床模型发布", 2));
children.push(codeLine("& $python tools\\train_audio_model.py --manifest D:\\table\\shumuzengxiao\\audio-training-data\\reviewed\\batch-001\\clinical_manifest.jsonl --output include\\cattle_audio_model.h --metadata tools\\audio_model_metadata.json --model-card tools\\audio_model_card.md --release --required-clinical-labels cough_suspect,wheeze_suspect"));
children.push(paragraph("训练器会输出 metadata JSON、模型卡和 C++ 头文件。若有任一门禁失败，kEnabled 仍为 false；应先解决数据或验证问题，不应手动绕过。"));
children.push(spacer());
children.push(heading("9.5 上板验收清单", 2));
[
  "启动串口后确认 microphone.initialized=true，status 从 calibrating 转为 ok。",
  "确认 microphone.channel 为 slot0 或 slot1，且在安静环境下 RMS、dBFS、SNR 合理且不长时间饱和。",
  "从网页请求一次 audio_capture，确认后端保存的 WAV 可回放且长度约两秒。",
  "确认 modelVersion 与训练元数据一致；未批准模型必须显示 modelStatus=feature_only。",
  "仅在临床发布门禁通过后，模拟风险标签、事件限频、去重和 WAV 证据关联。",
  "在不同风机、饲喂、人员、牛群密度和昼夜条件下记录误报与拒识，形成现场回归集。",
].forEach((item) => children.push(numbered(item)));

// 10
children.push(heading("10. 试点临床验证与持续迭代方案", 1));
children.push(paragraph("生产级模型不应一次性以公开数据替代真实现场采样。推荐以小范围试点建立基线、以事件证据和兽医记录构建标签、以独立动物和独立时段验证泛化能力，并通过受控发布逐步扩大范围。"));
children.push(heading("10.1 分阶段计划", 2));
children.push(table(
  ["阶段", "产出", "放行条件"],
  [
    ["阶段 A：设备基线", "每个安装点的噪声地板、饱和率、slot 状态、WAV 可听性。", "至少连续运行 7 天，无持续信号无效问题。"],
    ["阶段 B：事件采集", "带 cattleId、位置、时段、环境与人工审核的声学事件库。", "证明不同声源可区分，且能回放复查。"],
    ["阶段 C：临床签核", "兽医标注的 cough_suspect/wheeze_suspect 等清单及参考证据。", "每个风险标签达到最低数量、完整字段和许可要求。"],
    ["阶段 D：离线验证", "按动物和会话隔离的模型卡、混淆矩阵、误差分析。", "满足 precision、recall、macro-F1、拒识和跨时段检查。"],
    ["阶段 E：影子运行", "模型输出到网页复核队列，不触发强提醒。", "误报、漏报和现场工作量在可接受范围内。"],
    ["阶段 F：受控发布", "kEnabled=true 的版本化固件和监控计划。", "有回滚版本、数据留存、责任人和复审周期。"],
  ],
  [1750, 3900, CONTENT_WIDTH - 5650],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("10.2 推荐的试验设计", 2));
[
  "按动物而不是按音频片段切分训练、验证和测试集。目标牛个体不得同时出现在训练与验证。",
  "至少增加跨日期、跨栏位、跨天气、跨设备位置的独立外部测试集，防止模型只记住某个场景。",
  "风险事件参考标准由兽医检查、病例记录、体温/临床表现等组成，而不是审核员只凭声音主观判断。",
  "同时记录无风险牛和干扰声，评估真实世界假阳性率、每头牛每天告警数和人工复核负荷。",
  "建立错误样本集：风机、铁栏碰撞、饲喂车、犬吠、其他牲畜、人声、雨声和网络/供电异常音。",
].forEach((item) => children.push(bullet(item)));
children.push(spacer());
children.push(heading("10.3 模型更新与回滚", 2));
children.push(table(
  ["控制项", "要求"],
  [
    ["版本", "每次训练记录模型版本、数据集指纹、代码版本、阈值、执行命令和生成时间。"],
    ["基线回归", "新模型不得无故劣于既有测试集；必要时保留旧模型作为回滚头文件。"],
    ["灰度", "先对少量设备启用，在网页中观察候选与人工复核结果，再逐步扩大。"],
    ["撤销", "发现标签错误、数据污染、硬件漂移或误报异常时，立即回退到 feature_only 或已知稳定版本。"],
    ["再校准", "麦克风位置、供电、罩壳、风机和栏舍布局变化后，需要重新做设备基线和必要的模型外部验证。"],
  ],
  [2200, CONTENT_WIDTH - 2200],
  { alternate: "F7FAF8" },
));

// 11
children.push(heading("11. 风险、隐私与运维要求", 1));
children.push(heading("11.1 主要失效模式", 2));
children.push(table(
  ["风险", "可观测信号", "缓解措施"],
  [
    ["供电或接线不稳", "signal_invalid、饱和率升高、原始样本异常。", "使用稳定 3.3 V、共地、短线、必要滤波；检查 L/R 和 I2S 引脚。"],
    ["环境噪声漂移", "SNR 降低、unknown 增多、误报增加。", "记录噪声地板；按季节/设备状态采集数据并重新验证。"],
    ["数据泄漏", "同一牛/同一会话在训练和验证都有样本。", "使用 animalId/groupId 的强制分组；训练器检测交叉分组。"],
    ["标签不可靠", "不同审核者意见分歧，病例证据缺失。", "要求兽医签核、证据引用和可回放音频；保留撤销机制。"],
    ["过度自动化", "模型分数被误解为疾病结论。", "网页和文档明确显示筛查性质；不自动用药或隔离。"],
    ["串口重传", "相同事件多次入库。", "deviceId + bootId + edgeEventId 幂等去重。"],
  ],
  [2200, 3600, CONTENT_WIDTH - 5800],
  { alternate: "F7FAF8" },
));
children.push(spacer());
children.push(heading("11.2 数据治理", 2));
[
  "WAV、兽医记录和耳标关联信息应按项目权限管理，避免在无授权场景中公开传播原始数据。",
  "训练集、模型卡、评估报告和已部署头文件要保留哈希和版本记录，保证能回溯到具体来源与签核。",
  "若发现音频、标签或临床证据错误，应撤销其训练资格，重新生成清单和模型，不只修改展示层标签。",
  "对音频证据应定义保存期限、访问角色和删除流程，尤其是包含人员对话的偶发录音。",
].forEach((item) => children.push(bullet(item)));

// 12
children.push(heading("12. 结论", 1));
children.push(paragraph("数牧增效的牛声音模块已经完成了从 INMP441 采样、质量诊断、两秒声学特征、平台 WAV 证据、数据审计、分组训练、模型导出到端侧拒识的完整技术闭环。公开 CC0 数据验证了牛声/非牛声基线能够在既定条件下运行，但它不含临床呼吸风险标签，因而当前模型正确状态是 feature_only。"));
children.push(paragraph("下一步的关键不在于强行扩大模型类别，而在于按真实安装方式采集带兽医签核的临床数据，采用按动物和会话隔离的验证，满足发布门禁后再将 cough_suspect 和 wheeze_suspect 作为可回放的风险候选部署。系统最终应帮助饲养员更早、更有证据地安排检查，而不是替代兽医诊断。"));

// Appendix A
children.push(heading("附录 A：工程文件索引", 1, { pageBreakBefore: true }));
children.push(table(
  ["文件", "职责"],
  [
    ["硬件代码/现有硬件演示节点/src/main.cpp", "INMP441 I2S 采样、特征累计、事件发射、WAV 证据与遥测输出。"],
    ["硬件代码/现有硬件演示节点/include/config.h", "麦克风引脚、采样率、质量阈值、事件限频和证据采集参数。"],
    ["硬件代码/现有硬件演示节点/include/cattle_audio_model.h", "端侧模型占位或训练后生成的权重头文件；当前刻意禁用。"],
    ["硬件代码/现有硬件演示节点/tools/audio_dataset_sources.json", "来源、许可证、哈希、标签映射和允许用途注册表。"],
    ["硬件代码/现有硬件演示节点/tools/prepare_audio_dataset.py", "归档验证、转码、质量筛选、去重和分组清单生成。"],
    ["硬件代码/现有硬件演示节点/tools/export_reviewed_audio_dataset.py", "从平台导出审核过的音频事件。"],
    ["硬件代码/现有硬件演示节点/tools/verify_clinical_audio_manifest.py", "合并兽医签核 CSV，生成允许疾病训练的清单。"],
    ["硬件代码/现有硬件演示节点/tools/train_audio_model.py", "提取特征、训练 Softmax、评估、校准拒识并导出头文件。"],
    ["audio-training-data/artifacts/kaggle-asc24-v2/audio_model_metadata.json", "当前公开基线的可机读训练报告与验证指标。"],
    ["audio-training-data/artifacts/kaggle-asc24-v2/audio_model_card.md", "当前公开基线的模型卡与发布门禁状态。"],
  ],
  [4400, CONTENT_WIDTH - 4400],
  { alternate: "F7FAF8" },
));

// Appendix B
children.push(heading("附录 B：推荐遥测字段", 1));
children.push(paragraph("ESP32 每个分析窗口会通过 JSON 上报 microphone 对象。平台应至少保存下列字段，避免只保留一个“声音异常”布尔值而丢失后续审计能力。"));
children.push(table(
  ["字段", "含义"],
  [
    ["initialized / status / channel", "麦克风初始化、信号质量和 I2S 槽位状态。"],
    ["samples / readErrors", "采样量与 I2S 读取异常情况。"],
    ["rms / peak / dbfs / saturationRatio", "音量与失真质量指标。"],
    ["zeroCrossingRate / lowBandRatio / midBandRatio / highBandRatio", "可解释频率统计，便于回溯模型输入。"],
    ["snrDb / soundActive / vocalizationCandidate", "现场声音强度、噪声地板与基础事件状态。"],
    ["modelVersion / modelStatus", "模型版本与 feature_only/deployed 状态。"],
    ["eventId / eventLabel / eventScore / respiratoryCandidate", "候选事件身份、分数和风险筛查结果。"],
    ["captureInProgress / captureAvailable", "WAV 证据采集状态。"],
  ],
  [4300, CONTENT_WIDTH - 4300],
  { alternate: "F7FAF8" },
));

// Appendix C
children.push(heading("附录 C：参考文献与数据来源", 1));
children.push(paragraph([
  run("[1] Ferrari, A. et al. Cough sound description in relation to respiratory diseases in dairy calves. Preventive Veterinary Medicine, 2010. "),
  link("https://doi.org/10.1016/j.prevetmed.2010.06.013", "https://doi.org/10.1016/j.prevetmed.2010.06.013"),
]));
children.push(paragraph([
  run("[2] Vandermeulen, J. et al. Early recognition of bovine respiratory disease in calves using automated continuous monitoring of cough sounds. Computers and Electronics in Agriculture, 2016. "),
  link("https://doi.org/10.1016/j.compag.2016.07.014", "https://doi.org/10.1016/j.compag.2016.07.014"),
]));
children.push(paragraph([
  run("[3] Costa, J. H. C. et al. Symposium review: Precision technologies for dairy calves and management applications. Journal of Dairy Science, 2021. "),
  link("https://doi.org/10.3168/jds.2019-17885", "https://doi.org/10.3168/jds.2019-17885"),
]));
children.push(paragraph([
  run("[4] Limede, A. C. et al. Using audio-visual monitoring to evaluate immune and behavioral indicators to lipopolysaccharide challenge in beef cattle. Journal of Animal Science, 2025. "),
  link("https://doi.org/10.1093/jas/skaf345", "https://doi.org/10.1093/jas/skaf345"),
]));
children.push(paragraph([
  run("[5] Jobarteh, V. et al. Integrating multi-modal data fusion approaches for analysis of dairy cattle vocalizations. Frontiers in Veterinary Science, 2025. "),
  link("https://doi.org/10.3389/fvets.2025.1704031", "https://doi.org/10.3389/fvets.2025.1704031"),
]));
children.push(paragraph([
  run("[6] Schook, M. R. et al. Sound analysis in dairy cattle vocalisation as a potential welfare monitor. Computers and Electronics in Agriculture, 2015. "),
  link("https://doi.org/10.1016/j.compag.2015.08.028", "https://doi.org/10.1016/j.compag.2015.08.028"),
]));
children.push(paragraph([
  run("[7] Animal Sounds Classification (ASC24) 数据集，CC0-1.0。"),
  link("Kaggle source page", "https://www.kaggle.com/datasets/haithammoh/sounds-of-animals"),
]));
children.push(spacer());
children.push(callout(
  "引用说明",
  "以上论文用于说明声学事件连续监测和多模态复核的理论依据。项目没有把任何论文或公开数据集的结论扩展为针对本牛场的临床诊断性能声明。",
  COLORS.paleGold,
));

const doc = new Document({
  creator: "Codex",
  title: "数牧增效-牛声音健康风险筛查模型详细说明书",
  subject: "ESP32 INMP441 声学事件筛查与临床模型发布流程",
  description: "数牧增效项目牛声音健康风险筛查模型详细技术说明书。",
  styles: {
    default: {
      document: { run: { font: "Microsoft YaHei", size: 21, color: COLORS.ink } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 30, bold: true, color: COLORS.forest },
        paragraph: { spacing: { before: 300, after: 120 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 26, bold: true, color: COLORS.ink },
        paragraph: { spacing: { before: 220, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 23, bold: true, color: COLORS.ink },
        paragraph: { spacing: { before: 160, after: 90 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [{
          level: 0,
          format: LevelFormat.BULLET,
          text: "•",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 540, hanging: 260 } } },
        }],
      },
      {
        reference: "numbers",
        levels: [{
          level: 0,
          format: LevelFormat.DECIMAL,
          text: "%1.",
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 560, hanging: 280 } } },
        }],
      },
    ],
  },
  sections: [{
    properties: {
      page: {
        size: { width: PAGE_WIDTH, height: PAGE_HEIGHT },
        margin: { top: 1050, right: MARGIN_RIGHT, bottom: 1050, left: MARGIN_LEFT },
      },
    },
    headers: {
      default: new Header({
        children: [new Paragraph({
          children: [
            run("数牧增效 | 牛声音健康风险筛查模型详细说明书", { size: 17, color: COLORS.muted }),
          ],
          border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: COLORS.leaf, space: 1 } },
          spacing: { after: 40 },
        })],
      }),
    },
    footers: {
      default: new Footer({
        children: [new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [
            run("数牧增效  |  第 ", { size: 17, color: COLORS.muted }),
            new TextRun({ children: [PageNumber.CURRENT], font: "Microsoft YaHei", size: 17, color: COLORS.muted }),
            run(" 页", { size: 17, color: COLORS.muted }),
          ],
          spacing: { before: 40 },
        })],
      }),
    },
    children,
  }],
});

Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(output, buffer);
  console.log(output);
}).catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
