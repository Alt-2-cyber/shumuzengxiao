import { DiagnosisRecord, AlertItem, DeviceState, getAlerts, getDashboardMetrics, getDevices, getRecords, riskClass, riskText, syncTabBar } from '../../utils/data'
import { newsHomePreview, refreshNews } from '../../utils/news'

interface MetricCard {
  label: string
  value: string
  note: string
}

interface AlertView extends AlertItem {
  levelText: string
  levelClass: string
}

interface DeviceView extends DeviceState {
  statusText: string
  statusClass: string
}

Page({
  data: {
    metrics: [] as MetricCard[],
    latest: null as DiagnosisRecord | null,
    latestRiskText: '',
    latestRiskClass: '',
    devices: [] as DeviceView[],
    alerts: [] as AlertView[],
    hasRecords: false,
    newsUnread: 0, dailyTitle: '养牛新闻与每日小知识', dailyId: ''
  },

  newsPoll: 0,

  onShow() {
    syncTabBar(this, 0)
    this.updateNews()
    if (this.newsPoll) clearInterval(this.newsPoll)
    this.newsPoll = setInterval(() => this.updateNews(), 60000)

    const records = getRecords()
    const summary = getDashboardMetrics(records)
    const latest = records[0] || null
    const devices = getDevices().map((device) => ({
      ...device,
      statusText: device.status === 'online' ? '在线' : device.status === 'maintenance' ? '维护' : '离线',
      statusClass: device.status === 'online' ? 'normal' : device.status === 'maintenance' ? 'observe' : 'offline'
    }))
    const alerts = getAlerts(records).slice(0, 4).map((alert) => ({
      ...alert,
      levelText: riskText(alert.level),
      levelClass: riskClass(alert.level)
    }))

    this.setData({
      latest,
      latestRiskText: latest ? riskText(latest.riskLevel) : '',
      latestRiskClass: latest ? riskClass(latest.riskLevel) : '',
      hasRecords: records.length > 0,
      devices,
      alerts,
      metrics: [
        { label: '在栏牛只', value: `${summary.cattleCount}`, note: '核心棚区' },
        { label: '设备在线', value: `${summary.onlineDevices}/${summary.totalDevices}`, note: '采集链路' },
        { label: '风险识别', value: `${summary.warningCount}`, note: '需复核' },
        { label: '关注项', value: `${summary.observeCount}`, note: '持续观察' }
      ]
    })
  },

  onHide() { if (this.newsPoll) clearInterval(this.newsPoll); this.newsPoll = 0 },
  onUnload() { if (this.newsPoll) clearInterval(this.newsPoll); this.newsPoll = 0 },
  updateNews() {
    this.setData(newsHomePreview())
    refreshNews().then(() => this.setData(newsHomePreview())).catch(() => {})
  },
  goNews() { wx.navigateTo({ url: '/pages/news/news' }) },

  goDiagnosis() {
    wx.switchTab({ url: '/pages/diagnosis/diagnosis' })
  },

  goRecords() {
    wx.switchTab({ url: '/pages/records/records' })
  },

  goAssistant() {
    wx.navigateTo({ url: '/pages/assistant/assistant' })
  },

  goConsultation() {
    wx.navigateTo({ url: '/pages/consultation/consultation' })
  }
})
