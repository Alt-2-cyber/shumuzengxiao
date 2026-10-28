const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun,
  AlignmentType, HeadingLevel, LineRuleType,
  PageNumber, Header, Footer, BorderStyle, TabStopType,
} = require("C:\\Users\\q4984\\AppData\\Roaming\\npm\\node_modules\\docx");

const root = path.resolve(__dirname, "..");
const outputDir = path.join(root, "软著材料");
const data = JSON.parse(fs.readFileSync(path.join(outputDir, "softcopyright-word-content.json"), "utf8"));
const title = `${data.softwareName} ${data.version}`;
const pageWidth = 11906;
const pageHeight = 16838;
const contentWidth = pageWidth - 2042;
const chineseFont = { ascii: "DengXian", hAnsi: "DengXian", eastAsia: "等线", cs: "Arial" };
const codeFont = { ascii: "Consolas", hAnsi: "Consolas", eastAsia: "等线", cs: "Consolas" };

function imageSize(png) {
  const bytes = fs.readFileSync(png);
  if (bytes.toString("ascii", 1, 4) !== "PNG") throw new Error("Expected a PNG image");
  return { width: bytes.readUInt32BE(16), height: bytes.readUInt32BE(20), bytes };
}

function makeHeader(label) {
  return new Header({ children: [new Paragraph({
    spacing: { before: 0, after: 80 },
    border: { bottom: { style: BorderStyle.SINGLE, color: "AFC9BE", size: 5, space: 4 } },
    tabStops: [{ type: TabStopType.RIGHT, position: contentWidth }],
    children: [
      new TextRun({ text: title, font: chineseFont, size: 18, bold: true, color: "103B34" }),
      new TextRun({ text: `\t${label}`, font: chineseFont, size: 16, color: "53645F" }),
    ],
  })] });
}

function makeFooter() {
  return new Footer({ children: [new Paragraph({
    alignment: AlignmentType.CENTER,
    children: [
      new TextRun({ text: `${title}  |  第 `, font: chineseFont, size: 15, color: "657872" }),
      new TextRun({ children: [PageNumber.CURRENT], font: chineseFont, size: 15, color: "657872" }),
      new TextRun({ text: " 页 / 共 ", font: chineseFont, size: 15, color: "657872" }),
      new TextRun({ children: [PageNumber.TOTAL_PAGES], font: chineseFont, size: 15, color: "657872" }),
      new TextRun({ text: " 页", font: chineseFont, size: 15, color: "657872" }),
    ],
  })] });
}

function createDocument(children, label) {
  return new Document({
    title: `${title} ${label}`,
    subject: "软件著作权鉴别材料",
    creator: "牛舍多模态监测平台项目组",
    description: "可编辑 Word 材料；依据同版本 PDF 内容和源程序导出。",
    styles: {
      default: { document: { run: { font: chineseFont, size: 20 }, paragraph: { spacing: { after: 100 } } } },
      paragraphStyles: [{
        id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true,
        run: { font: chineseFont, size: 32, bold: true, color: "103B34" },
        paragraph: { outlineLevel: 0, spacing: { before: 0, after: 160 }, keepNext: true },
      }],
    },
    sections: [{
      properties: { page: {
        size: { width: pageWidth, height: pageHeight },
        margin: { top: 1247, right: 1021, bottom: 1021, left: 1021, header: 510, footer: 510 },
      } },
      headers: { default: makeHeader(label) },
      footers: { default: makeFooter() },
      children,
    }],
  });
}

function sourceChildren() {
  const children = [];
  if (data.programPages.length !== 60) throw new Error("Expected 60 source pages");
  data.programPages.forEach((lines, index) => {
    children.push(new Paragraph({
      pageBreakBefore: index > 0,
      spacing: { before: 0, after: 90, line: 200, lineRule: LineRuleType.EXACT },
      keepNext: true,
      children: [new TextRun({
        text: `程序鉴别材料 | ${index < 30 ? "连续前30页" : "连续后30页"} | V1.0`,
        font: chineseFont, size: 17, bold: true, color: "285C4F",
      })],
    }));
    for (const line of lines) {
      children.push(new Paragraph({
        spacing: { before: 0, after: 0, line: 194, lineRule: LineRuleType.EXACT },
        widowControl: false,
        children: [new TextRun({ text: line || " ", font: codeFont, size: 13, color: "25322F" })],
      }));
    }
  });
  return children;
}

function designChildren() {
  const children = [];
  if (data.documentPages.length !== 60) throw new Error("Expected 60 document pages");
  data.documentPages.forEach((page, index) => {
    children.push(new Paragraph({
      heading: HeadingLevel.HEADING_1,
      pageBreakBefore: index > 0,
      children: [new TextRun(`${String(index + 1).padStart(2, "0")} | ${page.title}`)],
    }));
    if (page.image) {
      const imagePath = path.join(root, "review_media", page.image);
      if (fs.existsSync(imagePath)) {
        const picture = imageSize(imagePath);
        const scale = Math.min(620 / picture.width, 290 / picture.height);
        children.push(new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 0, after: 120 },
          children: [new ImageRun({
            type: "png", data: picture.bytes,
            transformation: { width: Math.round(picture.width * scale), height: Math.round(picture.height * scale) },
            altText: { title: page.title, description: "项目架构或界面配图", name: page.image },
          })],
        }));
      }
    }
    for (const text of page.paragraphs) {
      children.push(new Paragraph({
        spacing: { before: 0, after: 120, line: 310, lineRule: LineRuleType.EXACT },
        children: [new TextRun({ text, font: chineseFont, size: 20, color: "25322F" })],
      }));
    }
    for (const [bulletIndex, bullet] of page.bullets.entries()) {
      children.push(new Paragraph({
        indent: { left: 240, hanging: 240 },
        spacing: { before: 0, after: 50, line: 300, lineRule: LineRuleType.EXACT },
        children: [new TextRun({ text: `${bulletIndex + 1}. ${bullet}`, font: chineseFont, size: 20, color: "25322F" })],
      }));
    }
  });
  return children;
}

async function main() {
  const program = createDocument(sourceChildren(), "程序鉴别材料");
  const design = createDocument(designChildren(), "软件设计说明书");
  fs.writeFileSync(path.join(outputDir, "牛舍多模态监测平台V1.0-程序鉴别材料-前后30页.docx"), await Packer.toBuffer(program));
  fs.writeFileSync(path.join(outputDir, "牛舍多模态监测平台V1.0-文档鉴别材料-软件设计说明书.docx"), await Packer.toBuffer(design));
  console.log(`Created editable DOCX files: source=60 planned pages, design=60 planned pages; source lines=${data.sourceLineCount}`);
}

main().catch((error) => { console.error(error.stack || error); process.exitCode = 1; });
