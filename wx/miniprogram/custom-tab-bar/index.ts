interface TabItem {
  pagePath: string
  text: string
  icon: string
}

Component({
  data: {
    selected: 0,
    tabs: [
      { pagePath: '/pages/index/index', text: '总览', icon: '⌂' },
      { pagePath: '/pages/diagnosis/diagnosis', text: 'AI识牛', icon: '◎' },
      { pagePath: '/pages/records/records', text: '记录', icon: '▣' },
      { pagePath: '/pages/admin/admin', text: '管理', icon: '⚙' }
    ] as TabItem[]
  },

  methods: {
    switchTab(event: WechatMiniprogram.TapEvent) {
      const { index } = event.currentTarget.dataset as { index?: number }
      if (index === undefined || index === this.data.selected) return

      const tab = this.data.tabs[index]
      wx.switchTab({ url: tab.pagePath })
    }
  }
})
