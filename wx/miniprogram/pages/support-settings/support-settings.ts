import { catalog, getSettings, messageError, saveSettings } from '../../utils/support'
Page({
  data: { baseUrl: '', apiKey: '', testing: false, message: '', error: '' },
  onLoad() { this.setData(getSettings()) },
  changeUrl(event: WechatMiniprogram.InputEvent) { this.setData({ baseUrl: event.detail.value, message: '', error: '' }) },
  changeKey(event: WechatMiniprogram.InputEvent) { this.setData({ apiKey: event.detail.value, message: '', error: '' }) },
  async save() {
    if (this.data.testing) return
    this.setData({ error: '', message: '' })
    try { saveSettings({ baseUrl: this.data.baseUrl, apiKey: this.data.apiKey }) }
    catch (error) { this.setData({ error: messageError(error) }); return }
    this.setData({ testing: true })
    try {
      const result = await catalog()
      this.setData({ message: `设置已保存，服务连接正常 · ${result.mode === 'llm' ? '大模型问答' : '知识库模式'}` })
    } catch (error) { this.setData({ error: `设置已保存。${messageError(error)}` }) }
    finally { this.setData({ testing: false }) }
  }
})
