import fs from 'node:fs/promises';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire('D:/table/shumuzengxiao/smart-cattle-frontend/package.json');
const { chromium } = require('playwright');

const outDir = 'D:/table/shumuzengxiao/report_assets';
await fs.mkdir(outDir, { recursive: true });

const pages = [
  ['intro', 'http://localhost:5173/'],
  ['dashboard', 'http://localhost:5173/dashboard'],
  ['environment', 'http://localhost:5173/environment'],
  ['health', 'http://localhost:5173/health'],
  ['devices', 'http://localhost:5173/devices'],
  ['models', 'http://localhost:5173/models'],
];

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({
  viewport: { width: 1440, height: 1000 },
  deviceScaleFactor: 1,
});

for (const [name, url] of pages) {
  await page.goto(url, { waitUntil: 'networkidle', timeout: 30000 });
  await page.waitForTimeout(900);
  const file = path.join(outDir, `web-${name}.png`);
  await page.screenshot({ path: file, fullPage: false });
  console.log(file);
}

await browser.close();
