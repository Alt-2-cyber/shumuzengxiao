import { ChatMessage, askAssistant, catalog, displayTime, makeId, messageError, readChat, saveChat } from '../../utils/support'

Page({
  data: {
    messages: [] as ChatMessage[], input: '', sending: false, mode: '连接中', error: '', scrollTarget: '',
    prompts: ['牛走路跛行要观察什么？', '牛咳嗽需要记录哪些信息？', 'B-1 红外体温偏高怎么办？', '牛舍风扇不转怎么排查？']
  },
  alive: true,
  onLoad(options: Record<string, string | undefined>) {
    this.alive = true
    const messages = readChat()
    this.setData({ messages, scrollTarget: messages.length ? `msg-${messages[messages.length - 1].id}` : '' })
    if (options.question) this.setData({ input: decodeURIComponent(options.question).slice(0, 1000) })
    this.refreshMode()
  },
  onShow() { this.refreshMode() },
  onUnload() { this.alive = false },
  async refreshMode() {
    try {
      const info = await catalog()
      if (this.alive) this.setData({ mode: info.mode === 'llm' ? 'DeepSeek 问答' : '知识库模式' })
    } catch (_) { if (this.alive) this.setData({ mode: '服务未连接' }) }
  },
  onInput(event: WechatMiniprogram.InputEvent) { this.setData({ input: event.detail.value }) },
  choosePrompt(event: WechatMiniprogram.TapEvent) {
    this.setData({ input: String(event.currentTarget.dataset.question || '') })
  },
  persist(messages: ChatMessage[]) {
    saveChat(messages)
    if (this.alive) this.setData({ messages, scrollTarget: messages.length ? `msg-${messages[messages.length - 1].id}` : '' })
  },
  async send() {
    if (this.data.sending) return
    const question = this.data.input.trim()
    if (!question) return
    if (question.length > 1000) { this.setData({ error: '每条问题不能超过 1000 个字' }); return }
    const id = makeId()
    const history = this.data.messages.filter(item => item.status === 'done')
    const user: ChatMessage = { id, role: 'user', content: question, time: displayTime(new Date().toISOString()),
      mode: '', model: '', category: '', references: [], status: 'pending', error: '' }
    this.setData({ sending: true, error: '', input: '' })
    try {
      this.persist([...this.data.messages, user].slice(-39))
      await this.fetchAnswer(user, history)
    } catch (error) { this.setData({ error: messageError(error) }) }
    finally { if (this.alive) this.setData({ sending: false }) }
  },
  async fetchAnswer(user: ChatMessage, history: ChatMessage[]) {
    try {
      const result = await askAssistant(user.content, history)
      const messages = this.data.messages.map(item => item.id === user.id ? { ...item, status: 'done' as const, error: '' } : item)
      const answer: ChatMessage = { id: makeId(), role: 'assistant', content: result.answer, time: displayTime(new Date().toISOString()),
        mode: result.mode, model: result.model, category: result.category, references: result.references || [], status: 'done', error: '' }
      this.persist([...messages, answer].slice(-40))
      if (this.alive) this.setData({ mode: result.mode === 'llm' ? 'DeepSeek 问答' : '知识库模式', error: result.notice || '' })
    } catch (error) {
      this.persist(this.data.messages.map(item => item.id === user.id ? { ...item, status: 'failed' as const, error: messageError(error) } : item))
    }
  },
  async retry(event: WechatMiniprogram.TapEvent) {
    if (this.data.sending) return
    const index = this.data.messages.findIndex(item => item.id === event.currentTarget.dataset.id)
    const user = this.data.messages[index]
    if (!user || user.role !== 'user') return
    this.setData({ sending: true, error: '' })
    try {
      await this.fetchAnswer(user, this.data.messages.slice(0, index))
    } catch (error) { this.setData({ error: messageError(error) }) }
    finally { if (this.alive) this.setData({ sending: false }) }
  },
  copyMessage(event: WechatMiniprogram.TapEvent) {
    const item = this.data.messages.find(message => message.id === event.currentTarget.dataset.id)
    if (item) wx.setClipboardData({ data: item.content })
  },
  copyReference(event: WechatMiniprogram.TapEvent) { wx.setClipboardData({ data: String(event.currentTarget.dataset.url || '') }) },
  consult(event: WechatMiniprogram.TapEvent) {
    const index = this.data.messages.findIndex(item => item.id === event.currentTarget.dataset.id)
    const question = this.data.messages.slice(0, index).reverse().find(item => item.role === 'user')
    const answer = this.data.messages[index]
    wx.navigateTo({ url: `/pages/consultation/consultation?question=${encodeURIComponent(question?.content || '')}&category=${answer?.category || 'health'}` })
  },
  newChat() {
    if (this.data.sending) return
    wx.showModal({ title: '清空当前会话？', content: '本机保存的问答将被删除，已提交的咨询单会保留。', success: result => {
      if (result.confirm) {
        try { this.persist([]); this.setData({ error: '' }) }
        catch (_) { wx.showToast({ title: '保存失败，请重试', icon: 'none' }) }
      }
    } })
  },
  settings() { wx.navigateTo({ url: '/pages/support-settings/support-settings' }) }
})
