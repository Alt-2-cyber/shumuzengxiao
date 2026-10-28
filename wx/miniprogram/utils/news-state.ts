export interface CattleArticle {
  id: string; kind: string; category: string; title: string; summary: string; content: string
  sourceName: string; sourceUrl: string; publishedAt: string; publishedDate?: string; collectedAt: string
}
export interface NewsSource {
  id: string; name: string; url: string; status: string; lastAttemptAt: string | null
  lastSuccessAt: string | null; articleCount: number
}
export interface NewsFeed {
  articles: CattleArticle[]; sources: NewsSource[]; dailyDate: string; dailyKnowledgeId: string
  refreshing: boolean; generatedAt: string
}
export interface NewsMessage { id: string; articleId: string; title: string; label: string; receivedAt: string; read: boolean }
export interface NewsPreferences { newsEnabled: boolean; dailyKnowledge: boolean; categories: string[] }
export interface NewsState {
  preferences: NewsPreferences; favorites: CattleArticle[]; readIds: string[]
  messages: NewsMessage[]; knownIds: string[]; initialized: boolean
}
export const newsCategories = [
  { id: 'health', name: '健康防疫' }, { id: 'nutrition', name: '饲养营养' },
  { id: 'environment', name: '环境管理' }, { id: 'industry', name: '行业动态' }, { id: 'market', name: '市场行情' }
]
export function emptyNewsState(): NewsState {
  return { preferences: { newsEnabled: true, dailyKnowledge: true, categories: newsCategories.map(item => item.id) },
    favorites: [], readIds: [], messages: [], knownIds: [], initialized: false }
}
export function newsCategoryName(id: string): string { return newsCategories.find(item => item.id === id)?.name || '行业动态' }
export function articleDate(article: CattleArticle): string { return article.publishedDate || new Date(Date.parse(article.publishedAt) + 28800000).toISOString().slice(0, 10) }
export function applyNewsFeed(state: NewsState, feed: NewsFeed, receivedAt: string): NewsState {
  const news = feed.articles.filter(item => item.kind === 'news')
  const matching = news.filter(item => state.preferences.categories.includes(item.category))
  const incoming = state.initialized ? matching.filter(item => !state.knownIds.includes(item.id)) : matching.slice(0, 3)
  const additions: NewsMessage[] = []
  if (state.preferences.newsEnabled) {
    incoming.slice(0, 10).forEach(item => additions.push({ id: `news:${item.id}`, articleId: item.id, title: item.title,
      label: state.initialized ? '新闻更新' : '资讯推荐', receivedAt, read: false }))
  }
  const daily = feed.articles.find(item => item.id === feed.dailyKnowledgeId)
  const dailyMessageId = `tip:${feed.dailyDate}`
  if (state.preferences.dailyKnowledge && daily && !state.messages.some(item => item.id === dailyMessageId)) {
    additions.unshift({ id: dailyMessageId, articleId: daily.id, title: daily.title, label: '今日小知识', receivedAt, read: false })
  }
  const known = [...news.map(item => item.id), ...state.knownIds]
  return { ...state, initialized: true, knownIds: [...new Set(known)].slice(0, 500),
    messages: [...additions.filter(item => !state.messages.some(old => old.id === item.id)), ...state.messages].slice(0, 100),
    favorites: state.favorites.map(saved => feed.articles.find(item => item.id === saved.id) || saved) }
}
export function markNewsRead(state: NewsState, id: string): NewsState {
  return { ...state, readIds: [id, ...state.readIds.filter(old => old !== id)].slice(0, 500),
    messages: state.messages.map(item => item.articleId === id ? { ...item, read: true } : item) }
}
export function markAllNewsRead(state: NewsState): NewsState { return { ...state, messages: state.messages.map(item => ({ ...item, read: true })) } }
export function toggleNewsFavorite(state: NewsState, article: CattleArticle): NewsState {
  const exists = state.favorites.some(item => item.id === article.id)
  if (!exists && state.favorites.length >= 100) throw new Error('最多可收藏 100 条，请先取消部分收藏')
  return { ...state, favorites: exists ? state.favorites.filter(item => item.id !== article.id) : [article, ...state.favorites] }
}
export function unreadNewsCount(state: NewsState): number { return state.messages.filter(item => !item.read).length }
