const fs = require('fs');
const path = require('path');
const { chromium } = require('../smart-cattle-frontend/node_modules/playwright');

async function main() {
  const dir = path.resolve(__dirname, '../.run/cow-copyright/screens');
  fs.mkdirSync(dir, { recursive: true });
  const browser = await chromium.launch({ headless: true });
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
  try {
    for (const [name, route] of [['web-dashboard.png','dashboard'],['web-environment.png','environment'],['web-devices.png','devices'],['web-models.png','models']]) {
      await page.goto(`http://127.0.0.1:5187/${route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1800);
      await page.screenshot({ path: path.join(dir,name), fullPage:false });
      console.log(`${route}: ${await page.title()}`);
    }
  } finally { await browser.close(); }
}
main().catch(e=>{console.error(e);process.exitCode=1;});
