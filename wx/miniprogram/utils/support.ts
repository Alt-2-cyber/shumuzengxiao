export interface ServiceSettings { baseUrl: string; apiKey: string }
export interface SupportReference { title: string; url: string }
export interface AssistantAnswer {
  answer: string; mode: string; model: string; notice: string; category: string; references: SupportReference[]
}
export interface ChatMessage {
  id: string; role: 'user' | 'assistant'; content: string; time: string
  mode: string; model: string; category: string; references: SupportReference[]
  status: 'done' | 'pending' | 'failed'; error: string
}
export interface ConsultationDraft {
  requestId: string; category: string; priority: string; subject: string
  description: string; cattleId: string; contact: string
}
export interface Consultation extends ConsultationDraft {
  id: string; status: string; createdAt: string; updatedAt: string
}
export interface SupportCategory { id: string; name: string; scope: string }
export const categories: SupportCategory[] = [
  { id: 'health', name: '牛病与健康', scope: '跛行、咳嗽、体温与体表异常' },
  { id: 'nutrition', name: '饲养与营养', scope: '采食、反刍、饮水与日粮管理' },
  { id: 'equipment', name: '设备与环境', scope: '传感器、网络、通风与数据排查' },
  { id: 'other', name: '其他问题', scope: '综合巡检与管理问题' }
]
export const priorities = [
  { id: 'normal', name: '常规' }, { id: 'soon', name: '尽快' }, { id: 'urgent', name: '紧急' }
]
const SETTINGS = 'cattle_support_settings_v1'
const CHAT = 'cattle_support_chat_v1'
const DRAFT = 'cattle_support_draft_v1'
const TOKEN = 'cattle_support_identity_v1'
const CACHE = 'cattle_support_consultations_v1'

export function makeId(): string {
  return `wx_${Date.now()}_${Math.random().toString(36).slice(2, 14)}_${Math.random().toString(36).slice(2, 10)}`
}
export function getSettings(): ServiceSettings {
  const value = wx.getStorageSync(SETTINGS) as ServiceSettings | undefined
  return value && typeof value.baseUrl === 'string' ? value : { baseUrl: 'http://127.0.0.1:8080', apiKey: '' }
}
export function saveSettings(value: ServiceSettings): void {
  const baseUrl = value.baseUrl.trim().replace(/\/+$/, '')
  if (!/^https?:\/\/[^\s/?#]+(?::\d+)?(?:\/[^\s?#]*)?$/i.test(baseUrl) || /@/.test(baseUrl)) {
    throw new Error('请输入有效的 HTTP 或 HTTPS 服务地址')
  }
  wx.setStorageSync(SETTINGS, { baseUrl, apiKey: value.apiKey.trim() })
}
export function readChat(): ChatMessage[] {
  const items = wx.getStorageSync(CHAT) as ChatMessage[] | undefined
  if (!Array.isArray(items)) return []
  return items.filter(item => item && typeof item.content === 'string' && (item.role === 'user' || item.role === 'assistant'))
    .slice(-40).map(item => item.status === 'pending'
      ? { ...item, status: 'failed', error: '上次请求未完成，请重试' } : item)
}
export function saveChat(items: ChatMessage[]): void { wx.setStorageSync(CHAT, items.slice(-40)) }
export function emptyDraft(): ConsultationDraft {
  return { requestId: makeId(), category: 'health', priority: 'normal', subject: '', description: '', cattleId: '', contact: '' }
}
export function readDraft(): ConsultationDraft {
  const draft = wx.getStorageSync(DRAFT) as ConsultationDraft | undefined
  return draft && typeof draft.requestId === 'string' ? draft : emptyDraft()
}
export function saveDraft(draft: ConsultationDraft): void { wx.setStorageSync(DRAFT, draft) }
export function clearDraft(): void { wx.removeStorageSync(DRAFT) }
export function cachedConsultations(): Consultation[] {
  const data = wx.getStorageSync(CACHE) as { baseUrl: string; items: Consultation[] } | undefined
  return data && data.baseUrl === getSettings().baseUrl && Array.isArray(data.items) ? data.items : []
}
export function cacheConsultations(items: Consultation[]): void {
  wx.setStorageSync(CACHE, { baseUrl: getSettings().baseUrl, items })
}
export function draftError(draft: ConsultationDraft): string {
  if (!categories.some(item => item.id === draft.category)) return '请选择咨询方向'
  if (draft.subject.trim().length < 5 || draft.subject.trim().length > 80) return '问题标题需为 5–80 个字'
  if (draft.description.trim().length < 10 || draft.description.trim().length > 2000) return '问题详情需为 10–2000 个字'
  if (draft.cattleId.length > 80 || draft.contact.length > 80) return '耳标或联系方式不能超过 80 个字'
  return ''
}
function request<T>(path: string, method: 'GET' | 'POST', body?: object, token = ''): Promise<T> {
  const settings = getSettings()
  return new Promise((resolve, reject) => {
    wx.request({
      url: `${settings.baseUrl}/api/mobile-support${path}`, method, data: body, timeout: 25000,
      header: { 'Content-Type': 'application/json', 'X-Mobile-Token': token,
        ...(settings.apiKey ? { Authorization: `Bearer ${settings.apiKey}` } : {}) },
      success(result) {
        if (result.statusCode >= 200 && result.statusCode < 300) resolve(result.data as T)
        else reject(new Error(result.statusCode === 401 || result.statusCode === 403 ? '访问凭证无效或权限不足，请检查服务设置'
          : result.statusCode === 400 ? '填写内容未通过校验，请检查后重试'
            : result.statusCode === 409 ? '咨询编号冲突，请新建咨询'
              : `服务暂不可用（${result.statusCode}），请稍后重试`))
      },
      fail() { reject(new Error('连接失败，请检查网络、服务地址和小程序合法域名设置')) }
    })
  })
}
let sessionPromise: Promise<string> | null = null
async function sessionToken(): Promise<string> {
  const token = wx.getStorageSync(TOKEN) as string | undefined
  if (token) return token
  if (!sessionPromise) {
    sessionPromise = request<{ token: string }>('/session', 'GET').then(result => {
      wx.setStorageSync(TOKEN, result.token)
      return result.token
    }).finally(() => { sessionPromise = null })
  }
  return sessionPromise
}
export function catalog(): Promise<{ mode: string; categories: SupportCategory[] }> { return request('/catalog', 'GET') }
export function askAssistant(question: string, messages: ChatMessage[]): Promise<AssistantAnswer> {
  const history = messages.filter(item => item.status === 'done').slice(-8)
    .map(item => ({ role: item.role, content: item.content.slice(0, 2000) }))
  return request('/assistant', 'POST', { question, history })
}
export async function getConsultations(): Promise<Consultation[]> {
  return request('/consultations', 'GET', undefined, await sessionToken())
}
export async function submitConsultation(draft: ConsultationDraft): Promise<Consultation> {
  return request('/consultations', 'POST', draft, await sessionToken())
}
export async function cancelConsultation(id: string): Promise<Consultation> {
  return request(`/consultations/${encodeURIComponent(id)}/cancel`, 'POST', {}, await sessionToken())
}
export function categoryName(id: string): string { return categories.find(item => item.id === id)?.name || '其他问题' }
export function priorityName(id: string): string { return priorities.find(item => item.id === id)?.name || '常规' }
export function displayTime(value: string): string {
  const time = new Date(value)
  if (Number.isNaN(time.getTime())) return value
  return `${time.getFullYear()}-${String(time.getMonth() + 1).padStart(2, '0')}-${String(time.getDate()).padStart(2, '0')} ${String(time.getHours()).padStart(2, '0')}:${String(time.getMinutes()).padStart(2, '0')}`
}
export function messageError(error: unknown): string { return error instanceof Error ? error.message : '操作失败，请稍后重试' }
