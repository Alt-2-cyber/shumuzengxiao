import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { http } from '@kit.NetworkKit';
import { util } from '@kit.ArkTS';
import { pasteboard } from '@kit.BasicServicesKit';

export interface ServiceSettings { baseUrl: string; apiKey: string; }
export interface SupportReference { title: string; url: string; }
export interface AssistantAnswer {
  answer: string; mode: string; model: string; notice: string; category: string; references: SupportReference[];
}
export interface ChatMessage {
  id: string; role: string; content: string; time: string; mode: string; model: string;
  category: string; references: SupportReference[]; status: string; error: string;
}
export interface ConsultationDraft {
  requestId: string; category: string; priority: string; subject: string;
  description: string; cattleId: string; contact: string;
}
export interface Consultation {
  id: string; category: string; priority: string; subject: string; description: string;
  cattleId: string; contact: string; status: string; createdAt: string; updatedAt: string;
}
export interface SupportCategory { id: string; name: string; scope: string; }
export interface SupportPriority { id: string; name: string; }
export interface SupportCatalog { mode: string; categories: SupportCategory[]; }
interface HistoryMessage { role: string; content: string; }
interface QuestionBody { question: string; history: HistoryMessage[]; }
interface ConsultationCache { baseUrl: string; items: Consultation[]; }

export const SUPPORT_CATEGORIES: SupportCategory[] = [
  { id: 'health', name: '牛病与健康', scope: '跛行、咳嗽、体温与体表异常' },
  { id: 'nutrition', name: '饲养与营养', scope: '采食、反刍、饮水与日粮管理' },
  { id: 'equipment', name: '设备与环境', scope: '传感器、网络、通风与数据排查' },
  { id: 'other', name: '其他问题', scope: '综合巡检与管理问题' }
];
export const SUPPORT_PRIORITIES: SupportPriority[] = [
  { id: 'normal', name: '常规' }, { id: 'soon', name: '尽快' }, { id: 'urgent', name: '紧急' }
];

export function newSupportId(): string { return util.generateRandomUUID(); }
export function newDraft(): ConsultationDraft {
  return { requestId: newSupportId(), category: 'health', priority: 'normal', subject: '', description: '', cattleId: '', contact: '' };
}
export function categoryName(id: string): string { return SUPPORT_CATEGORIES.find(item => item.id === id)?.name ?? '其他问题'; }
export function priorityName(id: string): string { return SUPPORT_PRIORITIES.find(item => item.id === id)?.name ?? '常规'; }
export function displayTime(value: string): string {
  const date = new Date(value);
  const pad = (number: number): string => `${number}`.padStart(2, '0');
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}
export function draftError(draft: ConsultationDraft): string {
  if (draft.subject.trim().length < 5 || draft.subject.trim().length > 80) { return '问题标题需为 5–80 个字'; }
  if (draft.description.trim().length < 10 || draft.description.trim().length > 2000) { return '问题详情需为 10–2000 个字'; }
  if (draft.cattleId.length > 80 || draft.contact.length > 80) { return '耳标或联系方式不能超过 80 个字'; }
  return '';
}
export function errorMessage(error: Error): string { return error.message || '操作失败，请稍后重试'; }
export async function copySupportText(text: string): Promise<void> {
  await pasteboard.getSystemPasteboard().setData(pasteboard.createData(pasteboard.MIMETYPE_TEXT_PLAIN, text));
}

export class SupportService {
  private static store: preferences.Preferences | null = null;
  private static settings: ServiceSettings = { baseUrl: 'http://10.0.2.2:8080', apiKey: '' };
  private static token: string = '';

  static async init(context: common.UIAbilityContext): Promise<void> {
    if (SupportService.store !== null) { return; }
    const store = await preferences.getPreferences(context, 'cattle_support_v1');
    const saved = await store.get('settings', '') as string;
    if (saved) { SupportService.settings = JSON.parse(saved) as ServiceSettings; }
    SupportService.token = await store.get('identity', '') as string;
    if (!SupportService.token) {
      SupportService.token = newSupportId() + newSupportId();
      await store.put('identity', SupportService.token);
      await store.flush();
    }
    SupportService.store = store;
  }

  static getSettings(): ServiceSettings { return SupportService.settings; }
  static async saveSettings(baseUrl: string, apiKey: string): Promise<void> {
    const address = baseUrl.trim().replace(/\/+$/, '');
    if (!/^https?:\/\/[^\s/?#]+(?:\/[^\s?#]*)?$/i.test(address) || address.includes('@')) {
      throw new Error('请输入有效的 HTTP 或 HTTPS 服务地址');
    }
    const settings: ServiceSettings = { baseUrl: address, apiKey: apiKey.trim() };
    await SupportService.write('settings', JSON.stringify(settings));
    SupportService.settings = settings;
  }

  private static async read(key: string): Promise<string> {
    if (!SupportService.store) { throw new Error('本机存储未初始化'); }
    return await SupportService.store.get(key, '') as string;
  }
  private static async write(key: string, value: string): Promise<void> {
    if (!SupportService.store) { throw new Error('本机存储未初始化'); }
    await SupportService.store.put(key, value);
    await SupportService.store.flush();
  }
  static async readChat(): Promise<ChatMessage[]> {
    const value = await SupportService.read('chat');
    if (!value) { return []; }
    const messages = JSON.parse(value) as ChatMessage[];
    messages.forEach(item => {
      if (item.status === 'pending') { item.status = 'failed'; item.error = '上次请求未完成，请重试'; }
    });
    return messages.slice(-40);
  }
  static async saveChat(messages: ChatMessage[]): Promise<void> { await SupportService.write('chat', JSON.stringify(messages.slice(-40))); }
  static async readDraft(): Promise<ConsultationDraft> {
    const value = await SupportService.read('draft');
    return value ? JSON.parse(value) as ConsultationDraft : newDraft();
  }
  static async saveDraft(draft: ConsultationDraft): Promise<void> { await SupportService.write('draft', JSON.stringify(draft)); }
  static async clearDraft(): Promise<void> { await SupportService.write('draft', ''); }
  static async readCache(): Promise<Consultation[]> {
    const value = await SupportService.read('consultations');
    if (!value) { return []; }
    const cache = JSON.parse(value) as ConsultationCache;
    return cache.baseUrl === SupportService.settings.baseUrl ? cache.items : [];
  }
  static async cache(items: Consultation[]): Promise<void> {
    const cache: ConsultationCache = { baseUrl: SupportService.settings.baseUrl, items: items };
    await SupportService.write('consultations', JSON.stringify(cache));
  }

  private static async request<T>(path: string, body: string = ''): Promise<T> {
    const connection = http.createHttp();
    try {
      const response = await connection.request(`${SupportService.settings.baseUrl}/api/mobile-support${path}`, {
        method: body ? http.RequestMethod.POST : http.RequestMethod.GET,
        header: { 'Content-Type': 'application/json', 'Authorization': SupportService.settings.apiKey ? `Bearer ${SupportService.settings.apiKey}` : '', 'X-Mobile-Token': SupportService.token },
        extraData: body, connectTimeout: 6000, readTimeout: 25000, usingCache: false,
        expectDataType: http.HttpDataType.STRING
      });
      if (response.responseCode === 401 || response.responseCode === 403) { throw new Error('访问凭证无效或权限不足，请检查服务设置'); }
      if (response.responseCode === 400) { throw new Error('填写内容未通过校验，请检查后重试'); }
      if (response.responseCode === 409) { throw new Error('咨询编号冲突，请新建咨询'); }
      if (response.responseCode < 200 || response.responseCode >= 300) { throw new Error(`服务暂不可用（${response.responseCode}）`); }
      return JSON.parse(response.result as string) as T;
    } catch (error) {
      const message = (error as Error).message;
      if (message && (message.startsWith('访问') || message.startsWith('填写') || message.startsWith('咨询') || message.startsWith('服务'))) {
        throw new Error(message);
      }
      throw new Error('连接失败，请检查网络和服务地址');
    } finally { connection.destroy(); }
  }

  static async catalog(): Promise<SupportCatalog> { return SupportService.request<SupportCatalog>('/catalog'); }
  static async ask(question: string, messages: ChatMessage[]): Promise<AssistantAnswer> {
    const history: HistoryMessage[] = messages.filter(item => item.status === 'done').slice(-8).map((item: ChatMessage): HistoryMessage => {
      return { role: item.role, content: item.content.slice(0, 2000) };
    });
    const body: QuestionBody = { question: question, history: history };
    return SupportService.request<AssistantAnswer>('/assistant', JSON.stringify(body));
  }
  static async consultations(): Promise<Consultation[]> { return SupportService.request<Consultation[]>('/consultations'); }
  static async submit(draft: ConsultationDraft): Promise<Consultation> { return SupportService.request<Consultation>('/consultations', JSON.stringify(draft)); }
  static async cancel(id: string): Promise<Consultation> { return SupportService.request<Consultation>(`/consultations/${encodeURIComponent(id)}/cancel`, '{}'); }
}
