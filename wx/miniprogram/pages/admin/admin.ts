import { AdminAction, AlertItem, DeviceState, getAdminActions, getAlerts, getDevices, getRecords, riskClass, riskText, syncTabBar } from '../../utils/data'

interface DeviceView extends DeviceState {
  statusText: string
  statusClass: string
}

interface AlertView extends AlertItem {
  levelText: string
  levelClass: string
}

interface CommandLog {
  id: string
  title: string
  time: string
}

Page({
  data: {
    devices: [] as DeviceView[],
    alerts: [] as AlertView[],
    actions: [] as AdminAction[],
    commandLogs: [] as CommandLog[],
    onlineRate: '100%'
  },

  onShow() {
    syncTabBar(this, 3)

    const devices = getDevices().map((device) => ({
      ...device,
      statusText: device.status === 'online' ? '在线' : device.status === 'maintenance' ? '维护' : '离线',
      statusClass: device.status === 'online' ? 'normal' : device.status === 'maintenance' ? 'observe' : 'offline'
    }))
    const onlineCount = devices.filter((device) => device.status === 'online').length

    this.setData({
      devices,
      actions: getAdminActions(),
      onlineRate: `${Math.round((onlineCount / devices.length) * 100)}%`,
      alerts: getAlerts(getRecords()).slice(0, 5).map((alert) => ({
        ...alert,
        levelText: riskText(alert.level),
        levelClass: riskClass(alert.level)
      }))
    })
  },

  runAction(event: WechatMiniprogram.TapEvent) {
    const { title } = event.currentTarget.dataset as { title?: string }
    if (!title) return

    const now = new Date()
    const time = `${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}`
    const commandLogs = [{ id: `${Date.now()}`, title, time }, ...this.data.commandLogs].slice(0, 4)
    this.setData({ commandLogs })
    wx.showToast({ title: `${title} 已下发`, icon: 'none' })
  },

  syncData() {
    wx.showToast({ title: '已刷新看板', icon: 'success' })
    this.onShow()
  },
  goService(event: WechatMiniprogram.TapEvent) {
    const target = event.currentTarget.dataset.target === 'assistant' ? 'assistant' : event.currentTarget.dataset.target === 'news' ? 'news' : 'consultation'
    wx.navigateTo({ url: `/pages/${target}/${target}` })
  }
})
