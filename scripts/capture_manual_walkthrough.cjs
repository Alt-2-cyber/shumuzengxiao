const fs = require('fs');
const path = require('path');
const { execFileSync } = require('child_process');
const assert = require('node:assert/strict');
const root = path.resolve(__dirname, '..');
const out = path.join(root, '.run', 'copyright-20261023', 'screens');
fs.mkdirSync(out, { recursive: true });
const pause = ms => new Promise(resolve => setTimeout(resolve, ms));
const manifests = [];
function entry(key, file, marks, extra = {}) {
  manifests.push({ key, file: path.resolve(file), marks, captured: new Date().toISOString(), ...extra });
  fs.writeFileSync(path.join(out, `${process.argv[2]}-manifest.json`), JSON.stringify(manifests, null, 2));
}

async function web() {
  const { chromium } = require('../smart-cattle-frontend/node_modules/playwright');
  const browser = await chromium.launch({ headless: true });
  try {
    const page = await browser.newPage({ viewport: { width: 1440, height: 1000 }, deviceScaleFactor: 1 });
    const visits = [
      ['web-home', 'dashboard', [['环境监测', '1'], ['牛体行为', '2']]],
      ['web-environment', 'environment', [['环境监测', '1'], ['环境曲线', '2']]],
      ['web-behavior', 'behavior', [['牛体行为', '1'], ['声音筛查', '2']]],
      ['web-audio', 'audio', [['声音筛查', '1'], ['视觉证据', '2']]],
      ['web-vision', 'vision', [['视觉证据', '1'], ['健康风险', '2']]],
      ['web-health', 'health', [['健康风险', '1'], ['设备控制', '2']]],
      ['web-devices', 'devices', [['设备控制', '1'], ['通风风扇', '2']]],
      ['web-models', 'models', [['AI 模型', '1'], ['已部署（仅牛只检测）', '2']]],
      ['web-realtime', 'dashboard', [['WebSocket', '1'], ['边缘状态', '2']]],
      ['web-evidence', 'vision', [['视觉证据', '1'], ['声音筛查', '2']]],
    ];
    for (const [key, route, targets] of visits) {
      await page.goto(`http://127.0.0.1:5173/${route}`, { waitUntil: 'domcontentloaded' });
      await page.waitForTimeout(1200);
      const marks = [];
      for (const [text, label] of targets) {
        const locator = page.getByText(text, { exact: true }).first();
        const box = await locator.boundingBox();
        if (!box || box.y < 0 || box.y + box.height > 1000) continue;
        marks.push({ rect: [box.x - 7, box.y - 6, box.x + box.width + 7, box.y + box.height + 6], label, text });
      }
      assert(marks.length, key);
      const file = path.join(out, `${key}.png`);
      await page.screenshot({ path: file });
      entry(key, file, marks, { route, width: 1440, height: 1000 });
      console.log(key);
    }
  } finally { await browser.close(); }
}

async function mini() {
  const automator = require('../.run/cattle-preview/mini-runtime/node_modules/miniprogram-automator');
  const app = await automator.connect({ wsEndpoint: 'ws://127.0.0.1:9431' });
  console.log('mini connected');
  async function invoke(method, ...args) {
    return app.evaluate(function(method, args) {
      const pages = getCurrentPages(); pages[pages.length - 1][method].apply(pages[pages.length - 1], args); return true;
    }, method, args);
  }
  async function route(url, method = 'navigateTo') {
    await app.evaluate(function(url, method) { wx[method]({ url: url }); return true; }, url, method);
    await pause(1400); return app.currentPage();
  }
  async function wait(predicate) {
    for (let i = 0; i < 70; i++) { const page = await app.currentPage(); const data = await page.data(); if (predicate(data)) return { page, data }; await pause(300); }
    throw new Error('Mini page did not reach expected state');
  }
  async function snap(key, targets) {
    await pause(600);
    const page = await app.currentPage();
    const marks = [];
    for (const [selector, label, text] of targets) {
      const element = await page.$(selector);
      if (!element) continue;
      const offset = await element.offset();
      const size = await element.size();
      const x = Number(offset.left), y = Number(offset.top), w = Number(size.width), h = Number(size.height);
      if (!Number.isFinite(x + y + w + h) || y < 0 || y + h > 835) continue;
      marks.push({ rect: [x - 3, y - 3, x + w + 3, y + h + 3], label, text });
    }
    const file = path.join(out, `${key}.png`);
    await app.screenshot({ path: file });
    const data = await page.data();
    entry(key, file, marks, { route: page.path, width: 430, height: 834 });
    console.log(key, marks.length);
    return data;
  }
  let savedSettings;
  let createdConsultation = '';
  try {
    savedSettings = await app.evaluate(function() { return wx.getStorageSync('cattle_support_settings_v1'); });
    await app.evaluate(function() { wx.setStorageSync('cattle_support_settings_v1', { baseUrl: 'http://127.0.0.1:8080', apiKey: '' }); return true; });
    await route('/pages/index/index', 'switchTab');
    await snap('wx-home', [['.service-shortcuts button:first-child', '1', 'AI助手'], ['.news-entry', '2', '养牛资讯']]);
    await route('/pages/diagnosis/diagnosis', 'switchTab');
    await snap('wx-photo', [['.scanner', '1', '上传或拍摄'], ['.action-row button:first-child', '2', '开始分析']]);
    await route('/pages/records/records', 'switchTab');
    await snap('wx-records', [['.clear-btn', '1', '清空'], ['.empty-state', '2', '空状态']]);
    await route('/pages/admin/admin', 'switchTab');
    await snap('wx-admin', [['.action-grid button:first-child', '1', 'AI助手'], ['.refresh-btn', '2', '刷新']]);
    await route('/pages/support-settings/support-settings');
    await snap('wx-settings', [['.support-field', '1', '平台服务地址'], ['.support-button', '2', '保存并测试连接']]);
    await route('/pages/index/index', 'switchTab');
    await route('/pages/assistant/assistant');
    const assistant = await app.currentPage();
    await assistant.setData({ input: '巡检时发现牛走路不稳，应记录哪些信息？请用四点简洁回答。' });
    await snap('wx-assistant-input', [['.chat-input', '1', '输入问题'], ['.send-button', '2', '发送']]);
    await invoke('send');
    const answer = await wait(d => !d.sending && d.messages && d.messages[d.messages.length - 1].role === 'assistant');
    await snap('wx-assistant-answer', [['.message.assistant:last-child .answer-actions button:last-child', '1', '转专家咨询'], ['.message.assistant:last-child .answer-actions button:first-child', '2', '复制']]);
    await route('/pages/index/index', 'switchTab');
    await route('/pages/consultation/consultation');
    const consult = await app.currentPage();
    const original = await consult.data();
    const draft = { ...original.draft, requestId: `manual_${Date.now()}_consultation`, subject: '操作手册演示：牛只步态观察咨询',
      description: '本条为操作手册截图演示，不代表真实病例。演示记录异常开始时间、步态、采食和已测量的体温，再交由兽医复核。', cattleId: 'DEMO-001', contact: '' };
    await consult.setData({ draft, tab: 'new', selected: null, error: '' });
    await snap('wx-consultation-top', [['.support-choices', '1', '选择咨询方向'], ['.support-segments', '2', '切换我的咨询']]);
    await app.pageScrollTo(900); await pause(400);
    await snap('wx-consultation-submit', [['.support-actions button:last-child', '1', '提交咨询']]);
    await invoke('submit');
    const receipt = await wait(d => !d.sending && d.selected && d.selected.status === 'pending');
    createdConsultation = receipt.data.selected.id;
    await app.pageScrollTo(0); await pause(400);
    await snap('wx-consultation-receipt', [['.support-button.danger', '1', '撤回咨询']]);
    await route('/pages/index/index', 'switchTab');
    await route('/pages/news/news');
    const news = await wait(d => !d.loading && d.articles && d.articles.length > 0);
    await snap('wx-news-list', [['.daily-strip', '1', '今日小知识'], ['.support-head button', '2', '订阅设置']]);
    await invoke('changeTab', { currentTarget: { dataset: { tab: 'knowledge' } } });
    await snap('wx-knowledge-list', [['.article-row', '1', '知识卡详情'], ['.news-tabs', '2', '栏目切换']]);
    const feed = await (await app.currentPage()).data();
    const article = feed.articles[0];
    await invoke('open', { currentTarget: { dataset: { id: article.id } } });
    await wait(d => !d.loading && d.article);
    await snap('wx-knowledge-detail', [['.article-toolbar button:first-child', '1', '收藏'], ['.article-actions button:first-child', '2', '问AI助手']]);
    await route('/pages/index/index', 'switchTab'); await route('/pages/news/news');
    await invoke('changeTab', { currentTarget: { dataset: { tab: 'messages' } } });
    await snap('wx-news-messages', [['.list-tools button', '1', '全部已读'], ['.news-tabs', '2', '消息栏目']]);
    await invoke('settings');
    await snap('wx-subscriptions', [['.preference-row:first-child', '1', '新闻提醒开关'], ['.preference-row:nth-child(2)', '2', '每日知识开关']]);
    await route('/pages/index/index', 'switchTab');
    // The demo receipt remains as a cancelled, clearly labelled manual example.
    if (createdConsultation) await fetch(`http://127.0.0.1:8080/api/mobile-support/consultations/${createdConsultation}/cancel`, {
      method: 'POST', headers: { 'X-Mobile-Token': await app.evaluate(function() { return wx.getStorageSync('cattle_support_identity_v1'); }), 'Content-Type': 'application/json' }, body: '{}'
    });
  } finally {
    if (savedSettings) await app.evaluate(function(s) { wx.setStorageSync('cattle_support_settings_v1', s); return true; }, savedSettings).catch(() => {});
    await app.disconnect();
  }
}

async function native() {
  const hdc = 'D:\\Program Files\\Huawei\\DevEco Studio\\sdk\\default\\openharmony\\toolchains\\hdc.exe';
  function cmd(...args) { return execFileSync(hdc, ['-t', '127.0.0.1:5555', ...args], { encoding: 'utf8', timeout: 18000 }); }
  function shell(...args) { return cmd('shell', ...args); }
  function walk(node, list = []) { list.push(node.attributes); for (const child of node.children || []) walk(child, list); return list; }
  const rect = a => a.bounds.match(/-?\d+/g).map(Number);
  const visible = a => { const [x, y, r, b] = rect(a); return r > x && b > y && y >= 132 && b <= 2663; };
  async function nodes() {
    shell('uitest', 'dumpLayout', '-p', '/data/local/tmp/manual-layout.json');
    const file = path.join(out, 'hm-layout.json'); cmd('file', 'recv', '/data/local/tmp/manual-layout.json', file);
    return walk(JSON.parse(fs.readFileSync(file, 'utf8')));
  }
  async function click(text, scroll = false) {
    for (let i = 0; i < (scroll ? 6 : 1); i++) {
      const a = (await nodes()).find(n => n.text === text && visible(n));
      if (a) { const [x, y, r, b] = rect(a); shell('uitest', 'uiInput', 'click', String((x + r) >> 1), String((y + b) >> 1)); await pause(600); return; }
      if (scroll) shell('uitest', 'uiInput', 'swipe', '700', '2250', '700', '1200', '800');
    }
    throw new Error('Native target not found: ' + text);
  }
  async function wait(text) {
    for (let i = 0; i < 65; i++) { const list = await nodes(); if (list.some(n => (n.text || '').includes(text))) return list; await pause(300); }
    throw new Error('Native page not ready: ' + text);
  }
  async function snap(key, targets) {
    await pause(800);
    const list = await nodes(); const marks = [];
    for (const [text, label] of targets) {
      const a = list.find(n => (n.text === text || n.hint === text || n.description === text) && visible(n));
      if (a) marks.push({ rect: rect(a), label, text });
    }
    const file = path.join(out, `${key}.jpeg`);
    shell('snapshot_display', '-f', '/data/local/tmp/manual-capture.jpeg');
    cmd('file', 'recv', '/data/local/tmp/manual-capture.jpeg', file);
    fs.writeFileSync(path.join(out, `${key}-layout.json`), JSON.stringify(list, null, 2));
    entry(key, file, marks, { width: 1272, height: 2756 }); console.log(key, marks.length);
  }
  const back = async () => { shell('uitest', 'uiInput', 'keyEvent', 'Back'); await pause(600); };
  shell('aa', 'force-stop', 'com.example.myapplication'); shell('power-shell', 'wakeup'); shell('aa', 'start', '-b', 'com.example.myapplication', '-a', 'EntryAbility');
  await wait('AI 助手 ↗');
  await snap('hm-home', [['AI 识牛', '1'], ['AI 助手 ↗', '2'], ['专家咨询 ↗', '3']]);
  await click('AI 识牛'); await wait('上传或拍摄牛只照片');
  await snap('hm-photo', [['上传或拍摄牛只照片', '1'], ['开始 AI 分析', '2']]);
  await click('记录'); await wait('识别记录'); await snap('hm-records', [['清空', '1'], ['记录', '2']]);
  await click('管理'); await wait('后台管理'); await snap('hm-admin', [['刷新', '1'], ['AI 助手 ↗', '2']]);
  await click('总览'); await click('AI 助手 ↗'); await wait('AI 助手');
  await snap('hm-assistant', [['描述牛只、环境或设备问题', '1'], ['发送问题', '2'], ['转专家咨询 ↗', '3']]);
  // Reuse the app's actual recent response; no response or record is fabricated for documentation.
  const buttons = (await nodes()).filter(n => n.type === 'Button' && visible(n));
  const settingsButton = buttons.find(n => n.description === '服务设置') || buttons.find(n => { const [x, y] = rect(n); return x > 1000 && y < 350; });
  if (settingsButton) {
    const [x, y, r, b] = rect(settingsButton); shell('uitest', 'uiInput', 'click', String((x + r) >> 1), String((y + b) >> 1));
    await wait('保存并测试连接'); await snap('hm-settings', [['平台服务地址', '1'], ['保存并测试连接', '2']]); await back();
  }
  await back(); await wait('专家咨询 ↗'); await click('专家咨询 ↗'); await wait('问题标题 *');
  await snap('hm-consultation-top', [['牛病与健康', '1'], ['问题标题 *', '2'], ['我的咨询', '3']]);
  shell('uitest', 'uiInput', 'swipe', '700', '2300', '700', '1100', '800');
  await snap('hm-consultation-submit', [['问题详情 *', '1'], ['提交咨询', '2']]);
  await click('我的咨询');
  shell('uitest', 'uiInput', 'swipe', '700', '900', '700', '2300', '1000');
  shell('uitest', 'uiInput', 'swipe', '700', '900', '700', '2300', '1000');
  await pause(700);
  await snap('hm-consultation-records', [['刷新', '1'], ['发起咨询', '2']]);
  await back(); await wait('养牛资讯 ↗'); await click('养牛资讯 ↗', true); await wait('今日小知识');
  await snap('hm-news-list', [['今日小知识', '1'], ['订阅设置', '2'], ['小知识', '3']]);
  const feed = await (await fetch('http://127.0.0.1:8080/api/mobile-support/news/feed')).json();
  const tip = feed.articles.find(a => a.id === feed.dailyKnowledgeId);
  await click(tip.title); await wait('养牛小知识');
  await snap('hm-knowledge-detail', [['☆ 收藏', '1'], ['★ 已收藏', '1'], ['问 AI 助手', '2'], ['延伸阅读链接 ↗', '3']]);
  await back(); await wait('今日小知识'); await click('收藏');
  await snap('hm-news-favorites', [['收藏', '1']]);
  const msg = (await nodes()).find(n => n.type === 'Button' && n.text.startsWith('消息 '));
  if (msg) await click(msg.text);
  await snap('hm-news-messages', [['全部已读', '1']]);
  await click('订阅设置'); await wait('新闻更新提醒');
  await snap('hm-subscriptions', [['新闻更新提醒', '1'], ['每日养牛小知识', '2'], ['健康防疫', '3']]);
  await back();
}

const mode = process.argv[2];
({ web, mini, native }[mode] || (() => { throw new Error('mode required'); }))().catch(error => { console.error(error.stack || error); process.exitCode = 1; });
