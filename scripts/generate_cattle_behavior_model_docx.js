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
  ImageRun,
  LevelFormat,
  Packer,
  PageBreak,
  PageNumber,
  Paragraph,
  SectionType,
  ShadingType,
  Table,
  TableCell,
  TableLayoutType,
  TableOfContents,
  TableRow,
  TabStopPosition,
  TabStopType,
  TextRun,
  VerticalAlign,
  WidthType,
} = require("docx");

const ROOT = path.resolve(__dirname, "..");
const OUTPUT = process.argv[2]
  ? path.resolve(process.argv[2])
  : path.join(ROOT, "牛行为识别模型详细说明书.docx");
const LIVE_SCREENSHOT = path.join(
  ROOT,
  "smart-cattle-frontend",
  "output",
  "playwright",
  "behavior-live-final.png",
);

const A4_WIDTH = 11906;
const A4_HEIGHT = 16838;
const MARGIN_X = 1276;
const MARGIN_TOP = 1134;
const MARGIN_BOTTOM = 1134;
const CONTENT_WIDTH = A4_WIDTH - MARGIN_X * 2;

const COLORS = {
  ink: "1D2924",
  muted: "66736D",
  primary: "236447",
  primaryDark: "173F30",
  green: "3C8C65",
  greenLight: "EAF4EE",
  gold: "C6922D",
  goldLight: "FBF3DF",
  blue: "32739A",
  blueLight: "EAF2F7",
  red: "A8463C",
  redLight: "F9ECEA",
  grayLight: "F3F5F4",
  line: "C9D1CD",
  white: "FFFFFF",
  black: "000000",
};

const thinBorder = { style: BorderStyle.SINGLE, size: 4, color: COLORS.line };
const gridBorders = {
  top: thinBorder,
  bottom: thinBorder,
  left: thinBorder,
  right: thinBorder,
  insideHorizontal: thinBorder,
  insideVertical: thinBorder,
};

function textRun(text, options = {}) {
  return new TextRun({
    text: String(text),
    font: options.font || "Microsoft YaHei",
    size: options.size,
    bold: options.bold,
    italics: options.italics,
    color: options.color,
    underline: options.underline,
    break: options.break,
  });
}

function body(text, options = {}) {
  const children = options.runs || [textRun(text, options)];
  return new Paragraph({
    style: options.style || "BodyCn",
    alignment: options.alignment,
    spacing: options.spacing,
    indent: options.indent,
    keepNext: options.keepNext,
    keepLines: options.keepLines,
    pageBreakBefore: options.pageBreakBefore,
    border: options.border,
    shading: options.shading,
    children,
  });
}

function noIndent(text, options = {}) {
  return body(text, { ...options, style: options.style || "BodyNoIndent" });
}

function heading1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [textRun(text, { bold: true })],
  });
}

function heading2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [textRun(text, { bold: true })],
  });
}

function heading3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [textRun(text, { bold: true })],
  });
}

function bulletList(items) {
  return items.map(
    (item) =>
      new Paragraph({
        style: "ListCn",
        numbering: { reference: "bullet-list", level: 0 },
        children: [textRun(item)],
      }),
  );
}

function numberedList(items, reference) {
  return items.map(
    (item) =>
      new Paragraph({
        style: "ListCn",
        numbering: { reference, level: 0 },
        children: [textRun(item)],
      }),
  );
}

function codeLines(lines) {
  return lines.map(
    (line, index) =>
      new Paragraph({
        style: "CodeLine",
        border: {
          left: { style: BorderStyle.SINGLE, size: 10, color: COLORS.primary },
          top: index === 0 ? thinBorder : undefined,
          right: thinBorder,
        },
        shading: { fill: "F1F4F2", type: ShadingType.CLEAR },
        children: [textRun(line || " ", { font: "Consolas", size: 17 })],
      }),
  );
}

function callout(title, text, tone = "green") {
  const palette = {
    green: [COLORS.primary, COLORS.greenLight],
    gold: [COLORS.gold, COLORS.goldLight],
    blue: [COLORS.blue, COLORS.blueLight],
    red: [COLORS.red, COLORS.redLight],
  }[tone];
  return new Paragraph({
    style: "Callout",
    border: { left: { style: BorderStyle.SINGLE, size: 18, color: palette[0] } },
    shading: { fill: palette[1], type: ShadingType.CLEAR },
    children: [
      textRun(`${title} `, { bold: true, color: palette[0] }),
      textRun(text),
    ],
  });
}

function valueRuns(value, options = {}) {
  if (Array.isArray(value)) {
    return value;
  }
  if (value && typeof value === "object" && value.runs) {
    return value.runs;
  }
  const spec = value && typeof value === "object" ? value : { text: value };
  return [
    textRun(spec.text === undefined ? "" : spec.text, {
      bold: spec.bold ?? options.bold,
      color: spec.color || options.color,
      size: spec.size || options.size,
      font: spec.font || options.font,
      italics: spec.italics,
    }),
  ];
}

function makeCell(value, width, options = {}) {
  const paragraphs =
    value && typeof value === "object" && value.paragraphs
      ? value.paragraphs
      : [
          new Paragraph({
            style: options.header ? "TableHeader" : "CellText",
            alignment: options.alignment || AlignmentType.LEFT,
            children: valueRuns(value, {
              bold: options.bold || options.header,
              color: options.header ? COLORS.white : COLORS.ink,
              size: options.size,
              font: options.font,
            }),
          }),
        ];
  return new TableCell({
    width: { size: width, type: WidthType.DXA },
    verticalAlign: options.verticalAlign || VerticalAlign.CENTER,
    borders: options.borders || gridBorders,
    shading: options.fill
      ? { fill: options.fill, type: ShadingType.CLEAR }
      : undefined,
    margins: { top: 100, bottom: 100, left: 130, right: 130 },
    children: paragraphs,
  });
}

function dataTable(headers, rows, widths, options = {}) {
  if (widths.reduce((sum, width) => sum + width, 0) !== CONTENT_WIDTH) {
    throw new Error(`Table widths must total ${CONTENT_WIDTH}: ${widths.join(",")}`);
  }
  const tableRows = [];
  if (headers) {
    tableRows.push(
      new TableRow({
        tableHeader: true,
        cantSplit: true,
        children: headers.map((header, index) =>
          makeCell(header, widths[index], {
            header: true,
            fill: options.headerFill || COLORS.primary,
            alignment: options.headerAlign || AlignmentType.CENTER,
          }),
        ),
      }),
    );
  }
  rows.forEach((row, rowIndex) => {
    const rowFill = options.zebra && rowIndex % 2 === 1 ? "F7F9F8" : undefined;
    tableRows.push(
      new TableRow({
        cantSplit: true,
        children: row.map((value, index) => {
          const cellOptions =
            value && typeof value === "object" && value.cell
              ? value.cell
              : {};
          return makeCell(value, widths[index], {
            fill: cellOptions.fill || rowFill,
            alignment:
              cellOptions.alignment ||
              (options.numericColumns && options.numericColumns.includes(index)
                ? AlignmentType.CENTER
                : AlignmentType.LEFT),
            bold: cellOptions.bold,
            size: cellOptions.size,
            verticalAlign: cellOptions.verticalAlign,
          });
        }),
      }),
    );
  });
  return new Table({
    width: { size: CONTENT_WIDTH, type: WidthType.DXA },
    columnWidths: widths,
    layout: TableLayoutType.FIXED,
    rows: tableRows,
  });
}

function caption(text) {
  return new Paragraph({
    style: "FigureCaption",
    alignment: AlignmentType.CENTER,
    children: [textRun(text, { color: COLORS.muted, size: 18 })],
  });
}

function spacer(points = 6) {
  return new Paragraph({ spacing: { after: points * 20 }, children: [] });
}

function splitWidth(total, count) {
  const base = Math.floor(total / count);
  const result = Array(count).fill(base);
  result[result.length - 1] += total - base * count;
  return result;
}

function blendWithWhite(hex, ratio) {
  const value = parseInt(hex, 16);
  const source = [(value >> 16) & 255, (value >> 8) & 255, value & 255];
  const channels = source.map((channel) =>
    Math.round(255 - (255 - channel) * ratio),
  );
  return channels.map((channel) => channel.toString(16).padStart(2, "0")).join("").toUpperCase();
}

function confusionMatrixTable() {
  const labels = ["采食", "卧姿反刍", "卧姿休息", "站立休息", "行走", "站立反刍"];
  const shortLabels = ["采食", "卧反", "卧休", "站休", "行走", "站反"];
  const matrix = [
    [1062, 3, 4, 10, 197, 25],
    [0, 186, 57, 29, 9, 18],
    [4, 37, 150, 19, 7, 20],
    [9, 67, 26, 128, 30, 143],
    [21, 3, 1, 6, 164, 7],
    [5, 41, 0, 21, 7, 96],
  ];
  const widths = [1750, 1267, 1267, 1267, 1267, 1267, 1269];
  const rows = matrix.map((values, rowIndex) => {
    const max = Math.max(...values);
    return [
      { text: labels[rowIndex], bold: true },
      ...values.map((value, columnIndex) => ({
        text: value,
        bold: rowIndex === columnIndex,
        cell: {
          alignment: AlignmentType.CENTER,
          fill:
            rowIndex === columnIndex
              ? blendWithWhite(COLORS.green, 0.35 + 0.55 * (value / max))
              : value === 0
                ? "FFFFFF"
                : blendWithWhite(COLORS.gold, 0.12 + 0.38 * (value / max)),
        },
      })),
    ];
  });
  return dataTable(["实际 / 预测", ...shortLabels], rows, widths, {
    headerFill: COLORS.primaryDark,
  });
}

function header() {
  return new Header({
    children: [
      new Paragraph({
        border: {
          bottom: { style: BorderStyle.SINGLE, size: 8, color: COLORS.primary },
        },
        tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
        children: [
          textRun("数牧增效 · 牛行为边缘识别", {
            bold: true,
            color: COLORS.primary,
            size: 18,
          }),
          textRun("\tpublic-neck-rf-v1", { color: COLORS.muted, size: 17 }),
        ],
      }),
    ],
  });
}

function footer() {
  return new Footer({
    children: [
      new Paragraph({
        border: {
          top: { style: BorderStyle.SINGLE, size: 4, color: COLORS.line },
        },
        tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
        children: [
          textRun("内部技术说明书 · 2026-07-19", {
            color: COLORS.muted,
            size: 16,
          }),
          textRun("\t第 ", { color: COLORS.muted, size: 16 }),
          new TextRun({ children: [PageNumber.CURRENT], color: COLORS.muted, size: 16 }),
          textRun(" 页", { color: COLORS.muted, size: 16 }),
        ],
      }),
    ],
  });
}

const coverChildren = [
  new Paragraph({
    spacing: { after: 2000 },
    border: {
      bottom: { style: BorderStyle.SINGLE, size: 24, color: COLORS.gold },
    },
    children: [
      textRun("数牧增效", { bold: true, size: 30, color: COLORS.primary }),
      textRun("  SMART CATTLE", { size: 18, color: COLORS.muted }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 260 },
    children: [
      textRun("牛三位置惯性传感器", {
        bold: true,
        size: 54,
        color: COLORS.primaryDark,
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 360 },
    children: [
      textRun("行为识别模型详细说明书", {
        bold: true,
        size: 54,
        color: COLORS.primaryDark,
      }),
    ],
  }),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 1200 },
    children: [
      textRun("颈部 MPU + 背部 ADXL345 + 腿部 MPU", {
        size: 25,
        color: COLORS.blue,
      }),
      textRun("  |  ", { size: 25, color: COLORS.line }),
      textRun("电脑训练与 ESP32 边缘部署", {
        size: 25,
        color: COLORS.gold,
      }),
    ],
  }),
  dataTable(
    null,
    [
      [{ text: "模型版本", bold: true }, "public-neck-rf-v1"],
      [{ text: "文档版本", bold: true }, "V1.0"],
      [{ text: "项目", bold: true }, "数牧增效智能牛舍监测平台"],
      [{ text: "编制日期", bold: true }, "2026 年 7 月 19 日"],
      [{ text: "文档状态", bold: true }, "实机基线版 / 可复现"],
    ],
    [2500, CONTENT_WIDTH - 2500],
    { zebra: true },
  ),
  spacer(24),
  callout(
    "模型定位：",
    "当前版本是“单传感器学习模型 + 三位置物理融合基线”。公开数据只训练颈部随机森林；背部和腿部信息通过姿态、活动强度规则参与融合，不是三传感器同步端到端学习模型。",
    "gold",
  ),
];

const bodyChildren = [];

bodyChildren.push(
  new Paragraph({
    style: "FrontTitle",
    children: [textRun("文档控制", { bold: true, color: COLORS.primaryDark })],
  }),
  dataTable(
    ["版本", "日期", "变更内容", "依据"],
    [
      [
        "V1.0",
        "2026-07-19",
        "形成训练、评估、三位置融合、ESP32 部署、网站链路和重训规范的完整说明",
        "现有代码、训练报告、实机页面",
      ],
    ],
    [1000, 1500, 4300, CONTENT_WIDTH - 6800],
  ),
  spacer(10),
  new Paragraph({
    style: "FrontTitle",
    children: [textRun("摘要", { bold: true, color: COLORS.primaryDark })],
  }),
  body(
    "本说明书描述数牧增效项目中牛行为识别模型的完整工程实现。系统在一块 ESP32 上连接三处惯性传感器：颈部 MPU-9250/6500、背部 ADXL345、腿部 MPU-9250/6500。电脑端使用公开的单惯性传感器数据训练 30 棵紧凑随机森林，并导出为 C++ 头文件；ESP32 以 20 Hz 读取三处传感器，每约 2 秒汇总一次颈部模型投票、背部倾角和腿部活动证据，输出六类行为及融合置信度。",
  ),
  body(
    "公开数据测试集采用按连续行为片段隔离的 80/20 拆分，得到 68.38% 准确率和 57.49% 宏平均 F1。该结果证明模型可以作为板端联调和数据采集基线，但尚不足以代表真实牧场跨牛只泛化能力。正式应用前必须采集颈、背、腿同步数据，按牛只隔离训练与测试，并重新校准安装方向和融合阈值。",
  ),
  dataTable(
    ["数据", "模型", "边缘运行", "当前验证"],
    [
      [
        { text: "13,088 行 / 6 类行为", bold: true },
        { text: "30 棵树 / 11,012 节点", bold: true },
        { text: "20 Hz / 约 2 s 每窗口", bold: true },
        { text: "三节点 3/3 在线 / 网页实时显示", bold: true },
      ],
    ],
    splitWidth(CONTENT_WIDTH, 4),
    { headerFill: COLORS.primaryDark, headerAlign: AlignmentType.CENTER },
  ),
  new Paragraph({ children: [new PageBreak()] }),
  new TableOfContents("目录", {
    hyperlink: true,
    headingStyleRange: "1-3",
  }),
  new Paragraph({
    style: "TocNote",
    children: [
      textRun("目录采用 Word 域自动生成，页码已在交付文件中更新。", {
        color: COLORS.muted,
        size: 17,
      }),
    ],
  }),
);

bodyChildren.push(
  heading1("1 文档范围与关键结论"),
  heading2("1.1 建设目标"),
  body(
    "本模型面向牛只采食、反刍、休息和行走等日常行为的连续监测。目标不是替代兽医诊断，而是在低功耗 ESP32 节点上形成可实时运行的行为基线，为异常行为时长、活动骤降、长期卧地和健康风险融合提供结构化数据。",
  ),
  heading2("1.2 当前实现的四个层次"),
  ...bulletList([
    "数据层：审计并使用 dataset_6.csv 中 13,088 行单位置惯性数据和六类标签。",
    "模型层：电脑训练紧凑随机森林，输出 public-neck-rf-v1，并转换为 ESP32 可直接编译的 C++ 数组。",
    "融合层：颈部模型提供学习得分，背部 ADXL345 提供躺卧倾角证据，腿部 MPU 提供行走活动证据。",
    "应用层：ESP32 串口输出 JSON，Spring Boot 后端接收并经 WebSocket 推送，Vue 页面实时展示三位置数据和行为结果。",
  ]),
  heading2("1.3 可声明结果与不可声明结果"),
  dataTable(
    ["类别", "可以准确表述", "不能据此表述"],
    [
      [
        { text: "训练数据", bold: true },
        "公开单位置惯性数据，共六类行为",
        "颈、背、腿三位置同步采集数据",
      ],
      [
        { text: "学习模型", bold: true },
        "颈部 MPU 上运行的 30 树随机森林",
        "端到端三传感器深度学习模型",
      ],
      [
        { text: "三位置使用", bold: true },
        "颈部投票与背部姿态、腿部活动的工程规则融合",
        "背部和腿部规则已经从同步标注样本学习得到",
      ],
      [
        { text: "评估", bold: true },
        "按连续行为片段隔离的公开数据测试结果",
        "跨牛只、跨牧场或医疗级性能",
      ],
    ],
    [1500, 3850, CONTENT_WIDTH - 5350],
    { zebra: true },
  ),
  callout(
    "关键边界：",
    "68.38% 准确率和 57.49% 宏平均 F1 只对应公开 CSV 的当前拆分。由于数据没有 cow_id、session_id 和同步三位置字段，这两个指标不能外推为真实牛群部署精度。",
    "red",
  ),
);

bodyChildren.push(
  heading1("2 三位置硬件架构"),
  heading2("2.1 传感器职责"),
  dataTable(
    ["安装位置", "器件与地址", "采集量", "模型职责"],
    [
      [
        { text: "颈部", bold: true, color: COLORS.green },
        "MPU-9250/6500，0x68",
        "三轴加速度 + 三轴角速度",
        "输入公开数据训练的随机森林；反映低头采食、反刍和颈部活动",
      ],
      [
        { text: "背部", bold: true, color: COLORS.gold },
        "ADXL345，0x53",
        "三轴加速度",
        "计算背部倾角和活动强度；为躺卧/站立提供物理证据",
      ],
      [
        { text: "腿部", bold: true, color: COLORS.blue },
        "MPU-9250/6500，0x69",
        "三轴加速度 + 三轴角速度",
        "计算腿部活动强度；为行走提供物理证据",
      ],
    ],
    [1200, 2200, 2200, CONTENT_WIDTH - 5600],
    { zebra: true },
  ),
  heading2("2.2 I2C 接线"),
  body(
    "三个运动传感器共用同一条 I2C 总线：SDA 接 ESP32 GPIO21，SCL 接 GPIO22，全部使用稳定的 3.3 V 电源并共地。通过地址选择脚保证三个地址互不冲突。",
  ),
  dataTable(
    ["模块", "供电", "总线", "地址选择与其余引脚"],
    [
      [
        "颈部 MPU 0x68",
        "VCC→3V3；GND→GND",
        "SDA→D21；SCL→D22",
        "AD0→GND；NCS/CS→3V3；EDA、ECL、INT、FSYNC 不接",
      ],
      [
        "背部 ADXL345 0x53",
        "VCC→3V3；GND→GND",
        "SDA→D21；SCL→D22",
        "CS→3V3 进入 I2C；SDO/ALT ADDRESS→GND 选择 0x53",
      ],
      [
        "腿部 MPU 0x69",
        "VCC→3V3；GND→GND",
        "SDA→D21；SCL→D22",
        "AD0→3V3；NCS/CS→3V3；EDA、ECL、INT、FSYNC 不接",
      ],
    ],
    [1700, 1900, 1900, CONTENT_WIDTH - 5500],
    { zebra: true },
  ),
  callout(
    "关于腿部 AD0：",
    "腿部 MPU 的 AD0 直接接 3.3 V 是正确的，这会把地址从 0x68 切换为 0x69。若扫描仍显示两个 0x68，应检查 AD0 是否真正拉高以及模块丝印是否对应 AD0。",
    "blue",
  ),
  heading2("2.3 安装与坐标方向"),
  ...bulletList([
    "颈部节点固定在颈圈上，避免自由摆动；记录板上 X/Y/Z 轴相对牛体前后、左右、上下的方向。",
    "背部 ADXL345 需要与背部刚性固定，静止站立时用于建立零倾角基准；绑带松动会直接破坏躺卧判断。",
    "腿部节点应固定在同一条腿和相同高度，避免碰撞关节；不同安装位置需要重新标定活动阈值。",
    "当前颈部模型直接使用原始轴向特征，没有旋转不变性。安装方向变化可能比算法参数变化影响更大。",
  ]),
  heading2("2.4 电源与总线工程要求"),
  ...bulletList([
    "不要把两块开发板的 3.3 V 稳压输出直接并联。使用单一、容量足够的 3.3 V 稳压源，并将所有模块 GND 共地。",
    "长线场景在主控附近放置 10 µF 与 0.1 µF 去耦，SDA/SCL 采用 2.2 kΩ～4.7 kΩ 上拉到 3.3 V。",
    "I2C 线尽量短并与蜂鸣器、电机、电源开关线分开；必要时降低 I2C 时钟或使用总线缓冲器。",
    "上线前扫描必须同时出现 0x53、0x68、0x69；任何一个缺失时固件输出 sensors_missing。",
  ]),
);

bodyChildren.push(
  heading1("3 数据集来源与审计"),
  heading2("3.1 数据来源"),
  body(
    "当前训练文件为本地 free_datasets/cattle_classification_github_andssuu/data/dataset_6.csv，对应开源仓库 cattle_classification。项目内清单给出的原始来源如下：",
  ),
  new Paragraph({
    style: "BodyNoIndent",
    children: [
      textRun("来源链接：", { bold: true }),
      new ExternalHyperlink({
        link: "https://github.com/andssuu/cattle_classification",
        children: [
          textRun("https://github.com/andssuu/cattle_classification", {
            color: COLORS.blue,
            underline: { type: "single" },
          }),
        ],
      }),
    ],
  }),
  noIndent("文件 SHA256：1F5853A7FAE08227584218965885398D3BECF7402BDC663C77C2EAA875409562", {
    font: "Consolas",
    size: 18,
  }),
  callout(
    "来源审计结论：",
    "本地 README 只说明该数据用于基于惯性传感器的牛行为分类，没有提供可用于当前工程审计的牛只编号、采样频率、安装方向、会话边界和许可证细节。正式对外发布模型前，应进一步核对原仓库数据许可和论文采集协议。",
    "gold",
  ),
  heading2("3.2 原始字段与实际使用字段"),
  dataTable(
    ["字段组", "原始列", "当前处理", "原因"],
    [
      [
        "加速度",
        "acc_x, acc_y, acc_z",
        "除以 16384，转为 g，作为模型特征",
        "与 MPU ±2 g 配置一致",
      ],
      [
        "陀螺仪",
        "gir_x, gir_y, gir_z",
        "除以 131，转为 °/s，作为模型特征",
        "与 MPU ±250 °/s 配置一致",
      ],
      [
        "磁力计",
        "mag_x, mag_y, mag_z",
        "忽略",
        "MPU-6500 无磁力计，且当前部署不依赖该量",
      ],
      [
        "速度",
        "displacement_speed",
        "忽略",
        "ESP32 节点没有同源速度输入，避免训练/部署特征不一致",
      ],
      ["标签", "label", "映射为 0～5", "用于监督训练和评估"],
    ],
    [1300, 2200, 3000, CONTENT_WIDTH - 6500],
    { zebra: true },
  ),
  heading2("3.3 规模与类别分布"),
  body(
    "CSV 共 13,089 行（含表头），有效样本 13,088 行。标签序列按相邻标签变化划分为 671 个连续行为片段。类别存在明显不平衡，采食占 43.80%，站立反刍仅占 6.36%。",
  ),
  dataTable(
    ["英文标签", "中文名称", "样本数", "占比"],
    [
      ["Grazing", "采食", "5,732", "43.80%"],
      ["Lying-Ruminating", "卧姿反刍", "2,034", "15.54%"],
      ["Lying-Resting", "卧姿休息", "1,702", "13.00%"],
      ["Standing-Resting", "站立休息", "1,559", "11.91%"],
      ["Walking", "行走", "1,229", "9.39%"],
      ["Standing-Ruminating", "站立反刍", "832", "6.36%"],
    ],
    [2700, 2500, 2000, CONTENT_WIDTH - 7200],
    { zebra: true, numericColumns: [2, 3] },
  ),
  heading2("3.4 数据限制"),
  ...bulletList([
    "只有一组惯性特征，没有 neck/body/leg 三组同步通道。",
    "没有 cow_id，无法实施按牛只独立测试，也无法判断同一牛是否同时出现在训练和测试中。",
    "没有 timestamp 和明确采样频率，训练数据与 ESP32 20 Hz 运行频率之间存在域差异风险。",
    "没有安装方向和传感器量程元数据，当前单位换算依赖 MPU 常见 ±2 g、±250 °/s 假设。",
    "行为过渡边界由标签变化推断，无法验证人工标注延迟和过渡样本质量。",
  ]),
);

bodyChildren.push(
  heading1("4 数据预处理与防泄漏拆分"),
  heading2("4.1 单位统一"),
  body(
    "训练脚本与 ESP32 固件使用相同量纲。原始加速度按 16,384 LSB/g 转换，原始角速度按 131 LSB/(°/s) 转换。板端 MPU 先转换为 m/s²，再除以标准重力加速度 9.80665 得到 g，因此训练与推理输入一致。",
  ),
  ...codeLines([
    "ax_g = acc_x_raw / 16384.0",
    "ay_g = acc_y_raw / 16384.0",
    "az_g = acc_z_raw / 16384.0",
    "gx_dps = gir_x_raw / 131.0",
    "gy_dps = gir_y_raw / 131.0",
    "gz_dps = gir_z_raw / 131.0",
  ]),
  heading2("4.2 六维输入顺序"),
  dataTable(
    ["索引", "特征", "单位", "ESP32 来源"],
    [
      ["0", "ax_g", "g", "颈部 MPU ax / 9.80665"],
      ["1", "ay_g", "g", "颈部 MPU ay / 9.80665"],
      ["2", "az_g", "g", "颈部 MPU az / 9.80665"],
      ["3", "gx_dps", "°/s", "颈部 MPU gx"],
      ["4", "gy_dps", "°/s", "颈部 MPU gy"],
      ["5", "gz_dps", "°/s", "颈部 MPU gz"],
    ],
    [1000, 1900, 1600, CONTENT_WIDTH - 4500],
    { zebra: true, numericColumns: [0] },
  ),
  heading2("4.3 连续片段拆分"),
  body(
    "脚本顺序扫描标签。当当前标签与上一行标签不同，就新建一个 group_id；同一连续行为片段内的全部样本保持在同一侧。随后针对每一类打乱片段编号，并取约 20% 片段进入测试集。最终训练集 10,476 行，测试集 2,612 行。",
  ),
  ...numberedList(
    [
      "逐行读取 CSV，仅保留六个已知标签。",
      "按标签变化生成 671 个连续片段编号。",
      "每个类别独立打乱片段，抽取约 20% 片段作为测试片段。",
      "整个片段一次性划入训练集或测试集，禁止将同一片段随机拆行。",
      "固定随机种子 20260719，保证结果可重复。",
    ],
    "steps-split",
  ),
  heading2("4.4 为什么不能随机拆行"),
  body(
    "连续采样相邻行高度相关。如果随机把相邻行分到训练和测试，测试集会含有与训练样本几乎相同的时刻，导致指标虚高。按连续片段拆分降低了这种局部泄漏。",
  ),
  callout(
    "剩余风险：",
    "片段拆分仍不是按牛只拆分。若多个片段来自同一头牛或同一次会话，个体特征仍可能同时出现在训练和测试中。未来三位置数据必须保留 cow_id，并优先采用按牛只隔离的验证。",
    "red",
  ),
);

bodyChildren.push(
  heading1("5 紧凑随机森林模型"),
  heading2("5.1 选择原因"),
  body(
    "当前主控为经典 ESP32，需同时处理 I2C、心率血氧、麦克风、红外测温、OLED、串口和执行器。紧凑随机森林不依赖 TensorFlow Lite 运行时，推理只包含阈值比较、树遍历和投票，部署路径短、结果可复现、调试透明，适合作为第一版板端基线。",
  ),
  heading2("5.2 超参数"),
  dataTable(
    ["参数", "值", "工程含义"],
    [
      ["模型版本", "public-neck-rf-v1", "公开单传感器颈部基线"],
      ["树数量", "30", "每个样本由 30 棵树投票"],
      ["最大深度", "10", "单树最多约 10 次节点判断"],
      ["最小叶节点样本数", "8", "抑制过细分裂"],
      ["每节点候选特征", "3 / 6", "随机选择三个特征寻找最优分裂"],
      ["每类每树抽样", "800", "六类平衡抽样，每棵树训练 4,800 条"],
      ["抽样方式", "有放回", "形成类别平衡 bootstrap 样本"],
      ["随机种子", "20260719", "保证拆分、抽样和模型可复现"],
      ["总节点数", "11,012", "导出后 30 棵树全部节点总和"],
    ],
    [2600, 2200, CONTENT_WIDTH - 4800],
    { zebra: true },
  ),
  heading2("5.3 决策树训练逻辑"),
  body(
    "每个节点在随机选出的三个候选特征中枚举可行阈值，计算左右子节点加权 Gini 不纯度，选取不纯度最小的分裂。达到最大深度、样本不足以形成两个最小叶节点或节点内仅剩一个类别时停止。叶节点保存该节点样本数最多的类别编号。",
  ),
  ...codeLines([
    "Gini(S) = 1 - Σ p_k²",
    "Impurity(split) = (n_left × Gini(left) + n_right × Gini(right)) / n_total",
    "leaf_value = argmax_k count(k)",
  ]),
  heading2("5.4 类别平衡策略"),
  body(
    "原始采食样本远多于站立反刍。每棵树不是按原始比例抽样，而是从每类训练索引中有放回抽取 800 条，使每棵树的六类先验相同。这提升少数类召回，但也会增加少数类预测的假阳性；当前行走高召回、低精确率就是这一权衡的表现之一。",
  ),
  heading2("5.5 单点分类与窗口投票"),
  body(
    "随机森林本身一次接收一个时刻的六维颈部特征并输出一个类别。ESP32 在约 2 秒窗口内对每个 20 Hz 样本调用一次模型，累计六类票数，再以票数比例作为颈部基础得分。这种时间平滑发生在固件层，不是训练脚本中的滑窗特征模型。",
  ),
);

bodyChildren.push(
  heading1("6 电脑训练、评估与模型导出"),
  heading2("6.1 文件位置"),
  dataTable(
    ["用途", "路径"],
    [
      [
        "训练脚本",
        "D:\\table\\shumuzengxiao\\牛行为识别数据集\\esp32_motion_model\\train_export_model.py",
      ],
      [
        "训练报告",
        "D:\\table\\shumuzengxiao\\牛行为识别数据集\\esp32_motion_model\\training_report.json",
      ],
      [
        "模型头文件",
        "D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\\include\\cattle_behavior_model.h",
      ],
      [
        "固件入口",
        "D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\\src\\main.cpp",
      ],
    ],
    [1900, CONTENT_WIDTH - 1900],
    { zebra: true },
  ),
  heading2("6.2 训练命令"),
  ...codeLines([
    "cd D:\\table\\shumuzengxiao\\牛行为识别数据集\\esp32_motion_model",
    "py train_export_model.py",
  ]),
  body(
    "脚本只依赖 Python 标准库和 NumPy，不依赖 scikit-learn。默认参数会加载 dataset_6.csv、训练随机森林、打印评估指标、覆盖 training_report.json，并把模型导出到固件 include 目录。",
  ),
  heading2("6.3 可调训练参数"),
  ...codeLines([
    "py train_export_model.py --trees 30 --depth 10 --min-leaf 8 --samples-per-class 800 --seed 20260719",
    "py train_export_model.py --dataset <csv路径> --output <头文件路径>",
  ]),
  heading2("6.4 C++ 导出格式"),
  body(
    "每个节点包含 threshold、left、right、feature 和 value。内部节点使用 feature≥0，比较 features[feature]≤threshold 后跳转左右节点；叶节点使用 feature=-1，并在 value 中保存类别编号。30 棵树分别导出为 static const Node 数组，再由 kTrees 指针表索引。",
  ),
  dataTable(
    ["成员", "类型", "作用"],
    [
      ["threshold", "float", "内部节点分裂阈值"],
      ["left / right", "int16_t", "左右子节点数组索引"],
      ["feature", "int8_t", "0～5 表示输入特征；-1 表示叶节点"],
      ["value", "uint8_t", "叶节点类别 0～5"],
    ],
    [2100, 1800, CONTENT_WIDTH - 3900],
    { zebra: true },
  ),
  heading2("6.5 版本与可复现性"),
  ...bulletList([
    "模型版本写入 cattle_behavior_model::kVersion，并随每条行为遥测发送到网站。",
    "training_report.json 固化数据路径、特征顺序、拆分方式、样本数、树数量、节点数和测试指标。",
    "每次更换数据、特征顺序、标签映射、阈值或树参数，都应升级模型版本并保留旧头文件和报告。",
    "对外发布时应同时保存 CSV 哈希、训练脚本提交版本、配置文件和固件二进制哈希。",
  ]),
);

bodyChildren.push(
  heading1("7 模型评估结果"),
  heading2("7.1 总体指标"),
  dataTable(
    ["测试样本", "准确率", "宏平均 F1", "评估拆分"],
    [
      [
        { text: "2,612", bold: true },
        { text: "68.38%", bold: true, color: COLORS.primary },
        { text: "57.49%", bold: true, color: COLORS.gold },
        "按连续行为片段分层隔离 80/20",
      ],
    ],
    [1800, 1800, 1900, CONTENT_WIDTH - 5500],
    { headerFill: COLORS.primaryDark, headerAlign: AlignmentType.CENTER },
  ),
  body(
    "准确率是全部测试样本中预测正确的比例；宏平均 F1 先计算每一类 F1，再对六类等权平均，因此更能反映少数类性能。当前宏平均 F1 明显低于准确率，说明类别间性能不均衡。",
  ),
  ...codeLines([
    "Precision = TP / (TP + FP)",
    "Recall = TP / (TP + FN)",
    "F1 = 2 × Precision × Recall / (Precision + Recall)",
    "Macro-F1 = mean(F1_0 ... F1_5)",
  ]),
  heading2("7.2 分类别指标"),
  dataTable(
    ["类别", "Precision", "Recall", "F1", "Support"],
    [
      ["采食", "96.46%", "81.63%", "88.43%", "1,301"],
      ["卧姿反刍", "55.19%", "62.21%", "58.49%", "299"],
      ["卧姿休息", "63.03%", "63.29%", "63.16%", "237"],
      ["站立休息", "60.09%", "31.76%", "41.56%", "403"],
      ["行走", "39.61%", "81.19%", "53.25%", "202"],
      ["站立反刍", "31.07%", "56.47%", "40.08%", "170"],
    ],
    [2450, 1700, 1700, 1700, CONTENT_WIDTH - 7550],
    { zebra: true, numericColumns: [1, 2, 3, 4] },
  ),
  heading2("7.3 混淆矩阵"),
  body(
    "行表示真实类别，列表示预测类别。绿色对角线为正确分类，浅金色为误分类。类别顺序与模型头文件完全一致。",
  ),
  confusionMatrixTable(),
  caption("表 7-1  public-neck-rf-v1 测试集混淆矩阵（共 2,612 条）"),
  heading2("7.4 主要误差模式"),
  ...bulletList([
    "采食表现最好，F1 为 88.43%；但仍有 197 条采食被识别为行走，占真实采食样本的约 15.14%。",
    "行走召回率 81.19%，但精确率只有 39.61%，说明模型倾向于把其他活跃行为判为行走。",
    "站立休息召回率只有 31.76%，其中 143 条被判为站立反刍，67 条被判为卧姿反刍。",
    "站立反刍精确率 31.07%，与站立休息、卧姿反刍存在明显混淆，说明单时刻原始轴特征不足以稳定区分是否反刍。",
    "两种卧姿类别 F1 约 58%～63%，背部倾角融合可加强躺卧大类，但不能单独区分反刍和休息。",
  ]),
  callout(
    "指标解释：",
    "网站显示的融合置信度不是经过概率校准的真实正确率。它由颈部票数比例和规则加权后归一化得到，只适合排序和阈值提示，不能把“87%”解释为该行为有 87% 的统计正确概率。",
    "gold",
  ),
);

bodyChildren.push(
  heading1("8 三位置物理融合算法"),
  heading2("8.1 活动强度"),
  body(
    "颈、背、腿活动强度都由相邻采样时刻三轴加速度差的欧氏距离计算，并在当前窗口内取平均。加速度单位为 m/s²。该量随采样频率和固定方式变化，因此阈值只对当前 20 Hz 和当前绑带条件有效。",
  ),
  ...codeLines([
    "delta_t = sqrt((ax_t-ax_t-1)² + (ay_t-ay_t-1)² + (az_t-az_t-1)²)",
    "activity = (1 / N) × Σ delta_t",
  ]),
  heading2("8.2 背部倾角"),
  body(
    "ADXL345 使用重力方向估计倾角。固件取 Z 轴绝对值与加速度模长之比，站立且 Z 轴接近重力方向时倾角接近 0°，传感器平面翻转到接近水平时倾角接近 90°。",
  ),
  ...codeLines([
    "magnitude = sqrt(ax² + ay² + az²)",
    "bodyTiltDeg = acos(|az| / magnitude) × 180 / π",
    "lyingPosture = bodyTiltDeg >= 55°",
  ]),
  heading2("8.3 颈部窗口投票"),
  body(
    "窗口内每个有效颈部样本得到一个 0～5 类别。基础得分等于该类票数除以窗口有效模型样本数。颈部模型状态取票数最多的类别，颈部模型置信度取其票数比例。",
  ),
  ...codeLines([
    "baseScore[k] = votes[k] / modelSamples",
    "neckModelState = argmax_k votes[k]",
    "neckModelConfidence = max(votes) / modelSamples",
  ]),
  heading2("8.4 融合阈值"),
  dataTable(
    ["配置/条件", "当前值", "用途", "位置"],
    [
      ["BODY_LIE_TILT_DEG", "55°", "判定躺卧姿态", "config.h"],
      ["WALK_LEG_ACTIVITY", "1.20", "腿部行走活动门限", "config.h"],
      ["VIGOROUS_LEG_ACTIVITY", "3.00", "行走证据增益归一化上限", "config.h"],
      ["ACTIVE_NECK_ACTIVITY", "0.65", "颈部活跃且腿不走时加强采食", "config.h"],
      ["bodyActivity", "0.90", "背部与腿同时活跃时加强行走", "main.cpp"],
      ["legActivity", "0.60", "上述联合活动条件的腿部门限", "main.cpp"],
    ],
    [2700, 1500, 3300, CONTENT_WIDTH - 7500],
    { zebra: true },
  ),
  heading2("8.5 规则与权重"),
  dataTable(
    ["条件", "得分调整"],
    [
      [
        "背部倾角 ≥ 55°",
        "卧姿反刍 +0.18，卧姿休息 +0.18；采食 ×0.65，站立休息 ×0.45，行走 ×0.35，站立反刍 ×0.45",
      ],
      [
        "背部倾角 < 55°",
        "卧姿反刍 ×0.60，卧姿休息 ×0.60",
      ],
      [
        "腿部活动 ≥ 1.20",
        "行走 +[0.25 + 0.20 × clamp(腿部活动/3.00, 0, 1)]",
      ],
      ["腿部活动 < 1.20", "行走 ×0.70"],
      [
        "背部活动 ≥ 0.90 且腿部活动 ≥ 0.60",
        "行走 +0.10",
      ],
      [
        "颈部活动 ≥ 0.65 且腿部活动 < 1.20",
        "采食 +0.10",
      ],
    ],
    [3100, CONTENT_WIDTH - 3100],
    { zebra: true },
  ),
  heading2("8.6 最终类别与置信度"),
  ...codeLines([
    "behavior = argmax_k adjustedScore[k]",
    "confidence = max(adjustedScore) / Σ adjustedScore[k]",
  ]),
  body(
    "三个运动传感器必须全部在线，且窗口内至少有一个运动样本和一个模型样本；否则输出 state=sensors_missing、confidence=0，并清空窗口。该设计优先保证数据完整性，避免在缺少背部或腿部证据时仍输出看似正常的融合结果。",
  ),
  callout(
    "实现性质：",
    "这些权重是保守工程基线，并未从同步三位置标注数据优化。实牛数据采集完成后，应使用验证集网格搜索或贝叶斯优化校准阈值，或由真正的三位置学习模型替代规则。",
    "red",
  ),
);

bodyChildren.push(
  heading1("9 ESP32 推理与资源占用"),
  heading2("9.1 时间调度"),
  dataTable(
    ["任务", "周期", "频率/窗口", "说明"],
    [
      ["三位置运动采样", "50 ms", "20 Hz", "读取 0x68、0x53、0x69 并执行颈部模型"],
      ["行为分类与遥测", "2,000 ms", "约 0.5 Hz", "融合约 38～40 个有效样本并输出 JSON"],
      ["MAX30102 轮询", "20 ms", "50 Hz 调度", "使用非阻塞 FIFO，避免阻塞运动采样"],
      ["I2C 恢复", "5,000 ms", "按需", "传感器掉线时周期性尝试恢复"],
    ],
    [2300, 1500, 1900, CONTENT_WIDTH - 5700],
    { zebra: true },
  ),
  heading2("9.2 一次窗口的执行顺序"),
  ...numberedList(
    [
      "读取颈部 MPU、背部 ADXL345、腿部 MPU；任一读取失败则标记 sensors_missing。",
      "分别计算三位置相邻加速度差，并累计活动强度。",
      "把颈部加速度从 m/s² 转为 g，连同 °/s 角速度组成六维输入。",
      "遍历 30 棵树得到单样本类别，并增加该类窗口票数。",
      "约 2 秒后计算平均活动、背部倾角和颈部票数比例。",
      "应用躺卧、行走和采食规则，取最高得分并归一化置信度。",
      "把结果写入 JSON、OLED 和实时网站链路，然后清空累计器开始下一窗口。",
    ],
    "steps-runtime",
  ),
  heading2("9.3 计算复杂度"),
  body(
    "最大树深为 10，每个颈部样本最多约 30×10=300 次节点比较；20 Hz 下约 6,000 次比较/秒。相比 240 MHz ESP32 的处理能力，该计算量很小。模型不申请大型张量缓冲区，窗口只保存票数、累加值和最新传感器读数。",
  ),
  heading2("9.4 编译资源实测"),
  dataTable(
    ["项目", "实测占用", "可用上限", "比例"],
    [
      ["RAM", "27,348 B", "327,680 B", "8.3%"],
      ["Flash 程序区", "494,649 B", "1,310,720 B", "37.7%"],
      ["固件二进制", "495,008 B", "—", "firmware.bin 文件大小"],
      ["森林节点数组", "132,144 B（129.05 KiB）", "—", "30 棵树静态常量合计"],
    ],
    [2200, 2600, 2100, CONTENT_WIDTH - 6900],
    { zebra: true },
  ),
  body(
    "上述 RAM/Flash 数字来自 2026-07-19 对 env:demo_esp32 的 PlatformIO release 构建。节点数组为 ELF 符号中 30 个 kTree 数组的合计，未包含树指针表和推理函数。",
  ),
  heading2("9.5 初始化与在线判定"),
  ...bulletList([
    "ADXL345 读取 DEVID 寄存器 0x00，必须等于 0xE5；随后配置全分辨率 ±16 g 和测量模式。",
    "MPU 读取 WHO_AM_I 0x75，接受 0x68、0x70、0x71、0x73、0x75，并配置唤醒、±250 °/s、±2 g。",
    "串口启动信息打印 ADXL345、MPU@68、MPU@69 状态和行为模型版本、树数量。",
    "JSON 中 mpu0、adxl345、mpu1 三个布尔值是网站判断在线 3/3 的直接依据。",
  ]),
);

bodyChildren.push(
  heading1("10 串口、后端与网站实时链路"),
  heading2("10.1 数据链路"),
  dataTable(
    ["阶段", "接口", "当前实现"],
    [
      ["ESP32 → 电脑", "USB 串口 115200, 8N1", "每约 2 秒输出一行 UTF-8 JSON"],
      ["电脑串口服务", "Spring Boot + jSerialComm", "过滤非 JSON 日志，附加 receivedAt，保留最近 120 条"],
      ["后端查询", "GET /api/telemetry/snapshot", "返回连接状态、最新一条和历史窗口"],
      ["实时推送", "WebSocket /ws/telemetry", "广播 telemetry、status 和 command_ack 事件"],
      ["网站页面", "Vue /behavior", "展示行为、置信度、三位置轴数据、趋势和最近记录"],
    ],
    [2100, 2600, CONTENT_WIDTH - 4700],
    { zebra: true },
  ),
  heading2("10.2 行为 JSON 样例"),
  ...codeLines([
    "{",
    "  \"deviceId\": \"demo_esp32_01\",",
    "  \"seq\": 553,",
    "  \"mpu0\": true, \"adxl345\": true, \"mpu1\": true,",
    "  \"behavior\": {",
    "    \"state\": \"lying_resting\",",
    "    \"confidence\": 0.87,",
    "    \"model\": \"public-neck-rf-v1\",",
    "    \"fusion\": \"neck_ml+body_tilt+leg_activity\",",
    "    \"windowSamples\": 38,",
    "    \"neckModelState\": \"lying_resting\",",
    "    \"neckModelConfidence\": 1.00,",
    "    \"bodyTiltDeg\": 72.8,",
    "    \"neckActivity\": 0.05,",
    "    \"bodyActivity\": 0.18,",
    "    \"legActivity\": 0.05",
    "  }",
    "}",
  ]),
  heading2("10.3 关键字段说明"),
  dataTable(
    ["字段", "类型", "含义"],
    [
      ["behavior.state", "string", "融合后的六类行为或 sensors_missing"],
      ["behavior.confidence", "number", "规则调整后最高得分占总得分比例"],
      ["behavior.model", "string", "板端模型版本 public-neck-rf-v1"],
      ["behavior.windowSamples", "integer", "上一识别窗口的有效三位置样本数"],
      ["behavior.neckModelState", "string", "未融合前的颈部窗口投票结果"],
      ["behavior.neckModelConfidence", "number", "颈部最高票数/模型样本数"],
      ["behavior.bodyTiltDeg", "number/null", "背部倾角，传感器无效时为 null"],
      ["behavior.*Activity", "number/null", "颈部、背部、腿部平均活动强度"],
      ["mpu0/adxl345/mpu1", "boolean", "颈、背、腿节点在线状态"],
    ],
    [3000, 1600, CONTENT_WIDTH - 4600],
    { zebra: true },
  ),
  heading2("10.4 实机页面"),
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 120, after: 80 },
    children: [
      new ImageRun({
        type: "png",
        data: fs.readFileSync(LIVE_SCREENSHOT),
        transformation: { width: 610, height: 424 },
        altText: {
          title: "牛行为实时页面",
          description: "COM19 实机数据下的三位置行为识别页面，三个运动节点均在线",
          name: "behavior-live-final",
        },
      }),
    ],
  }),
  caption("图 10-1  COM19 实机遥测页面：三位置节点在线 3/3，模型与融合证据实时显示"),
  heading2("10.5 串口选择"),
  body(
    "项目配置默认端口仍写为 COM18，但本次整机实测由后端自动识别为 COM19。TelemetryService 会先寻找配置端口；若系统只有一个串口，或端口描述含 USB/UART/CP210/CH340/Silicon Labs，则可自动选中。上传固件时建议显式指定 COM19，避免端口变化造成误操作。",
  ),
);

bodyChildren.push(
  heading1("11 实机验证与验收"),
  heading2("11.1 已完成验证"),
  dataTable(
    ["验证项", "结果", "证据"],
    [
      ["模型训练与导出", "通过", "生成 11,012 节点头文件和 training_report.json"],
      ["ESP32 release 编译", "通过", "RAM 8.3%，Flash 37.7%"],
      ["三位置 I2C 在线", "通过", "颈部 0x68、背部 0x53、腿部 0x69，页面显示 3/3"],
      ["实时串口链路", "通过", "COM19、115200，后端持续接收 JSON"],
      ["网站实时展示", "通过", "行为、窗口样本、倾角、活动、轴数据和趋势均可见"],
    ],
    [2500, 1400, CONTENT_WIDTH - 3900],
    { zebra: true },
  ),
  heading2("11.2 台架功能测试"),
  dataTable(
    ["用例", "操作", "预期"],
    [
      ["三节点静止", "全部平放并保持静止 10 秒", "三位置在线，活动值接近稳定低值，窗口样本约 38～40"],
      ["背部翻转", "缓慢把 ADXL345 从基准姿态转动超过 55°", "bodyTiltDeg 越过阈值，卧姿类别得分增强"],
      ["腿部摆动", "保持颈、背稳定，连续摆动腿部 MPU", "legActivity 上升；超过 1.20 后行走得分增强"],
      ["颈部活动", "保持腿静止，连续移动颈部 MPU", "neckActivity 上升；超过 0.65 时采食得分可增强"],
      ["节点掉线", "断开任意一个运动传感器", "网站提示节点离线，行为 state=sensors_missing"],
      ["恢复测试", "重新接好掉线节点并等待", "I2C 恢复后重新出现在线 3/3 和正常窗口"],
    ],
    [1700, 3650, CONTENT_WIDTH - 5350],
    { zebra: true },
  ),
  heading2("11.3 实牛现场验证"),
  ...numberedList(
    [
      "检查绑带牢固、轴向记录、外壳防水、线缆应力释放和单一 3.3 V 电源。",
      "用视频覆盖传感器采集全程，并让视频时间与 ESP32 timestamp_ms 对齐。",
      "至少记录站立静止、卧地、采食、行走、站立反刍和卧姿反刍的连续片段。",
      "人工标注人员在不知道模型输出的条件下独立标注，冲突片段复核。",
      "计算每类混淆矩阵、宏平均 F1、按牛只指标和连续 24 小时掉线率。",
      "只在独立验证集上调整 55°、1.20、3.00、0.65 等阈值，测试集保留到最终一次评估。",
    ],
    "steps-fieldtest",
  ),
  heading2("11.4 建议验收门槛"),
  callout(
    "注意：",
    "以下是下一阶段建议目标，不是当前模型已经达到的指标。最终门槛应由项目应用风险和真实数据规模确认。",
    "gold",
  ),
  dataTable(
    ["指标", "建议目标", "验证方式"],
    [
      ["跨牛只宏平均 F1", "≥ 0.75", "测试牛完全不出现在训练/验证中"],
      ["采食、行走召回率", "各 ≥ 0.85", "按牛只报告均值和最差值"],
      ["板端/电脑推理一致性", "100%", "固定黄金样本逐条比对类别"],
      ["窗口端到端延迟 P95", "≤ 2.5 s", "ESP32 采样到网站更新时间"],
      ["三位置掉线率", "< 0.1% / 24 h", "连续运行日志统计"],
      ["资源余量", "Flash < 70%，RAM < 60%", "release 编译报告"],
    ],
    [3000, 2000, CONTENT_WIDTH - 5000],
    { zebra: true },
  ),
);

bodyChildren.push(
  heading1("12 局限性与适用边界"),
  heading2("12.1 当前主要局限"),
  dataTable(
    ["风险", "影响", "控制措施"],
    [
      ["单位置公开训练数据", "背部和腿部不是学习输入", "明确基线性质；采集同步三位置数据后重训"],
      ["无 cow_id", "无法证明跨牛只泛化", "新数据必须按牛只分组，测试牛独立"],
      ["采样率未知", "活动频谱与 20 Hz 板端数据可能不一致", "确认来源采样率；重采本地 20 Hz 数据"],
      ["安装方向敏感", "轴向变化会改变树阈值判断", "统一安装夹具；记录方向；做坐标校准或重训"],
      ["单点模型", "对反刍的周期性时间结构利用不足", "升级为 2～5 秒滑窗特征或 1D 模型"],
      ["规则置信度未校准", "不能解释为统计概率", "使用验证集做 Platt/温度校准或仅作为相对分数"],
      ["绑带与电源噪声", "误判行走或节点掉线", "机械固定、电源去耦、I2C 线束和长时稳定性测试"],
    ],
    [2200, 3000, CONTENT_WIDTH - 5200],
    { zebra: true },
  ),
  heading2("12.2 适用场景"),
  ...bulletList([
    "硬件联调、I2C 节点在线验证和实时数据链路演示。",
    "实牛三位置同步数据采集期间的初始行为提示和人工标注辅助。",
    "研究原型中的采食、躺卧、站立、行走六类基线对比。",
    "与温湿度、体表温度、声音、心率血氧等信号联合形成风险提示，但行为结果只作为一个证据源。",
  ]),
  heading2("12.3 不适用场景"),
  ...bulletList([
    "不能直接作为疾病诊断、治疗决策或动物福利合规判定的唯一依据。",
    "不能在未重新验证时迁移到不同牛种、年龄、安装位置、采样频率或传感器量程。",
    "不能用当前公开测试指标宣称真实牧场 68.38% 或更高的跨牛只识别准确率。",
    "不能把融合 confidence 当作经过校准的概率，也不能以单个 2 秒窗口触发高风险处置。",
    "健康风险必须按时长聚合；只有采食下降、卧地增加或活动降低持续出现并伴随体温、声音异常时才提高风险，同时保留人工与兽医复核。",
  ]),
);

bodyChildren.push(
  heading1("13 三位置同步数据采集与重训规范"),
  heading2("13.1 推荐采集设计"),
  dataTable(
    ["项目", "最低建议", "说明"],
    [
      ["牛只数量", "≥ 10 头，建议 20 头以上", "覆盖体型、年龄、健康状态和个体差异"],
      ["采样频率", "固定 20 Hz", "与当前固件一致；三个位置在同一采样循环读取"],
      ["单次窗口", "2 秒 / 40 样本", "可额外保存连续原始流用于不同窗口实验"],
      ["采集时长", "每头覆盖多日和不同时段", "避免单一日况、饲喂流程和环境偏差"],
      ["标注证据", "同步视频 + 双人复核", "保留原始视频、标注版本和冲突记录"],
      ["安装版本", "每次安装记录照片和轴向", "绑带位置变化必须形成新的 mounting_id"],
    ],
    [2200, 2600, CONTENT_WIDTH - 4800],
    { zebra: true },
  ),
  heading2("13.2 推荐原始数据字段"),
  dataTable(
    ["字段组", "推荐字段"],
    [
      ["标识与时间", "timestamp_ms, cow_id, session_id, mounting_id, firmware_version"],
      ["颈部 MPU", "neck_ax, neck_ay, neck_az, neck_gx, neck_gy, neck_gz"],
      ["背部 ADXL345", "body_ax, body_ay, body_az"],
      ["腿部 MPU", "leg_ax, leg_ay, leg_az, leg_gx, leg_gy, leg_gz"],
      ["质量字段", "neck_online, body_online, leg_online, supply_mv, dropped_samples"],
      ["标签字段", "label, label_source, annotator, label_start_ms, label_end_ms, confidence"],
    ],
    [2300, CONTENT_WIDTH - 2300],
    { zebra: true },
  ),
  heading2("13.3 标签规范"),
  dataTable(
    ["标签", "现场定义建议", "边界处理"],
    [
      ["grazing", "低头取食、咀嚼并持续摄入饲草", "与抬头转场、饮水分开"],
      ["lying_ruminating", "卧姿且出现稳定反刍咀嚼周期", "姿态稳定后开始计时"],
      ["lying_resting", "卧姿、无明确反刍周期", "短暂动作不立即切换标签"],
      ["standing_resting", "站立、低活动、无明确反刍", "排除等待行走和采食过渡"],
      ["walking", "连续步态造成位置移动", "起步/停步各留过渡区"],
      ["standing_ruminating", "站立且出现稳定反刍咀嚼周期", "与站立休息由视频复核区分"],
      ["transition/unknown", "动作切换、遮挡或标注不确定", "训练时排除或单独建类，不强行归入六类"],
    ],
    [2100, 4300, CONTENT_WIDTH - 6400],
    { zebra: true },
  ),
  heading2("13.4 按牛只隔离的数据拆分"),
  ...numberedList(
    [
      "先按 cow_id 划分训练牛、验证牛和测试牛，例如 70%/15%/15%。",
      "同一头牛的所有日期、会话和窗口只能出现在一个集合中。",
      "训练集用于拟合；验证集用于模型、窗口和阈值选择；测试集只做最终一次报告。",
      "数据量较小时采用 leave-one-cow-out 或 group k-fold，并报告各牛指标分布。",
      "过渡样本、掉线样本和异常电源样本不得静默混入正常类别。",
    ],
    "steps-groupsplit",
  ),
  heading2("13.5 下一版模型路线"),
  dataTable(
    ["路线", "输入", "优点", "代价与建议"],
    [
      [
        "窗口统计特征 + RF/ExtraTrees",
        "三位置 2 秒窗口的均值、标准差、RMS、能量、倾角、相关性",
        "部署简单、可解释、适合经典 ESP32",
        "优先推荐；先建立可靠跨牛只基线",
      ],
      [
        "量化 1D-CNN",
        "40×15 左右的三位置同步序列",
        "可学习周期与位置间时序关系",
        "需要 TFLite Micro、内存评估和 int8 校准，适合 ESP32-S3 优先",
      ],
      [
        "颈部模型 + 学习型后融合",
        "各位置子模型概率和物理特征",
        "保留现有架构，逐步替换手工权重",
        "需可靠概率校准和同步验证集",
      ],
    ],
    [2200, 3000, 2100, CONTENT_WIDTH - 7300],
    { zebra: true },
  ),
  heading2("13.6 重训验收"),
  ...bulletList([
    "离线 Python 模型与导出 C++ 模型在黄金样本上的类别必须完全一致。",
    "按牛只报告总体和逐牛混淆矩阵，不只报告随机窗口平均值。",
    "在不同安装批次、不同日期和不同电量下做鲁棒性测试。",
    "保存模型卡和回滚版本；上线后监测类别漂移、低置信度、sensors_missing 与节点活动基线。",
  ]),
);

bodyChildren.push(
  heading1("14 部署、回滚与维护"),
  heading2("14.1 重新训练"),
  ...codeLines([
    "cd D:\\table\\shumuzengxiao\\牛行为识别数据集\\esp32_motion_model",
    "py train_export_model.py",
  ]),
  heading2("14.2 编译与上传到 COM19"),
  ...codeLines([
    "cd D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点",
    "py -m platformio run -e demo_esp32",
    "py -m platformio run -e demo_esp32 -t upload --upload-port COM19",
    "py -m platformio device monitor --port COM19 --baud 115200",
  ]),
  body(
    "串口监视器和 Spring Boot 后端不能同时占用 COM19。烧录和查看启动日志完成后应关闭监视器，再启动后端。",
  ),
  heading2("14.3 启动实时网站"),
  ...codeLines([
    "cd D:\\table\\shumuzengxiao",
    "$env:ESP32_SERIAL_PORT=\"COM19\"",
    ".\\start-all.bat",
    "前端：http://localhost:5173/behavior",
    "后端：http://localhost:8080/api/telemetry/snapshot?limit=60",
  ]),
  heading2("14.4 发布前检查"),
  ...numberedList(
    [
      "确认 training_report.json 的数据路径、样本数和模型版本与头文件一致。",
      "完成 release 编译，并保存 firmware.bin、训练报告、模型头文件和源码版本。",
      "启动日志三节点均为 ok；连续观察 10 个窗口，样本约 38～40 且 online 均为 true。",
      "确认网站模型标签与新版本一致，后端历史数据不混入旧固件结果。",
    ],
    "steps-release",
  ),
  heading2("14.5 回滚策略"),
  body(
    "每个版本应保留 cattle_behavior_model.h、config.h、training_report.json 和 firmware.bin。出现类别漂移、掉线、内存异常或字段不兼容时，直接烧录上一版并恢复配套后端约定。融合参数也必须纳入版本管理：当前 bodyActivity=0.90 和腿部门限 0.60 仍在 main.cpp，后续应迁入 config.h 并把配置版本写入遥测。",
  ),
);

bodyChildren.push(
  heading1("15 故障排查"),
  dataTable(
    ["现象", "优先检查", "处理"],
    [
      [
        "只发现一个 MPU 地址",
        "腿部 AD0 是否接 3V3；颈部 AD0 是否接 GND",
        "断电测量连接；重新扫描应同时出现 0x68 和 0x69",
      ],
      [
        "ADXL345 显示 0x1D",
        "SDO/ALT ADDRESS 被拉高",
        "将 SDO 接 GND，保持 CS 接 3V3，恢复地址 0x53",
      ],
      [
        "sensors_missing",
        "mpu0/adxl345/mpu1 哪个为 false；I2C 错误计数",
        "检查 3.3 V、共地、SDA/SCL、地址和绑带线束；等待 5 秒恢复",
      ],
      [
        "活动值跳变或误报行走",
        "腿部模块是否松动、碰撞；电源纹波",
        "先修复机械固定，再基于静止/行走数据校准 1.20 阈值",
      ],
      [
        "躺卧不识别",
        "背部 Z 轴方向、站立零姿态、bodyTiltDeg",
        "统一安装方向；用实测站立/躺卧分布重设 55°",
      ],
      [
        "行为长期固定为某一类",
        "颈部轴向和 g/°s 单位；六维顺序",
        "对比串口轴数据与训练特征；检查传感器量程和 mounting_id",
      ],
      [
        "windowSamples 明显低于 38",
        "主循环是否被阻塞；I2C 重试；串口大量日志",
        "保持 MAX30102 非阻塞读取，减少 delay 和同步等待",
      ],
      [
        "网站显示离线",
        "COM19 是否被串口监视器占用；后端 8080；WebSocket",
        "关闭其他串口程序，设置 ESP32_SERIAL_PORT=COM19，重启后端",
      ],
      [
        "上传失败",
        "端口变化、后端占用、驱动、BOOT 模式",
        "停止后端，确认设备管理器端口，显式 --upload-port COM19",
      ],
      [
        "3.3 V 不稳定",
        "电源容量、线损、蜂鸣器/风扇干扰、稳压器温升",
        "使用单一稳压源和去耦；不要并联两块开发板的 3.3 V 输出",
      ],
    ],
    [1900, 3100, CONTENT_WIDTH - 5000],
    { zebra: true },
  ),
  heading2("15.1 最小诊断顺序"),
  ...numberedList(
    [
      "只保留 ESP32 和三个运动传感器，确认电源和 I2C 地址。",
      "观察启动日志的 WHO_AM_I/DEVID 初始化结果。",
      "读取 10 秒原始轴数据，检查静止模长约为 9.8 m/s²。",
      "查看 windowSamples、bodyTiltDeg 和三个 activity 是否随动作合理变化。",
      "对比 neckModelState 与融合 state 定位问题，再逐项接回其他传感器、执行器和网站。",
    ],
    "steps-debug",
  ),
);

bodyChildren.push(
  heading1("16 结论与后续路线"),
  body(
    "当前 public-neck-rf-v1 已完成从公开数据训练、C++ 导出、ESP32 编译、三位置融合、串口传输到网站实时显示的端到端工程闭环。模型在公开片段隔离测试集上达到 68.38% 准确率和 57.49% 宏平均 F1；固件资源占用为 RAM 8.3%、Flash 37.7%，三处运动传感器在 COM19 实机链路中均在线。",
  ),
  body(
    "该版本适合作为硬件联调、数据采集和算法迭代基线。下一阶段的核心不是继续调整公开单传感器模型，而是形成带 cow_id、timestamp、mounting_id 和同步视频标签的颈/背/腿三位置数据集；随后按牛只隔离评估，优先训练窗口统计特征随机森林，再根据数据量和 ESP32-S3 资源评估量化 1D-CNN。",
  ),
  callout(
    "最终结论：",
    "模型已经可以运行和实时展示，但尚不能作为生产级三位置学习模型宣称。完成同步实牛数据、按牛只独立验证、阈值校准和长时稳定性测试后，才能进入正式健康预警使用。",
    "green",
  ),
  heading2("16.1 推荐优先级"),
  ...numberedList(
    [
      "固定三处安装结构和轴向，先解决机械一致性与供电稳定性。",
      "升级固件采集格式，保存三位置原始流、timestamp_ms、cow_id 和 mounting_id。",
      "同步视频标注至少 10～20 头牛，并建立 transition/unknown 质量标签。",
      "按牛只分组重训并报告逐牛指标，达到验收目标后再替换 public-neck-rf-v1。",
      "将行为时长与温度、声音、心率血氧做时间聚合，形成可解释的多模态风险规则。",
    ],
    "steps-roadmap",
  ),
);

bodyChildren.push(
  heading1("附录 A 标签与编号"),
  dataTable(
    ["编号", "固件/JSON 标签", "中文显示", "来源标签"],
    [
      ["0", "grazing", "采食", "Grazing"],
      ["1", "lying_ruminating", "卧姿反刍", "Lying-Ruminating"],
      ["2", "lying_resting", "卧姿休息", "Lying-Resting"],
      ["3", "standing_resting", "站立休息", "Standing-Resting"],
      ["4", "walking", "行走", "Walking"],
      ["5", "standing_ruminating", "站立反刍", "Standing-Ruminating"],
    ],
    [1100, 3000, 2300, CONTENT_WIDTH - 6400],
    { zebra: true, numericColumns: [0] },
  ),
  heading1("附录 B 关键配置清单"),
  dataTable(
    ["配置", "值", "说明"],
    [
      ["PIN_I2C_SDA", "21", "三个运动传感器共享 SDA"],
      ["PIN_I2C_SCL", "22", "三个运动传感器共享 SCL"],
      ["MPU0_I2C_ADDR", "0x68", "颈部 MPU"],
      ["ADXL345_I2C_ADDR", "0x53", "背部 ADXL345"],
      ["MPU1_I2C_ADDR", "0x69", "腿部 MPU"],
      ["MOTION_SAMPLE_INTERVAL_MS", "50", "20 Hz 运动采样"],
      ["SAMPLE_INTERVAL_MS", "2000", "行为融合和遥测窗口"],
      ["BODY_LIE_TILT_DEG", "55.0", "躺卧倾角"],
      ["WALK_LEG_ACTIVITY", "1.20", "腿部行走门限"],
      ["VIGOROUS_LEG_ACTIVITY", "3.00", "剧烈腿部活动尺度"],
      ["ACTIVE_NECK_ACTIVITY", "0.65", "颈部活跃门限"],
      ["Serial", "115200 8N1", "ESP32 与后端遥测"],
    ],
    [3200, 1800, CONTENT_WIDTH - 5000],
    { zebra: true },
  ),
  heading1("附录 C 代码与数据索引"),
  dataTable(
    ["对象", "本地路径"],
    [
      ["数据集", "D:\\table\\shumuzengxiao\\牛行为识别数据集\\free_datasets\\cattle_classification_github_andssuu\\data\\dataset_6.csv"],
      ["训练脚本", "D:\\table\\shumuzengxiao\\牛行为识别数据集\\esp32_motion_model\\train_export_model.py"],
      ["训练报告", "D:\\table\\shumuzengxiao\\牛行为识别数据集\\esp32_motion_model\\training_report.json"],
      ["模型头文件", "D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\\include\\cattle_behavior_model.h"],
      ["融合阈值", "D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\\include\\config.h"],
      ["ESP32 固件", "D:\\table\\shumuzengxiao\\硬件代码\\现有硬件演示节点\\src\\main.cpp"],
      ["后端串口服务", "D:\\table\\shumuzengxiao\\smart-cattle-backend\\src\\main\\java\\com\\shumuzengxiao\\smartcattle\\service\\TelemetryService.java"],
      ["实时页面", "D:\\table\\shumuzengxiao\\smart-cattle-frontend\\src\\views\\BehaviorView.vue"],
    ],
    [1900, CONTENT_WIDTH - 1900],
    { zebra: true },
  ),
  heading1("附录 D 复现实验记录"),
  dataTable(
    ["项目", "记录"],
    [
      ["训练数据", "13,088 行；671 个连续行为片段"],
      ["拆分", "训练 10,476；测试 2,612；片段级分层 80/20"],
      ["模型", "30 树；深度 10；最小叶 8；每节点 3 特征；每类每树 800"],
      ["结果", "Accuracy 0.6838；Macro-F1 0.5749；总节点 11,012"],
      ["编译环境", "Espressif32 7.0.1；Arduino ESP32 3.20017；release"],
      ["板卡", "ESP32 Dev Module，240 MHz，320 KB RAM，4 MB Flash"],
      ["资源", "RAM 27,348 B / 8.3%；Flash 494,649 B / 37.7%"],
      ["实机链路", "COM19，115200；三位置节点 3/3 在线；网页已实时显示"],
      ["记录日期", "2026-07-19"],
    ],
    [2600, CONTENT_WIDTH - 2600],
    { zebra: true },
  ),
  heading1("附录 E 参考资料"),
  ...numberedList(
    [
      "andssuu/cattle_classification：Convolutional neural networks in the classification of cattle behaviour through inertial sensors，https://github.com/andssuu/cattle_classification。",
      "项目训练脚本 train_export_model.py 与训练报告 training_report.json，模型版本 public-neck-rf-v1。",
      "项目 ESP32 固件 main.cpp、config.h 与生成模型 cattle_behavior_model.h。",
      "项目 Spring Boot TelemetryService、WebSocket /ws/telemetry 与 Vue BehaviorView.vue。",
    ],
    "refs",
  ),
);

const numberingRefs = [
  "steps-split",
  "steps-runtime",
  "steps-fieldtest",
  "steps-groupsplit",
  "steps-release",
  "steps-debug",
  "steps-roadmap",
  "refs",
];

const doc = new Document({
  creator: "Codex",
  title: "牛三位置惯性传感器行为识别模型详细说明书",
  subject: "颈部 MPU、背部 ADXL345、腿部 MPU 的电脑训练与 ESP32 边缘部署",
  keywords: "牛行为识别, ESP32, MPU-9250, MPU-6500, ADXL345, 随机森林, 三位置融合",
  description: "数牧增效项目牛行为识别模型 V1.0 详细技术说明书",
  features: { updateFields: true },
  styles: {
    default: {
      document: {
        run: { font: "Microsoft YaHei", size: 21, color: COLORS.ink },
        paragraph: { spacing: { line: 330, after: 120 } },
      },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "BodyCn",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 34, bold: true, color: COLORS.primaryDark },
        paragraph: {
          spacing: { before: 120, after: 260 },
          outlineLevel: 0,
          pageBreakBefore: true,
          keepNext: true,
          border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: COLORS.gold } },
        },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "BodyCn",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 28, bold: true, color: COLORS.primary },
        paragraph: { spacing: { before: 260, after: 140 }, outlineLevel: 1, keepNext: true },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "BodyCn",
        quickFormat: true,
        run: { font: "Microsoft YaHei", size: 24, bold: true, color: COLORS.blue },
        paragraph: { spacing: { before: 200, after: 100 }, outlineLevel: 2, keepNext: true },
      },
      {
        id: "BodyCn",
        name: "正文中文",
        basedOn: "Normal",
        next: "BodyCn",
        run: { font: "SimSun", size: 21, color: COLORS.ink },
        paragraph: {
          spacing: { line: 340, after: 120 },
          indent: { firstLine: 420 },
          alignment: AlignmentType.JUSTIFIED,
          widowControl: true,
        },
      },
      {
        id: "BodyNoIndent",
        name: "正文无缩进",
        basedOn: "BodyCn",
        next: "BodyNoIndent",
        run: { font: "SimSun", size: 21, color: COLORS.ink },
        paragraph: { spacing: { line: 340, after: 120 }, alignment: AlignmentType.LEFT },
      },
      {
        id: "ListCn",
        name: "列表中文",
        basedOn: "Normal",
        next: "ListCn",
        run: { font: "SimSun", size: 20, color: COLORS.ink },
        paragraph: { spacing: { line: 300, after: 60 }, alignment: AlignmentType.LEFT },
      },
      {
        id: "CellText",
        name: "表格正文",
        basedOn: "Normal",
        next: "CellText",
        run: { font: "Microsoft YaHei", size: 18, color: COLORS.ink },
        paragraph: { spacing: { line: 260, after: 0 } },
      },
      {
        id: "TableHeader",
        name: "表头",
        basedOn: "Normal",
        next: "CellText",
        run: { font: "Microsoft YaHei", size: 18, bold: true, color: COLORS.white },
        paragraph: { spacing: { line: 260, after: 0 }, alignment: AlignmentType.CENTER },
      },
      {
        id: "CodeLine",
        name: "代码行",
        basedOn: "Normal",
        next: "CodeLine",
        run: { font: "Consolas", size: 17, color: "26332D" },
        paragraph: { spacing: { line: 240, after: 0 }, indent: { left: 180, right: 100 } },
      },
      {
        id: "Callout",
        name: "提示框",
        basedOn: "BodyNoIndent",
        next: "BodyCn",
        run: { font: "Microsoft YaHei", size: 19, color: COLORS.ink },
        paragraph: {
          spacing: { line: 300, before: 120, after: 160 },
          indent: { left: 260, right: 180 },
        },
      },
      {
        id: "FigureCaption",
        name: "图注",
        basedOn: "Normal",
        next: "BodyCn",
        run: { font: "Microsoft YaHei", size: 18, color: COLORS.muted },
        paragraph: { spacing: { before: 60, after: 180 }, alignment: AlignmentType.CENTER },
      },
      {
        id: "FrontTitle",
        name: "前置标题",
        basedOn: "Normal",
        next: "BodyCn",
        run: { font: "Microsoft YaHei", size: 30, bold: true, color: COLORS.primaryDark },
        paragraph: {
          spacing: { before: 160, after: 180 },
          border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: COLORS.gold } },
          keepNext: true,
        },
      },
      {
        id: "TocNote",
        name: "目录说明",
        basedOn: "Normal",
        next: "Normal",
        run: { font: "Microsoft YaHei", size: 17, color: COLORS.muted },
        paragraph: { spacing: { before: 240, after: 0 }, alignment: AlignmentType.CENTER },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullet-list",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 620, hanging: 300 } } },
          },
        ],
      },
      ...numberingRefs.map((reference) => ({
        reference,
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 680, hanging: 360 } } },
          },
        ],
      })),
    ],
  },
  sections: [
    {
      properties: {
        type: SectionType.NEXT_PAGE,
        page: {
          size: { width: A4_WIDTH, height: A4_HEIGHT },
          margin: {
            top: MARGIN_TOP,
            bottom: MARGIN_BOTTOM,
            left: MARGIN_X,
            right: MARGIN_X,
            header: 567,
            footer: 567,
          },
        },
      },
      children: coverChildren,
    },
    {
      properties: {
        page: {
          size: { width: A4_WIDTH, height: A4_HEIGHT },
          margin: {
            top: MARGIN_TOP,
            bottom: MARGIN_BOTTOM,
            left: MARGIN_X,
            right: MARGIN_X,
            header: 567,
            footer: 567,
          },
          pageNumbers: { start: 1 },
        },
      },
      headers: { default: header() },
      footers: { default: footer() },
      children: bodyChildren,
    },
  ],
});

async function main() {
  if (!fs.existsSync(LIVE_SCREENSHOT)) {
    throw new Error(`Missing live screenshot: ${LIVE_SCREENSHOT}`);
  }
  const buffer = await Packer.toBuffer(doc);
  fs.writeFileSync(OUTPUT, buffer);
  console.log(`Wrote ${OUTPUT}`);
  console.log(`Size ${buffer.length} bytes`);
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});
