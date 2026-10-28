import { defineStore } from 'pinia'
import { getDashboard } from '../api/client'

let pollTimer = null

export const useDashboardStore = defineStore('dashboard', {
  state: () => ({
    data: null,
    loading: false,
    error: ''
  }),
  actions: {
    async load() {
      if (this.loading) return
      this.loading = true
      this.error = ''
      try {
        this.data = await getDashboard()
      } catch (error) {
        this.error = error?.message || '加载失败'
      } finally {
        this.loading = false
      }
    },
    startPolling(intervalMs = 5000) {
      this.stopPolling()
      this.load()
      pollTimer = window.setInterval(() => this.load(), intervalMs)
    },
    stopPolling() {
      if (pollTimer !== null) {
        window.clearInterval(pollTimer)
        pollTimer = null
      }
    }
  }
})
