App<IAppOption>({
  globalData: {},
  onLaunch() {
    const launchLogs = wx.getStorageSync('launchLogs') || []
    launchLogs.unshift(Date.now())
    wx.setStorageSync('launchLogs', launchLogs.slice(0, 20))
  },
})
