import { DiagnosisRecord, clearRecords, getRecords, riskClass, riskText, syncTabBar } from '../../utils/data'

interface RecordView extends DiagnosisRecord {
  riskLabel: string
  riskClassName: string
}

Page({
  data: {
    records: [] as RecordView[],
    hasRecords: false
  },

  onShow() {
    syncTabBar(this, 2)
    this.loadRecords()
  },

  loadRecords() {
    const records = getRecords().map((record) => ({
      ...record,
      riskLabel: riskText(record.riskLevel),
      riskClassName: riskClass(record.riskLevel)
    }))
    this.setData({
      records,
      hasRecords: records.length > 0
    })
  },

  clearAll() {
    if (!this.data.hasRecords) {
      wx.showToast({ title: '暂无记录', icon: 'none' })
      return
    }

    wx.showModal({
      title: '清空识别记录',
      content: '本地保存的 AI 识牛记录会被清空，是否继续？',
      confirmText: '清空',
      confirmColor: '#F05E49',
      success: (res) => {
        if (res.confirm) {
          clearRecords()
          this.loadRecords()
          wx.showToast({ title: '已清空', icon: 'success' })
        }
      }
    })
  },

  goDiagnosis() {
    wx.switchTab({ url: '/pages/diagnosis/diagnosis' })
  }
})
