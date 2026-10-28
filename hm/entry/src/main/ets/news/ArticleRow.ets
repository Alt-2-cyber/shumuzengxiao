import { APP_MUTED, APP_PRIMARY, APP_PRIMARY_SOFT, APP_SUCCESS, APP_WARNING, APP_WARNING_SOFT } from '../support/AppTheme';
import { CattleArticle, categoryLabel, articleDate } from './NewsService';
import { SUPPORT_LINE, SUPPORT_MUTED, SUPPORT_TEXT } from '../support/SupportUI';

@Component
export struct ArticleRow {
  @Prop article: CattleArticle = { id: '', kind: '', category: '', title: '', summary: '', content: '', sourceName: '', sourceUrl: '', publishedAt: '', collectedAt: '' };
  @Prop unread: boolean = false;
  @Prop saved: boolean = false;
  onOpen: () => void = () => {};
  build() {
    Column({ space: 9 }) {
      Row({ space: 10 }) {
        Text(categoryLabel(this.article.category)).fontSize(12).fontColor(this.article.category === 'market' ? APP_WARNING : APP_PRIMARY)
          .padding({ left: 7, right: 7, top: 4, bottom: 4 }).borderRadius(4)
          .backgroundColor(this.article.category === 'market' ? APP_WARNING_SOFT : APP_PRIMARY_SOFT)
        if (this.unread) { Circle().width(5).height(5).fill(APP_PRIMARY) }
        Blank()
        if (this.saved) { SymbolGlyph($r('sys.symbol.star_fill')).fontSize(13).fontColor([APP_WARNING]) }
      }.width('100%')
      Text(this.article.title).fontSize(17).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT).lineHeight(26)
      if (this.article.summary) { Text(this.article.summary).fontSize(13).fontColor(APP_MUTED).lineHeight(22).maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis }) }
      Text(`${this.article.sourceName} · ${articleDate(this.article)}`).fontSize(12).fontColor(SUPPORT_MUTED).lineHeight(20)
    }.width('100%').alignItems(HorizontalAlign.Start).padding({ top: 16, bottom: 16 })
      .border({ width: { bottom: 1 }, color: SUPPORT_LINE }).onClick(this.onOpen)
  }
}
