import { Consultation, ConsultationDraft, cacheConsultations, cachedConsultations, cancelConsultation, categories,
  categoryName, clearDraft, displayTime, draftError, emptyDraft, getConsultations, messageError, priorities,
  priorityName, readDraft, saveDraft, submitConsultation } from '../../utils/support'

interface ConsultationRow extends Consultation { categoryText: string; priorityText: string; timeText: string }
function rows(items: Consultation[]): ConsultationRow[] {
  return items.map(item => ({ ...item, categoryText: categoryName(item.category), priorityText: priorityName(item.priority), timeText: displayTime(item.createdAt) }))
}
Page({
  data: {
    tab: 'new', categories, priorities, draft: emptyDraft(), records: [] as ConsultationRow[],
    selected: null as ConsultationRow | null, loading: false, sending: false, error: '', notice: '', cancelling: false
  },
  onLoad(options: Record<string, string | undefined>) {
    const draft = readDraft()
    const question = options.question ? decodeURIComponent(options.question) : ''
    if (question) {
      if (draft.subject || draft.description) {
        wx.showModal({ title: '保留已有草稿？', content: '替换后将带入 AI 会话中的问题。', confirmText: '带入问题', cancelText: '保留草稿', success: result => {
          if (result.confirm) this.importQuestion(question, options.category || 'health')
        } })
      } else this.importQuestion(question, options.category || 'health')
    }
    this.setData({ draft: question && !draft.subject && !draft.description ? this.data.draft : draft, records: rows(cachedConsultations()) })
  },
  importQuestion(question: string, category: string) {
    const draft = { ...emptyDraft(), subject: question.slice(0, 80), description: question.slice(0, 2000),
      category: categories.some(item => item.id === category) ? category : 'health' }
    this.updateDraft(draft)
  },
  updateDraft(draft: ConsultationDraft) {
    this.setData({ draft })
    try { saveDraft(draft) }
    catch (_) { this.setData({ error: '草稿未能保存到本机，请检查存储空间' }) }
  },
  changeField(event: WechatMiniprogram.InputEvent) {
    const field = event.currentTarget.dataset.field as keyof ConsultationDraft
    if (!['subject', 'description', 'cattleId', 'contact'].includes(field)) return
    this.updateDraft({ ...this.data.draft, [field]: event.detail.value })
  },
  chooseCategory(event: WechatMiniprogram.TapEvent) { this.updateDraft({ ...this.data.draft, category: String(event.currentTarget.dataset.id) }) },
  choosePriority(event: WechatMiniprogram.TapEvent) { this.updateDraft({ ...this.data.draft, priority: String(event.currentTarget.dataset.id) }) },
  changeTab(event: WechatMiniprogram.TapEvent) {
    this.setData({ tab: String(event.currentTarget.dataset.tab), selected: null, error: '', notice: '' })
    if (this.data.tab === 'records') this.refresh()
  },
  async refresh() {
    if (this.data.loading) return
    this.setData({ loading: true, error: '', notice: '' })
    try {
      const items = await getConsultations()
      this.setData({ records: rows(items) })
      cacheConsultations(items)
    } catch (error) {
      this.setData({ error: messageError(error), notice: this.data.records.length ? '以下为本机缓存，当前状态尚未刷新' : '' })
    } finally { this.setData({ loading: false }) }
  },
  async submit() {
    if (this.data.sending) return
    const error = draftError(this.data.draft)
    if (error) { this.setData({ error }); return }
    this.setData({ sending: true, error: '', notice: '' })
    try {
      const item = await submitConsultation(this.data.draft)
      const records = rows([item, ...this.data.records.filter(record => record.id !== item.id)])
      this.setData({ records, selected: records[0], tab: 'records', draft: emptyDraft(),
        notice: '平台已收件，等待受理；尚未分配专家。' })
      try { clearDraft(); cacheConsultations(records) } catch (_) { /* Server receipt remains authoritative. */ }
    } catch (failure) { this.setData({ error: `${messageError(failure)}；草稿已保留，可使用原咨询编号重试。` }) }
    finally { this.setData({ sending: false }) }
  },
  openRecord(event: WechatMiniprogram.TapEvent) {
    this.setData({ selected: this.data.records.find(item => item.id === event.currentTarget.dataset.id) || null, error: '', notice: '' })
  },
  closeRecord() { this.setData({ selected: null }) },
  cancel() {
    if (!this.data.selected || this.data.cancelling) return
    const id = this.data.selected.id
    wx.showModal({ title: '撤回这条咨询？', content: '咨询单会保留在记录中，状态改为已撤回。', success: async result => {
      if (!result.confirm) return
      this.setData({ cancelling: true, error: '' })
      try {
        const item = await cancelConsultation(id)
        const records = rows(this.data.records.map(record => record.id === id ? item : record))
        this.setData({ records, selected: records.find(record => record.id === id) || null })
        cacheConsultations(records)
      } catch (error) { this.setData({ error: messageError(error) }) }
      finally { this.setData({ cancelling: false }) }
    } })
  },
  resetDraft() {
    wx.showModal({ title: '清空草稿？', content: '尚未提交的内容会被清空。', success: result => {
      if (result.confirm) { this.updateDraft(emptyDraft()); this.setData({ error: '' }) }
    } })
  },
  settings() { wx.navigateTo({ url: '/pages/support-settings/support-settings' }) }
})
