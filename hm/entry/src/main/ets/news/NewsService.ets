import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { http } from '@kit.NetworkKit';
import { SupportService } from '../support/SupportService';

export interface CattleArticle {
  id: string; kind: string; category: string; title: string; summary: string; content: string;
  sourceName: string; sourceUrl: string; publishedAt: string; publishedDate?: string; collectedAt: string;
}
export interface NewsSource {
  id: string; name: string; url: string; status: string; lastAttemptAt: string | null;
  lastSuccessAt: string | null; articleCount: number;
}
export interface NewsFeed {
  articles: CattleArticle[]; sources: NewsSource[]; dailyDate: string; dailyKnowledgeId: string;
  refreshing: boolean; generatedAt: string;
}
export interface NewsMessage { id: string; articleId: string; title: string; label: string; receivedAt: string; read: boolean; }
export interface NewsPreferences { newsEnabled: boolean; dailyKnowledge: boolean; categories: string[]; }
export interface NewsState {
  preferences: NewsPreferences; favorites: CattleArticle[]; readIds: string[];
  messages: NewsMessage[]; knownIds: string[]; initialized: boolean;
}
interface NewsCache { baseUrl: string; feed: NewsFeed; fetchedAt: number; }
export interface NewsCategory { id: string; name: string; }
export const NEWS_CATEGORIES: NewsCategory[] = [
  { id: 'health', name: '健康防疫' }, { id: 'nutrition', name: '饲养营养' },
  { id: 'environment', name: '环境管理' }, { id: 'industry', name: '行业动态' }, { id: 'market', name: '市场行情' }
];
export function categoryLabel(id: string): string { return NEWS_CATEGORIES.find(item => item.id === id)?.name ?? '行业动态'; }
export function articleDate(article: CattleArticle): string { return article.publishedDate || new Date(Date.parse(article.publishedAt) + 28800000).toISOString().slice(0, 10); }
export function emptyNewsState(): NewsState {
  return { preferences: { newsEnabled: true, dailyKnowledge: true, categories: NEWS_CATEGORIES.map(item => item.id) },
    favorites: [], readIds: [], messages: [], knownIds: [], initialized: false };
}
export function cloneNewsState(state: NewsState): NewsState { return JSON.parse(JSON.stringify(state)) as NewsState; }
export function unreadNews(state: NewsState): number { return state.messages.filter(item => !item.read).length; }

export class NewsService {
  private static store: preferences.Preferences | null = null;
  private static pending: Promise<NewsFeed> | null = null;
  static async init(context: common.UIAbilityContext): Promise<void> {
    await SupportService.init(context);
    if (!NewsService.store) { NewsService.store = await preferences.getPreferences(context, 'cattle_news_v1'); }
  }
  static async state(): Promise<NewsState> {
    if (!NewsService.store) { throw new Error('本机资讯存储未初始化'); }
    const value = await NewsService.store.get('state', '') as string;
    return value ? JSON.parse(value) as NewsState : emptyNewsState();
  }
  static async save(state: NewsState): Promise<void> {
    if (!NewsService.store) { throw new Error('本机资讯存储未初始化'); }
    await NewsService.store.put('state', JSON.stringify(state));
    await NewsService.store.flush();
  }
  private static async cache(): Promise<NewsCache | null> {
    if (!NewsService.store) { return null; }
    const value = await NewsService.store.get('feed', '') as string;
    if (!value) { return null; }
    const cache = JSON.parse(value) as NewsCache;
    return cache.baseUrl === SupportService.getSettings().baseUrl ? cache : null;
  }
  static async cachedFeed(): Promise<NewsFeed | null> { return (await NewsService.cache())?.feed ?? null; }
  private static async request<T>(path: string): Promise<T> {
    const connection = http.createHttp();
    const settings = SupportService.getSettings();
    try {
      const response = await connection.request(`${settings.baseUrl}/api/mobile-support/news${path}`, {
        method: http.RequestMethod.GET, header: { 'Authorization': settings.apiKey ? `Bearer ${settings.apiKey}` : '' },
        connectTimeout: 5000, readTimeout: 12000, usingCache: false, expectDataType: http.HttpDataType.STRING
      });
      if (response.responseCode === 401 || response.responseCode === 403) { throw new Error('请检查平台访问凭证'); }
      if (response.responseCode !== 200) { throw new Error('资讯服务暂不可用'); }
      return JSON.parse(response.result as string) as T;
    } catch (error) {
      if ((error as Error).message.startsWith('请检查') || (error as Error).message.startsWith('资讯服务')) { throw new Error((error as Error).message); }
      throw new Error('资讯更新失败，请检查网络和服务地址');
    } finally { connection.destroy(); }
  }
  static async refresh(force: boolean = false): Promise<NewsFeed> {
    const cache = await NewsService.cache();
    if (!force && cache && Date.now() - cache.fetchedAt < 60000) { await NewsService.receive(cache.feed); return cache.feed; }
    if (!NewsService.pending) { NewsService.pending = NewsService.fetchFeed(); }
    return NewsService.pending;
  }
  private static async fetchFeed(): Promise<NewsFeed> {
    try {
      const baseUrl = SupportService.getSettings().baseUrl;
      const feed = await NewsService.request<NewsFeed>('/feed');
      const cache: NewsCache = { baseUrl: baseUrl, feed: feed, fetchedAt: Date.now() };
      if (NewsService.store) { await NewsService.store.put('feed', JSON.stringify(cache)); await NewsService.store.flush(); }
      await NewsService.receive(feed);
      return feed;
    } finally { NewsService.pending = null; }
  }
  private static async receive(feed: NewsFeed): Promise<void> {
    const state = cloneNewsState(await NewsService.state());
    const news = feed.articles.filter(item => item.kind === 'news');
    const matching = news.filter(item => state.preferences.categories.includes(item.category));
    const incoming = state.initialized ? matching.filter(item => !state.knownIds.includes(item.id)) : matching.slice(0, 3);
    const additions: NewsMessage[] = [];
    const now = new Date().toISOString();
    if (state.preferences.newsEnabled) {
      incoming.slice(0, 10).forEach(item => {
        const message: NewsMessage = { id: `news:${item.id}`, articleId: item.id, title: item.title,
          label: state.initialized ? '新闻更新' : '资讯推荐', receivedAt: now, read: false };
        additions.push(message);
      });
    }
    const daily = feed.articles.find(item => item.id === feed.dailyKnowledgeId);
    if (state.preferences.dailyKnowledge && daily && !state.messages.some(item => item.id === `tip:${feed.dailyDate}`)) {
      const message: NewsMessage = { id: `tip:${feed.dailyDate}`, articleId: daily.id, title: daily.title,
        label: '今日小知识', receivedAt: now, read: false };
      additions.unshift(message);
    }
    state.messages = additions.filter(item => !state.messages.some(old => old.id === item.id)).concat(state.messages).slice(0, 100);
    state.knownIds = Array.from(new Set<string>(news.map(item => item.id).concat(state.knownIds))).slice(0, 500);
    state.favorites = state.favorites.map(saved => feed.articles.find(item => item.id === saved.id) ?? saved);
    state.initialized = true;
    await NewsService.save(state);
  }
  static async article(id: string): Promise<CattleArticle> {
    const cached = (await NewsService.cachedFeed())?.articles.find(item => item.id === id);
    if (cached) { return cached; }
    const favorite = (await NewsService.state()).favorites.find(item => item.id === id);
    return favorite ?? NewsService.request<CattleArticle>(`/articles/${encodeURIComponent(id)}`);
  }
  static async markRead(id: string): Promise<void> {
    const state = cloneNewsState(await NewsService.state());
    state.readIds = [id].concat(state.readIds.filter(old => old !== id)).slice(0, 500);
    state.messages.forEach(item => { if (item.articleId === id) { item.read = true; } });
    await NewsService.save(state);
  }
  static async markAllRead(): Promise<void> {
    const state = cloneNewsState(await NewsService.state());
    state.messages.forEach(item => { item.read = true; });
    await NewsService.save(state);
  }
  static async favorite(article: CattleArticle): Promise<boolean> {
    const state = cloneNewsState(await NewsService.state());
    const exists = state.favorites.some(item => item.id === article.id);
    if (!exists && state.favorites.length >= 100) { throw new Error('最多可收藏 100 条，请先取消部分收藏'); }
    state.favorites = exists ? state.favorites.filter(item => item.id !== article.id) : [article].concat(state.favorites);
    await NewsService.save(state);
    return !exists;
  }
}
