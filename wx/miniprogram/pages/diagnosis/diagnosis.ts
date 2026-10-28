import { DiagnosisRecord, createMockAnalysis, riskClass, riskText, saveRecord, syncTabBar } from '../../utils/data'

Page({
  data: {
    imagePath: '',
    analyzing: false,
    result: null as DiagnosisRecord | null,
    riskLabel: '',
    riskClassName: '',
    progress: 0
  },

  onShow() {
    syncTabBar(this, 1)
  },

  chooseImage() {
    wx.chooseMedia({
      count: 1,
      mediaType: ['image'],
      sourceType: ['album', 'camera'],
      sizeType: ['compressed'],
      success: (res) => {
        const imagePath = res.tempFiles[0]?.tempFilePath || ''
        this.setData({
          imagePath,
          result: null,
          riskLabel: '',
          riskClassName: '',
          progress: 0
        })
      }
    })
  },

  analyzeImage() {
    if (!this.data.imagePath) {
      wx.showToast({ title: '请先上传牛只照片', icon: 'none' })
      return
    }

    this.setData({ analyzing: true, progress: 12 })
    const sourcePath = this.data.imagePath
    const timer = setInterval(() => {
      const nextProgress = Math.min(this.data.progress + 18, 92)
      this.setData({ progress: nextProgress })
    }, 180)

    setTimeout(() => {
      clearInterval(timer)
      try {
        const savedPath = wx.getFileSystemManager().saveFileSync(sourcePath)
        this.finishAnalysis(savedPath || sourcePath)
      } catch (_error) {
        this.finishAnalysis(sourcePath)
      }
    }, 1100)
  },

  finishAnalysis(imagePath: string) {
    const result = createMockAnalysis(imagePath)
    saveRecord(result)
    this.setData({
      imagePath,
      result,
      analyzing: false,
      progress: 100,
      riskLabel: riskText(result.riskLevel),
      riskClassName: riskClass(result.riskLevel)
    })
    wx.showToast({ title: '分析完成', icon: 'success' })
  },

  resetImage() {
    this.setData({
      imagePath: '',
      analyzing: false,
      result: null,
      riskLabel: '',
      riskClassName: '',
      progress: 0
    })
  },

  goRecords() {
    wx.switchTab({ url: '/pages/records/records' })
  }
})
