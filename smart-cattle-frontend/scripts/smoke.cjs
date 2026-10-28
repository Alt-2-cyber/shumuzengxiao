const { chromium } = require('playwright')

async function main() {
  const browser = await chromium.launch({ headless: true })
  const page = await browser.newPage({ viewport: { width: 1440, height: 1000 } })

  await page.goto('http://localhost:5173/dashboard', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.topbar h1', { timeout: 20000 })
  await page.waitForSelector('canvas[data-engine^="three.js"]', { timeout: 20000 })
  await page.waitForTimeout(1200)

  const title = await page.locator('.topbar h1').innerText()
  const text = await page.locator('body').innerText()
  const canvasMeta = await page.locator('canvas[data-engine^="three.js"]').first().evaluate((canvas) => ({
    width: canvas.width,
    height: canvas.height,
    engine: canvas.dataset.engine
  }))

  await page.screenshot({ path: 'dashboard-screenshot.png', fullPage: true })
  await page.locator('canvas[data-engine^="three.js"]').first().screenshot({ path: 'canvas-screenshot.png' })

  const routes = [
    ['intro', 'http://localhost:5173', '项目介绍'],
    ['environment', 'http://localhost:5173/environment', '环境监测'],
    ['health', 'http://localhost:5173/health', '健康风险'],
    ['behavior', 'http://localhost:5173/behavior', '牛体行为'],
    ['devices', 'http://localhost:5173/devices', '设备控制'],
    ['models', 'http://localhost:5173/models', 'AI 模型'],
    ['vision', 'http://localhost:5173/vision', '视觉证据'],
    ['audio', 'http://localhost:5173/audio', '声音筛查'],
  ]
  const routeChecks = []
  for (const [name, url, expectedTitle] of routes) {
    await page.goto(url, { waitUntil: 'domcontentloaded' })
    await page.waitForFunction(
      (expected) => document.querySelector('.topbar h1')?.innerText === expected,
      expectedTitle,
      { timeout: 20000 }
    )
    routeChecks.push([name, await page.locator('.topbar h1').innerText() === expectedTitle])
  }

  await page.goto('http://localhost:5173/devices', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.topbar h1', { timeout: 20000 })
  await page.waitForFunction(
      () => {
      const text = document.querySelector('.actuator-connection')?.innerText || ''
      return text.includes('已连接') || text.includes('离线') || text.includes('等待数据')
    },
    null,
    { timeout: 15000 }
  )
  const controlState = await page.locator('.actuator-connection').innerText()
  const controlReady = controlState.includes('已连接')
  let commandIssued = false
  if (controlReady) {
    await page.getByTitle('强制开启风扇').click()
    await page.waitForFunction(
      () => {
        const text = document.querySelector('.command-result')?.innerText || ''
        return text.includes('设备已执行') || text.includes('WiFi 轮询队列') || text.includes('命令已通过')
      },
      null,
      { timeout: 8000 }
    )
    const commandResult = await page.locator('.command-result').innerText()
    commandIssued = commandResult.includes('设备已执行') || commandResult.includes('WiFi 轮询队列') || commandResult.includes('命令已通过')
  }
  const unsupportedDisabled = await page.locator('.unavailable-control-grid button').evaluateAll(
    (buttons) => buttons.length === 2 && buttons.every((button) => button.disabled)
  )
  if (controlReady) {
    await page.getByTitle('恢复温湿度和 MQ 自动联动').click()
    await page.waitForFunction(
      () => document.querySelector('button[title="恢复温湿度和 MQ 自动联动"]')?.classList.contains('active') ||
        (document.querySelector('.command-result')?.innerText || '').includes('WiFi 轮询队列') ||
        (document.querySelector('.command-result')?.innerText || '').includes('命令已通过'),
      null,
      { timeout: 8000 }
    )
  }

  await page.setViewportSize({ width: 1440, height: 1000 })
  await page.goto('http://localhost:5173/behavior', { waitUntil: 'domcontentloaded' })
  await page.waitForSelector('.telemetry-livebar', { timeout: 20000 })
  await page.waitForSelector('.motion-chart canvas', { timeout: 20000 })
  await page.waitForFunction(
    () => {
      const text = document.querySelector('.telemetry-livebar')?.innerText || ''
      return ['实时数据流', 'ESP32 实时链路离线', '数据已停止更新', '网页实时通道重连中']
        .some((label) => text.includes(label))
    },
    null,
    { timeout: 15000 }
  )
  const sequenceBefore = await page.locator('.model-footline').innerText()
  const realtimeText = await page.locator('.telemetry-livebar').innerText()
  const liveStream = realtimeText.includes('实时数据流')
  if (liveStream) {
    await page.waitForFunction(
      (previous) => document.querySelector('.model-footline')?.innerText !== previous,
      sequenceBefore,
      { timeout: 8000 }
    )
  }
  const sequenceAfter = await page.locator('.model-footline').innerText()
  const motionCanvas = await page.locator('.motion-chart canvas').evaluate((canvas) => ({
    width: canvas.width,
    height: canvas.height,
    dataUrlLength: canvas.toDataURL().length
  }))
  await page.setViewportSize({ width: 390, height: 844 })
  const mobileWidth = await page.locator('body').evaluate((body) => ({
    clientWidth: body.clientWidth,
    scrollWidth: body.scrollWidth
  }))
  await browser.close()

  const checks = [
    ['title', title === '总览驾驶舱'],
    ['dashboard text', text.includes('总览驾驶舱')],
    ['three canvas width', canvasMeta.width > 300],
    ['three canvas height', canvasMeta.height > 250],
    ['three engine', canvasMeta.engine?.startsWith('three.js')],
    ['hardware control state handled', controlReady ? commandIssued : controlState.includes('离线') || controlState.includes('等待数据')],
    ['unsupported controls disabled', unsupportedDisabled],
    ['telemetry state rendered', liveStream || realtimeText.includes('ESP32 实时链路离线') || realtimeText.includes('数据已停止更新') || realtimeText.includes('网页实时通道重连中')],
    ['telemetry sequence updates', liveStream ? sequenceBefore !== sequenceAfter : sequenceAfter.length > 0],
    ['motion chart width', motionCanvas.width > 300],
    ['motion chart height', motionCanvas.height > 200],
    ['motion chart painted', motionCanvas.dataUrlLength > 5000],
    ['mobile no horizontal overflow', mobileWidth.scrollWidth === mobileWidth.clientWidth],
    ...routeChecks
  ]

  const failed = checks.filter(([, ok]) => !ok)
  console.log(JSON.stringify({ title, canvasMeta, checks }, null, 2))
  if (failed.length) {
    throw new Error(`Smoke check failed: ${failed.map(([name]) => name).join(', ')}`)
  }
}

main().catch((error) => {
  console.error(error)
  process.exit(1)
})
