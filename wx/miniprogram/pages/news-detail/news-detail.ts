import { CattleArticle, getNewsArticle, markNewsRead, newsCategoryName, readNewsState, saveNewsState, toggleNewsFavorite, articleDate } from '../../utils/news'
import { messageError } from '../../utils/support'
Page({
  data: { article: null as CattleArticle | null, loading: true, error: '', saved: false, categoryText: '', dateText: '' },
  articleId: '',
  onLoad(options: Record<string, string | undefined>) { this.articleId = options.id || ''; this.load() },
  async load() {
    this.setData({ loading: true, error: '' })
    try {
      const article = await getNewsArticle(this.articleId)
      const state = markNewsRead(readNewsState(), article.id)
      saveNewsState(state)
      this.setData({ article, saved: state.favorites.some(item => item.id === article.id), categoryText: newsCategoryName(article.category), dateText: articleDate(article) })
    } catch (error) { this.setData({ error: messageError(error) }) }
    finally { this.setData({ loading: false }) }
  },
  favorite() {
    if (!this.data.article) return
    try {
      const state = toggleNewsFavorite(readNewsState(), this.data.article)
      saveNewsState(state)
      this.setData({ saved: state.favorites.some(item => item.id === this.data.article?.id) })
    } catch (error) { this.setData({ error: messageError(error) }) }
  },
  original() { if (this.data.article) wx.setClipboardData({ data: this.data.article.sourceUrl }) },
  ask() {
    if (!this.data.article) return
    wx.navigateTo({ url: `/pages/assistant/assistant?question=${encodeURIComponent(`关于“${this.data.article.title}”，牛场日常管理要注意什么？`)}` })
  },
  consult() {
    if (!this.data.article) return
    const question = `我想咨询“${this.data.article.title}”相关的牛场管理问题。`
    wx.navigateTo({ url: `/pages/consultation/consultation?question=${encodeURIComponent(question)}&category=${this.data.article.category === 'nutrition' ? 'nutrition' : this.data.article.category === 'environment' ? 'equipment' : 'health'}` })
  }
})
