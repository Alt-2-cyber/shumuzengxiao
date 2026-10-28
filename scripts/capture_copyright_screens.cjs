const fs = require('fs');
const path = require('path');
const { chromium } = require('../smart-cattle-frontend/node_modules/playwright');

const root = path.resolve(__dirname, '..');
const out = path.join(root, '.run', 'cow-copyright', 'screens');
const annotated = path.join(out, 'annotated');
fs.mkdirSync(annotated, { recursive: true });

async function mark(page, text, label) {
  const locator = page.getByText(text, { exact: true }).first();
  const box = await locator.boundingBox();
  if (!box) throw new Error(`Cannot find target text: ${text}`);
  await page.evaluate(({ box, label }) => {
    const target = document.createElement('div');
    target.style.position = 'fixed';
    target.style.left = `${Math.max(2, box.x - 8)}px`;
    target.style.top = `${Math.max(2, box.y - 8)}px`;
    target.style.width = `${box.width + 16}px`;
    target.style.height = `${box.height + 16}px`;
    target.style.border = '4px solid #E21D2E';
    target.style.borderRadius = '5px';
    target.style.boxSizing = 'border-box';
    target.style.zIndex = '2147483647';
    target.style.pointerEvents = 'none';
    const caption = document.createElement('span');
    caption.textContent = label;
    caption.style.position = 'absolute';
    caption.style.left = '0';
    caption.style.top = '-34px';
    caption.style.padding = '4px 9px';
    caption.style.color = '#FFFFFF';
    caption.style.background = '#E21D2E';
    caption.style.font = 'bold 16px Microsoft YaHei, sans-serif';
    caption.style.whiteSpace = 'nowrap';
    target.appendChild(caption);
    document.body.appendChild(target);
  }, { box, label });
}

async function captureWeb() {
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  const items = [
    ['web-dashboard.png', 'dashboard', '环境监测', '1 点击环境监测'],
    ['web-environment.png', 'environment', '设备控制', '2 查看设备控制'],
    ['web-devices.png', 'devices', '通风风扇', '3 选择风扇控制'],
    ['web-models.png', 'models', 'AI 模型', '4 查看模型状态'],
  ];
  for (const [file, route, target, label] of items) {
    await page.goto(`http://127.0.0.1:5173/${route}`, { waitUntil: 'domcontentloaded' });
    await page.waitForTimeout(900);
    await page.screenshot({ path: path.join(out, file), fullPage: false });
    await mark(page, target, label);
    await page.screenshot({ path: path.join(annotated, file), fullPage: false });
  }
  await browser.close();
}

captureWeb().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
