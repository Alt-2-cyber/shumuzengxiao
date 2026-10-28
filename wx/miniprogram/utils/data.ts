export type RiskLevel = 'normal' | 'observe' | 'warning' | 'urgent'

export interface DiagnosisRecord {
  id: string
  imagePath: string
  createdAt: string
  cowId: string
  riskLevel: RiskLevel
  score: number
  conclusion: string
  findings: string[]
  suggestions: string[]
  modelVersion: string
}

export interface DeviceState {
  id: string
  name: string
  type: string
  status: 'online' | 'offline' | 'maintenance'
  value: string
}

export interface AlertItem {
  id: string
  title: string
  source: string
  level: RiskLevel
  time: string
}

export interface AdminAction {
  id: string
  title: string
  subtitle: string
  tone: 'green' | 'gold' | 'red'
}

export const RECORDS_KEY = 'smart_cattle_diagnosis_records'

const FINDING_POOL = [
  '眼鼻区域未见明显分泌物，精神状态初步稳定',
  '皮毛反光较均匀，未见大面积脱毛或破损',
  '站姿稳定，未识别到明显跛行姿态',
  '鼻镜区域偏暗，建议补拍近距离头部照片',
  '腹部轮廓清晰，未见异常鼓胀迹象',
  '局部皮肤纹理不清，可能受光照或遮挡影响',
  '耳部姿态正常，仍需结合现场采食情况判断',
  '口鼻附近存在疑似湿润区域，建议人工复核'
]

const SUGGESTION_MAP: Record<RiskLevel, string[]> = {
  normal: ['继续日常巡检', '保持牛舍通风与饮水', '按计划记录体温和采食情况'],
  observe: ['补拍眼鼻和皮肤局部照片', '观察 2 小时内活动量变化', '检查同栏牛只是否有类似表现'],
  warning: ['安排人工近距离复核', '记录体温、采食和呼吸频率', '必要时隔离观察并保留截图证据'],
  urgent: ['立即通知管理员现场处理', '建议隔离疑似异常牛只', '联系兽医复核并同步环境数据']
}

export function formatTime(date = new Date()): string {
  const pad = (value: number) => String(value).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function riskText(level: RiskLevel): string {
  const map: Record<RiskLevel, string> = {
    normal: '健康',
    observe: '关注',
    warning: '疑似异常',
    urgent: '高风险'
  }
  return map[level]
}

export function riskClass(level: RiskLevel): string {
  if (level === 'observe') return 'observe'
  if (level === 'warning') return 'warn'
  if (level === 'urgent') return 'danger'
  return 'normal'
}

export function deviceStatusText(status: DeviceState['status']): string {
  const map: Record<DeviceState['status'], string> = {
    online: '在线',
    offline: '离线',
    maintenance: '维护'
  }
  return map[status]
}

export function getRecords(): DiagnosisRecord[] {
  return wx.getStorageSync(RECORDS_KEY) || []
}

export function saveRecord(record: DiagnosisRecord): DiagnosisRecord[] {
  const records = [record, ...getRecords()].slice(0, 50)
  wx.setStorageSync(RECORDS_KEY, records)
  return records
}

export function clearRecords(): void {
  wx.setStorageSync(RECORDS_KEY, [])
}

export function createMockAnalysis(imagePath: string): DiagnosisRecord {
  const seed = Array.from(imagePath).reduce((sum, char) => sum + char.charCodeAt(0), Date.now() % 97)
  const score = 58 + (seed % 39)
  const riskLevel: RiskLevel = score >= 86 ? 'normal' : score >= 74 ? 'observe' : score >= 64 ? 'warning' : 'urgent'
  const findingStart = seed % (FINDING_POOL.length - 2)
  const findings = FINDING_POOL.slice(findingStart, findingStart + 3)
  const cowId = `C-${String((seed % 86) + 1).padStart(3, '0')}`
  const conclusionMap: Record<RiskLevel, string> = {
    normal: '图像特征整体稳定，未发现明显疾病风险。',
    observe: '存在轻微信号不确定性，建议补拍局部并继续观察。',
    warning: '识别到疑似异常体征，需要人工复核确认。',
    urgent: '多项图像特征偏离正常范围，建议立即现场处理。'
  }

  return {
    id: `diag_${Date.now()}`,
    imagePath,
    createdAt: formatTime(),
    cowId,
    riskLevel,
    score,
    conclusion: conclusionMap[riskLevel],
    findings,
    suggestions: SUGGESTION_MAP[riskLevel],
    modelVersion: 'CattleVision-Mini v0.8'
  }
}

export function getDashboardMetrics(records = getRecords()) {
  const latest = records[0]
  const warningCount = records.filter((item) => item.riskLevel === 'warning' || item.riskLevel === 'urgent').length
  const observeCount = records.filter((item) => item.riskLevel === 'observe').length
  return {
    cattleCount: 86,
    onlineDevices: 4,
    totalDevices: 4,
    warningCount,
    observeCount,
    latestRisk: latest ? riskText(latest.riskLevel) : '暂无记录',
    latestScore: latest ? latest.score : 0
  }
}

export function getDevices(): DeviceState[] {
  return [
    { id: 'esp32_env_01', name: 'ESP32-S3 环境节点', type: '主控采集', status: 'online', value: '26.9℃ / 67%' },
    { id: 'maixcam_01', name: 'MaixCam 视觉节点', type: 'AI 摄像头', status: 'online', value: '9.8 FPS' },
    { id: 'mic_i2s_01', name: 'INMP441 声音节点', type: 'I2S 麦克风', status: 'online', value: 'VAD 正常' },
    { id: 'relay_box_01', name: '继电器控制箱', type: '执行器', status: 'online', value: '自动模式' }
  ]
}

export function getAlerts(records = getRecords()): AlertItem[] {
  const recordAlerts = records
    .filter((item) => item.riskLevel !== 'normal')
    .slice(0, 5)
    .map((item) => ({
      id: item.id,
      title: `${item.cowId} ${riskText(item.riskLevel)}识别`,
      source: 'AI 照片分析',
      level: item.riskLevel,
      time: item.createdAt
    }))

  return [
    ...recordAlerts,
    { id: 'env_001', title: '氨气趋势偏高', source: '环境节点', level: 'observe', time: formatTime(new Date(Date.now() - 1000 * 60 * 38)) },
    { id: 'dev_001', title: 'MaixCam 在线', source: '设备状态', level: 'normal', time: formatTime(new Date(Date.now() - 1000 * 60 * 64)) }
  ]
}

export function getAdminActions(): AdminAction[] {
  return [
    { id: 'fan', title: '开启风扇', subtitle: '通风 20 分钟', tone: 'green' },
    { id: 'capture', title: '触发抓拍', subtitle: '调用视觉节点', tone: 'gold' },
    { id: 'alarm', title: '声光提醒', subtitle: '通知现场巡检', tone: 'red' },
    { id: 'sync', title: '同步模型', subtitle: '更新识别参数', tone: 'green' }
  ]
}

export function syncTabBar(page: WechatMiniprogram.Page.Instance<WechatMiniprogram.IAnyObject, WechatMiniprogram.IAnyObject>, selected: number): void {
  if (typeof page.getTabBar !== 'function') return

  const tabBar = page.getTabBar()
  if (tabBar) {
    tabBar.setData({ selected })
  }
}
