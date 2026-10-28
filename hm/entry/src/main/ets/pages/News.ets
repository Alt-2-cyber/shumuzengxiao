import { APP_FIELD, APP_MUTED, APP_PRIMARY, APP_PRIMARY_SOFT, APP_SUCCESS, APP_SUCCESS_SOFT, APP_WARNING } from '../support/AppTheme';
import { common } from '@kit.AbilityKit';
import { ArticleRow } from '../news/ArticleRow';
import { CattleArticle, NewsFeed, NewsMessage, NewsCategory, NewsSource, NewsState, NewsService, NEWS_CATEGORIES,
  cloneNewsState, emptyNewsState, unreadNews } from '../news/NewsService';
import { SUPPORT_BG, SUPPORT_PRIMARY, SUPPORT_LINE, SUPPORT_MUTED, SUPPORT_TEXT, SupportHeader, SupportNotice } from '../support/SupportUI';
import { displayTime } from '../support/SupportService';
interface ArticleParams { id: string; }

@Entry
@Component
struct NewsPage {
  @State tab: number = 0;
  @State category: string = 'all';
  @State query: string = '';
  @State state: NewsState = emptyNewsState();
  @State articles: CattleArticle[] = [];
  @State daily: CattleArticle | null = null;
  @State sources: NewsSource[] = [];
  @State loading: boolean = false;
  @State error: string = '';
  @State cached: boolean = false;
  @State subscriptions: boolean = false;
  private feed: NewsFeed | null = null;
  private initialized: boolean = false;
  private alive: boolean = true;
  private poll: number = -1;
  private contentScroller: Scroller = new Scroller();

  aboutToAppear(): void { this.alive = true; this.initialize(); }
  aboutToDisappear(): void { this.alive = false; this.stopPoll(); }
  onPageHide(): void { this.stopPoll(); }
  onPageShow(): void { if (this.initialized) { this.load(false); this.startPoll(); } }
  startPoll(): void { this.stopPoll(); this.poll = setInterval(() => this.load(false), 60000); }
  stopPoll(): void { if (this.poll >= 0) { clearInterval(this.poll); this.poll = -1; } }
  async initialize(): Promise<void> {
    try {
      await NewsService.init(getContext(this) as common.UIAbilityContext);
      this.feed = await NewsService.cachedFeed();
      this.state = await NewsService.state();
      this.renderFeed(); this.initialized = true;
      await this.load(false); this.startPoll();
    } catch (error) { this.error = '本机资讯记录读取失败'; }
  }
  async load(force: boolean = true): Promise<void> {
    if (this.loading) { return; }
    this.loading = true; this.error = '';
    try {
      const feed = await NewsService.refresh(force);
      if (!this.alive) { return; }
      this.feed = feed; this.state = await NewsService.state(); this.cached = false; this.renderFeed();
    } catch (error) { this.error = `${(error as Error).message}${this.feed ? '，当前显示上次缓存' : ''}`; this.cached = this.feed !== null; }
    finally { this.loading = false; }
  }
  renderFeed(): void {
    const list = this.tab === 2 ? this.state.favorites : (this.feed?.articles ?? []).filter(item => item.kind === (this.tab === 1 ? 'knowledge' : 'news'));
    const query = this.query.trim().toLowerCase();
    this.articles = list.filter(item => (this.category === 'all' || item.category === this.category) &&
      (!query || `${item.title} ${item.summary} ${item.sourceName}`.toLowerCase().includes(query)));
    this.daily = this.feed?.articles.find(item => item.id === this.feed?.dailyKnowledgeId) ?? null;
    this.sources = this.feed?.sources ?? [];
  }
  changeTab(index: number): void {
    this.tab = index; this.category = 'all'; this.query = ''; this.renderFeed();
    setTimeout((): void => { this.contentScroller.scrollEdge(Edge.Top); }, 40);
  }
  async open(id: string): Promise<void> {
    try {
      await NewsService.markRead(id); this.state = await NewsService.state();
      const params: ArticleParams = { id: id };
      this.getUIContext().getRouter().pushUrl({ url: 'pages/NewsDetail', params: params });
    } catch (error) { this.error = (error as Error).message; }
  }
  async markAll(): Promise<void> { try { await NewsService.markAllRead(); this.state = await NewsService.state(); } catch (error) { this.error = (error as Error).message; } }
  async togglePreference(key: string, enabled: boolean): Promise<void> {
    const state = cloneNewsState(this.state);
    if (key === 'news') { state.preferences.newsEnabled = enabled; } else { state.preferences.dailyKnowledge = enabled; }
    await this.persistState(state);
  }
  async toggleCategory(id: string, selected: boolean): Promise<void> {
    const state = cloneNewsState(this.state);
    state.preferences.categories = selected ? Array.from(new Set<string>(state.preferences.categories.concat([id]))) : state.preferences.categories.filter(value => value !== id);
    await this.persistState(state);
  }
  async persistState(state: NewsState): Promise<void> {
    try { await NewsService.save(state); this.state = state; } catch (error) { this.error = '订阅设置保存失败'; }
  }

  @Builder
  Subscriptions() {
    Row() {
      Column({ space: 6 }) { Text('新闻更新提醒').fontSize(16).fontColor(SUPPORT_TEXT); Text('站内消息').fontSize(12).fontColor(SUPPORT_MUTED) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Toggle({ type: ToggleType.Switch, isOn: this.state.preferences.newsEnabled }).selectedColor(SUPPORT_PRIMARY).onChange((enabled: boolean) => this.togglePreference('news', enabled))
    }.width('100%').padding({ top: 20, bottom: 20 })
    Row() {
      Column({ space: 6 }) { Text('每日养牛小知识').fontSize(16).fontColor(SUPPORT_TEXT); Text('每天推荐一张知识卡').fontSize(12).fontColor(SUPPORT_MUTED) }.layoutWeight(1).alignItems(HorizontalAlign.Start)
      Toggle({ type: ToggleType.Switch, isOn: this.state.preferences.dailyKnowledge }).selectedColor(SUPPORT_PRIMARY).onChange((enabled: boolean) => this.togglePreference('daily', enabled))
    }.width('100%').padding({ top: 20, bottom: 20 }).border({ width: { bottom: 1 }, color: SUPPORT_LINE })
    Text('关注方向').fontSize(16).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).padding({ top: 22, bottom: 12 })
    ForEach(NEWS_CATEGORIES, (category: NewsCategory) => {
      Row() {
        Text(category.name).fontSize(15).fontColor(SUPPORT_TEXT).layoutWeight(1)
        Checkbox({ name: category.id }).select(this.state.preferences.categories.includes(category.id)).selectedColor(SUPPORT_PRIMARY)
          .onChange((selected: boolean) => this.toggleCategory(category.id, selected))
      }.width('100%').padding({ top: 12, bottom: 12 })
    }, (category: NewsCategory) => category.id)
    SupportNotice({ text: '设置保存在本机。应用打开时同步站内消息；锁屏通知尚未启用。' })
  }

  @Builder
  MessageList() {
    Row() {
      Text(`${unreadNews(this.state)} 条未读`).fontSize(13).fontColor(SUPPORT_MUTED).layoutWeight(1)
      Button('全部已读', { type: ButtonType.Normal }).fontSize(14).fontColor(APP_PRIMARY).backgroundColor(Color.Transparent)
        .enabled(unreadNews(this.state) > 0).onClick(() => this.markAll())
    }.width('100%')
    if (this.state.messages.length === 0) { SupportNotice({ text: '暂无推送消息' }) }
    ForEach(this.state.messages, (message: NewsMessage) => {
      Column({ space: 10 }) {
        Row({ space: 12 }) { Text(message.label).fontSize(12).fontColor(APP_PRIMARY); if (!message.read) { Text('未读').fontSize(11).fontColor(APP_WARNING) } }
        Text(message.title).fontSize(17).fontColor(SUPPORT_TEXT).fontWeight(FontWeight.Medium).lineHeight(26)
        Text(displayTime(message.receivedAt)).fontSize(12).fontColor(SUPPORT_MUTED)
      }.width('100%').alignItems(HorizontalAlign.Start).padding({ top: 16, bottom: 16 }).border({ width: { bottom: 1 }, color: SUPPORT_LINE })
        .onClick(() => this.open(message.articleId))
    }, (message: NewsMessage) => `${message.id}-${message.read}`)
  }

  @Builder
  FeedList() {
    if (this.daily !== null) {
      Column({ space: 8 }) {
        Row({ space: 6 }) {
          SymbolGlyph($r('sys.symbol.leaf')).fontSize(15).fontColor([APP_SUCCESS])
          Text('今日小知识').fontSize(12).fontWeight(FontWeight.Medium).fontColor(APP_SUCCESS)
          Blank()
          SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(13).fontColor([APP_SUCCESS])
        }.width('100%')
        Text(this.daily.title).fontSize(18).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).lineHeight(28)
        Text(this.daily.summary).fontSize(13).fontColor(APP_MUTED).lineHeight(22)
      }.width('100%').alignItems(HorizontalAlign.Start).padding(16).margin({ bottom: 18 })
        .backgroundColor(APP_SUCCESS_SOFT).borderRadius(8).onClick(() => { if (this.daily) { this.open(this.daily.id); } })
    }
    Row() {
      ForEach(['新闻', '小知识', '收藏', `消息 ${unreadNews(this.state) || ''}`], (label: string, index: number) => {
        Button(label, { type: ButtonType.Normal }).layoutWeight(1).height(46).fontSize(14).fontColor(this.tab === index ? SUPPORT_PRIMARY : SUPPORT_MUTED)
          .backgroundColor(Color.Transparent).border({ width: { bottom: this.tab === index ? 2 : 0 }, color: SUPPORT_PRIMARY }).onClick(() => this.changeTab(index))
      }, (label: string, index: number) => `${index}-${label}`)
    }.width('100%').margin({ bottom: 14 }).border({ width: { bottom: 1 }, color: SUPPORT_LINE })
    if (this.tab === 3) { this.MessageList() }
    else {
      TextInput({ text: this.query, placeholder: '搜索标题、内容摘要或来源' }).height(46).fontSize(14).fontColor(SUPPORT_TEXT).placeholderColor(APP_MUTED)
        .backgroundColor(APP_FIELD).borderRadius(6).maxLength(100).onChange((value: string) => { this.query = value; this.renderFeed(); })
      Scroll() {
        Row({ space: 8 }) {
          Button('全部', { type: ButtonType.Normal }).height(34).fontSize(13).fontColor(this.category === 'all' ? SUPPORT_PRIMARY : SUPPORT_MUTED)
            .backgroundColor(this.category === 'all' ? APP_PRIMARY_SOFT : APP_FIELD).borderRadius(6)
            .onClick(() => { this.category = 'all'; this.renderFeed(); })
          ForEach(NEWS_CATEGORIES, (category: NewsCategory) => {
            Button(category.name, { type: ButtonType.Normal }).height(34).fontSize(13).fontColor(this.category === category.id ? SUPPORT_PRIMARY : SUPPORT_MUTED)
              .backgroundColor(this.category === category.id ? APP_PRIMARY_SOFT : APP_FIELD).borderRadius(6)
              .onClick(() => { this.category = category.id; this.renderFeed(); })
          }, (category: NewsCategory) => category.id)
        }.padding({ top: 12, bottom: 12 })
      }.scrollable(ScrollDirection.Horizontal).scrollBar(BarState.Off).width('100%').align(Alignment.Start)
      Text(`${this.articles.length} 条${this.tab === 2 ? '本机收藏' : ''}`).fontSize(12).fontColor(SUPPORT_MUTED).padding({ top: 8, bottom: 8 })
      if (this.articles.length === 0) { SupportNotice({ text: this.loading ? '正在更新…' : this.tab === 2 ? '还没有收藏的内容' : '没有匹配的内容' }) }
      ForEach(this.articles, (article: CattleArticle) => {
        ArticleRow({ article: article, unread: !this.state.readIds.includes(article.id), saved: this.state.favorites.some(item => item.id === article.id), onOpen: () => this.open(article.id) })
      }, (article: CattleArticle) => `${article.id}-${this.state.readIds.includes(article.id)}-${this.state.favorites.some(item => item.id === article.id)}`)
    }
    ForEach(this.sources, (source: NewsSource) => {
      Text(`${source.name}：${source.status === 'ok' ? '已更新' : source.status === 'pending' ? '同步中' : '暂不可用'}${source.lastSuccessAt ? ' · ' + displayTime(source.lastSuccessAt) : ''}`)
        .fontSize(11).fontColor(SUPPORT_MUTED).lineHeight(20).padding({ top: 12 })
    }, (source: NewsSource) => `${source.id}-${source.status}-${source.lastSuccessAt}`)
  }

  build() {
    Column() {
      SupportHeader({ title: '养牛资讯' })
      Row() {
        Text('新闻 · 每日小知识').fontSize(13).fontColor(SUPPORT_MUTED).layoutWeight(1)
        Button(this.subscriptions ? '返回资讯' : '订阅设置', { type: ButtonType.Normal }).fontSize(14).fontColor(APP_PRIMARY).backgroundColor(Color.Transparent)
          .onClick(() => { this.subscriptions = !this.subscriptions; setTimeout((): void => { this.contentScroller.scrollEdge(Edge.Top); }, 40); })
        Button({ type: ButtonType.Normal }) {
          if (this.loading) { LoadingProgress().width(21).height(21).color(APP_PRIMARY) }
          else { SymbolGlyph($r('sys.symbol.arrow_clockwise')).fontSize(21).fontColor([APP_PRIMARY]) }
        }.width(40).height(40).padding(0).borderRadius(8).backgroundColor(APP_FIELD).accessibilityText('刷新资讯')
          .enabled(!this.loading).onClick(() => this.load(true))
      }.width('100%').padding({ bottom: 16 })
      Scroll(this.contentScroller) {
        Column() {
          if (this.error) { SupportNotice({ text: this.error, error: true }) }
          if (this.subscriptions) { this.Subscriptions() } else { this.FeedList() }
        }.width('100%').alignItems(HorizontalAlign.Start).padding({ bottom: 24 })
      }.width('100%').layoutWeight(1).scrollBar(BarState.Off).align(Alignment.TopStart)
    }.height('100%').width('100%').padding({ left: 18, right: 18 }).backgroundColor(SUPPORT_BG)
  }
}
