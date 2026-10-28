import { APP_FIELD, APP_PRIMARY, APP_PRIMARY_SOFT, APP_TEXT, APP_WARNING, APP_WARNING_SOFT } from '../support/AppTheme';
import { common } from '@kit.AbilityKit';
import { CattleArticle, NewsService, categoryLabel, articleDate } from '../news/NewsService';
import { copySupportText } from '../support/SupportService';
import { SUPPORT_BG, SUPPORT_MUTED, SUPPORT_TEXT, SupportButton, SupportHeader, SupportNotice } from '../support/SupportUI';
interface ArticleParams { id: string; }
interface QuestionParams { question: string; }
interface ConsultationParams { question: string; category: string; }

@Entry
@Component
struct NewsDetail {
  @State article: CattleArticle | null = null;
  @State loading: boolean = true;
  @State error: string = '';
  @State saved: boolean = false;
  @State notice: string = '';
  private articleId: string = '';
  aboutToAppear(): void {
    const params = this.getUIContext().getRouter().getParams() as ArticleParams;
    this.articleId = params?.id ?? ''; this.load();
  }
  async load(): Promise<void> {
    this.loading = true; this.error = '';
    try {
      await NewsService.init(getContext(this) as common.UIAbilityContext);
      this.article = await NewsService.article(this.articleId);
      await NewsService.markRead(this.articleId);
      this.saved = (await NewsService.state()).favorites.some(item => item.id === this.articleId);
    } catch (error) { this.error = (error as Error).message; }
    finally { this.loading = false; }
  }
  async favorite(): Promise<void> {
    if (!this.article) { return; }
    try { this.saved = await NewsService.favorite(this.article); } catch (error) { this.error = (error as Error).message; }
  }
  async original(): Promise<void> {
    if (!this.article) { return; }
    try { await copySupportText(this.article.sourceUrl); this.notice = '原文链接已复制'; } catch (error) { this.error = '复制失败，请重试'; }
  }
  ask(): void {
    if (!this.article) { return; }
    const params: QuestionParams = { question: `关于“${this.article.title}”，牛场日常管理要注意什么？` };
    this.getUIContext().getRouter().pushUrl({ url: 'pages/Assistant', params: params });
  }
  consult(): void {
    if (!this.article) { return; }
    const params: ConsultationParams = { question: `我想咨询“${this.article.title}”相关的牛场管理问题。`,
      category: this.article.category === 'nutrition' ? 'nutrition' : this.article.category === 'environment' ? 'equipment' : 'health' };
    this.getUIContext().getRouter().pushUrl({ url: 'pages/Consultation', params: params });
  }

  build() {
    Column() {
      SupportHeader({ title: '资讯详情', settingsVisible: false })
      Scroll() {
        Column({ space: 14 }) {
          if (this.loading) { SupportNotice({ text: '正在读取内容…' }) }
          if (this.error) { SupportNotice({ text: this.error, error: true }); SupportButton({ label: '重试', onPress: () => this.load() }) }
          if (this.article !== null) {
            Text(`${this.article.kind === 'knowledge' ? '养牛小知识' : '行业新闻'} · ${categoryLabel(this.article.category)}`).fontSize(13).fontColor(APP_PRIMARY)
            Text(this.article.title).fontSize(24).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT).lineHeight(36)
            Text(`${this.article.sourceName} · ${articleDate(this.article)}`).fontSize(12).fontColor(SUPPORT_MUTED).lineHeight(20)
            Row({ space: 14 }) {
              Button({ type: ButtonType.Normal }) {
                Row({ space: 7 }) {
                  SymbolGlyph(this.saved ? $r('sys.symbol.star_fill') : $r('sys.symbol.star')).fontSize(18).fontColor([APP_WARNING])
                  Text(this.saved ? '已收藏' : '收藏').fontSize(13).fontColor(APP_WARNING)
                }
              }.height(38).padding({ left: 12, right: 12 }).borderRadius(8).backgroundColor(APP_WARNING_SOFT)
                .accessibilityText(this.saved ? '取消收藏' : '收藏文章').onClick(() => this.favorite())
              Button({ type: ButtonType.Normal }) {
                Row({ space: 6 }) {
                  Text(this.article.kind === 'news' ? '原文链接' : '延伸阅读').fontSize(13).fontColor(APP_PRIMARY)
                  SymbolGlyph($r('sys.symbol.arrow_up_right')).fontSize(15).fontColor([APP_PRIMARY])
                }
              }.height(38).padding({ left: 12, right: 12 }).backgroundColor(APP_PRIMARY_SOFT).borderRadius(8)
                .accessibilityText('复制原文链接').onClick(() => this.original())
            }.width('100%').justifyContent(FlexAlign.SpaceBetween).padding({ top: 4, bottom: 10 })
            if (this.notice) { SupportNotice({ text: this.notice }) }
            if (this.article.summary) {
              Text(this.article.summary).fontSize(15).fontColor(APP_TEXT).lineHeight(26).width('100%')
                .padding(14).backgroundColor(APP_FIELD).borderRadius(8)
            }
            Text(this.article.content).fontSize(16).fontColor(SUPPORT_TEXT).lineHeight(29).copyOption(CopyOptions.LocalDevice)
            Row({ space: 10 }) {
              SupportButton({ label: '问 AI 助手', secondary: true, onPress: () => this.ask() }).layoutWeight(1)
              SupportButton({ label: '专家咨询', secondary: true, onPress: () => this.consult() }).layoutWeight(1)
            }.width('100%').padding({ top: 20, bottom: 24 })
          }
        }.width('100%').alignItems(HorizontalAlign.Start)
      }.width('100%').layoutWeight(1).scrollBar(BarState.Off).align(Alignment.TopStart)
    }.width('100%').height('100%').padding({ left: 18, right: 18 }).backgroundColor(SUPPORT_BG)
  }
}
