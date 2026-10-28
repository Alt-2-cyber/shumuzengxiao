import { CattleArticle, NewsFeed, NewsMessage, NewsState, cachedNewsFeed, newsCategories, newsCategoryName,
  openNews, readNewsState, refreshNews, saveNewsState, unreadNewsCount, markAllNewsRead, articleDate } from '../../utils/news'
import { displayTime, messageError } from '../../utils/support'
interface ArticleRow extends CattleArticle { categoryText: string; dateText: string; unread: boolean; saved: boolean }
interface MessageRow extends NewsMessage { timeText: string }
interface BooleanChange { detail: { value: boolean } }
interface TopicsChange { detail: { value: string[] } }
function rows(articles: CattleArticle[], state: NewsState): ArticleRow[] {
  return articles.map(item => ({ ...item, categoryText: newsCategoryName(item.category), dateText: articleDate(item),
    unread: !state.readIds.includes(item.id), saved: state.favorites.some(saved => saved.id === item.id) }))
}
Page({
  data: { tab: 'news', category: 'all', search: '', articles: [] as ArticleRow[], messages: [] as MessageRow[],
    state: readNewsState(), categories: newsCategories, daily: null as ArticleRow | null, unread: 0,
    loading: false, error: '', cached: false, updatedText: '', sourceText: '', settingsOpen: false },
  feed: null as NewsFeed | null,
  poll: 0,
  active: false,
  onShow() {
    this.active = true
    this.setData({ loading: false })
    this.feed = cachedNewsFeed()
    this.renderFeed()
    this.load(false)
    this.poll = setInterval(() => this.load(false), 60000)
  },
  onHide() { this.stopPoll() },
  onUnload() { this.stopPoll() },
  stopPoll() { this.active = false; if (this.poll) clearInterval(this.poll); this.poll = 0 },
  async onPullDownRefresh() { await this.load(true); wx.stopPullDownRefresh() },
  async load(force = true) {
    if (this.data.loading) return
    this.setData({ loading: true, error: '' })
    try {
      const feed = await refreshNews(force)
      if (!this.active) return
      this.feed = feed
      this.setData({ cached: false })
      this.renderFeed()
    } catch (error) { if (this.active) this.setData({ error: messageError(error), cached: !!this.feed }) }
    finally { if (this.active) this.setData({ loading: false }) }
  },
  refresh() { this.load(true) },
  renderFeed() {
    const state = readNewsState()
    const all = this.data.tab === 'saved' ? state.favorites : (this.feed?.articles || []).filter(item => item.kind === (this.data.tab === 'knowledge' ? 'knowledge' : 'news'))
    const query = this.data.search.trim().toLowerCase()
    const filtered = all.filter(item => (this.data.category === 'all' || item.category === this.data.category)
      && (!query || `${item.title} ${item.summary} ${item.sourceName}`.toLowerCase().includes(query)))
    const daily = this.feed?.articles.find(item => item.id === this.feed?.dailyKnowledgeId)
    const goodSources = this.feed?.sources.filter(item => item.lastSuccessAt) || []
    const latest = goodSources.map(item => item.lastSuccessAt || '').sort().reverse()[0]
    this.setData({ state, categories: newsCategories.map(item => ({ ...item, selected: state.preferences.categories.includes(item.id) })), articles: rows(filtered, state), unread: unreadNewsCount(state),
      daily: daily ? rows([daily], state)[0] : null,
      messages: state.messages.map(item => ({ ...item, timeText: new Date(item.receivedAt).toLocaleString() })),
      updatedText: latest ? displayTime(latest) : this.feed?.refreshing ? '来源同步中' : '尚未同步新闻',
      sourceText: this.feed ? this.feed.sources.map(item => `${item.name}：${item.status === 'ok' ? '已更新' : item.status === 'pending' ? '同步中' : '暂不可用'}`).join(' · ') : '' })
  },
  changeTab(event: WechatMiniprogram.TapEvent) { this.setData({ tab: String(event.currentTarget.dataset.tab), category: 'all', search: '' }); this.renderFeed() },
  changeCategory(event: WechatMiniprogram.TapEvent) { this.setData({ category: String(event.currentTarget.dataset.id) }); this.renderFeed() },
  changeSearch(event: WechatMiniprogram.InputEvent) { this.setData({ search: event.detail.value }); this.renderFeed() },
  open(event: WechatMiniprogram.TapEvent) { try { openNews(String(event.currentTarget.dataset.id)); this.renderFeed() } catch (error) { this.setData({ error: messageError(error) }) } },
  openDaily() { if (this.data.daily) openNews(this.data.daily.id) },
  markAll() { try { saveNewsState(markAllNewsRead(readNewsState())); this.renderFeed() } catch (error) { this.setData({ error: messageError(error) }) } },
  settings() { this.setData({ settingsOpen: !this.data.settingsOpen }) },
  toggleNews(event: BooleanChange) { this.updatePreference('newsEnabled', event.detail.value) },
  toggleDaily(event: BooleanChange) { this.updatePreference('dailyKnowledge', event.detail.value) },
  updatePreference(key: 'newsEnabled' | 'dailyKnowledge', value: boolean) {
    const state = readNewsState()
    try { saveNewsState({ ...state, preferences: { ...state.preferences, [key]: value } }); this.renderFeed() }
    catch (error) { this.setData({ error: messageError(error) }) }
  },
  toggleTopics(event: TopicsChange) {
    const state = readNewsState()
    try { saveNewsState({ ...state, preferences: { ...state.preferences, categories: event.detail.value } }); this.renderFeed() }
    catch (error) { this.setData({ error: messageError(error) }) }
  }
})
