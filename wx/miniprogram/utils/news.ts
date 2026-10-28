import { getSettings } from './support'
import { CattleArticle, NewsFeed, NewsState, applyNewsFeed, emptyNewsState, markNewsRead, unreadNewsCount } from './news-state'
export * from './news-state'
const STATE_KEY = 'cattle_news_state_v1'
const FEED_KEY = 'cattle_news_feed_v1'
export function readNewsState(): NewsState {
  const state = wx.getStorageSync(STATE_KEY) as NewsState | undefined
  return state && state.preferences && Array.isArray(state.messages) && Array.isArray(state.favorites) ? state : emptyNewsState()
}
export function saveNewsState(state: NewsState): void { wx.setStorageSync(STATE_KEY, state) }
export function cachedNewsFeed(): NewsFeed | null {
  const cache = wx.getStorageSync(FEED_KEY) as { baseUrl: string; feed: NewsFeed; fetchedAt: number } | undefined
  return cache && cache.baseUrl === getSettings().baseUrl && Array.isArray(cache.feed.articles) ? cache.feed : null
}
function fetchNews<T>(path: string): Promise<T> {
  const settings = getSettings()
  return new Promise((resolve, reject) => wx.request({ url: `${settings.baseUrl}/api/mobile-support/news${path}`,
    method: 'GET', timeout: 12000, header: { ...(settings.apiKey ? { Authorization: `Bearer ${settings.apiKey}` } : {}) },
    success(response) {
      if (response.statusCode === 200) resolve(response.data as T)
      else reject(new Error(response.statusCode === 401 || response.statusCode === 403 ? '请检查平台访问凭证' : '资讯服务暂不可用'))
    }, fail() { reject(new Error('资讯更新失败，请检查网络和服务地址')) }
  }))
}
let refreshing: Promise<NewsFeed> | null = null
export async function refreshNews(force = false): Promise<NewsFeed> {
  const cache = wx.getStorageSync(FEED_KEY) as { baseUrl: string; feed: NewsFeed; fetchedAt: number } | undefined
  if (!force && cache && cache.baseUrl === getSettings().baseUrl && Date.now() - cache.fetchedAt < 60000) {
    saveNewsState(applyNewsFeed(readNewsState(), cache.feed, new Date().toISOString()))
    return cache.feed
  }
  if (!refreshing) {
    const baseUrl = getSettings().baseUrl
    refreshing = fetchNews<NewsFeed>('/feed').then(feed => {
      if (!feed || !Array.isArray(feed.articles)) throw new Error('资讯数据格式异常')
      wx.setStorageSync(FEED_KEY, { baseUrl, feed, fetchedAt: Date.now() })
      saveNewsState(applyNewsFeed(readNewsState(), feed, new Date().toISOString()))
      return feed
    }).finally(() => { refreshing = null })
  }
  return refreshing
}
export async function getNewsArticle(id: string): Promise<CattleArticle> {
  const cached = cachedNewsFeed()?.articles.find(item => item.id === id) || readNewsState().favorites.find(item => item.id === id)
  return cached || fetchNews<CattleArticle>(`/articles/${encodeURIComponent(id)}`)
}
export function openNews(id: string): void {
  saveNewsState(markNewsRead(readNewsState(), id))
  wx.navigateTo({ url: `/pages/news-detail/news-detail?id=${encodeURIComponent(id)}` })
}
export function newsHomePreview(): { newsUnread: number; dailyTitle: string; dailyId: string } {
  const feed = cachedNewsFeed()
  const daily = feed?.articles.find(item => item.id === feed.dailyKnowledgeId)
  return { newsUnread: unreadNewsCount(readNewsState()), dailyTitle: daily?.title || '养牛新闻与每日小知识', dailyId: daily?.id || '' }
}
