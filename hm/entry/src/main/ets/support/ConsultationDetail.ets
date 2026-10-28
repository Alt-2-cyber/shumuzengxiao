import { APP_FIELD, APP_PRIMARY, APP_WARNING, APP_WARNING_SOFT } from './AppTheme';
import { Consultation, categoryName, displayTime, priorityName } from './SupportService';
import { SUPPORT_MUTED, SUPPORT_TEXT, SupportButton, SupportNotice } from './SupportUI';

@Component
export struct ConsultationDetail {
  @Prop item: Consultation = { id: '', category: '', priority: '', subject: '', description: '', cattleId: '', contact: '', status: '', createdAt: '', updatedAt: '' };
  @Prop cancelling: boolean = false;
  onBack: () => void = () => {};
  onCancel: () => void = () => {};

  @Builder
  Label(text: string) {
    Text(text).fontSize(15).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).padding({ top: 22, bottom: 10 })
  }

  build() {
    Column() {
      Button({ type: ButtonType.Normal }) {
        Row({ space: 6 }) {
          SymbolGlyph($r('sys.symbol.chevron_backward')).fontSize(15).fontColor([APP_PRIMARY])
          Text('返回咨询列表').fontSize(14).fontColor(APP_PRIMARY)
        }
      }.height(44).backgroundColor(Color.Transparent).padding({ left: 0, top: 12, bottom: 12 }).onClick(this.onBack)
      Text(this.item.subject).fontSize(22).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT).lineHeight(32).padding({ top: 12, bottom: 14 })
      Text(`${this.item.status === 'cancelled' ? '已撤回' : '待受理'} · ${categoryName(this.item.category)} · ${priorityName(this.item.priority)}`)
        .fontSize(13).fontColor(this.item.status === 'cancelled' ? SUPPORT_MUTED : APP_WARNING)
        .padding({ left: 10, right: 10, top: 8, bottom: 8 }).borderRadius(6)
        .backgroundColor(this.item.status === 'cancelled' ? APP_FIELD : APP_WARNING_SOFT)
      Text(displayTime(this.item.createdAt)).fontSize(12).fontColor(SUPPORT_MUTED).padding({ top: 10 })
      Text(`咨询编号：${this.item.id}`).fontSize(11).fontColor(SUPPORT_MUTED).padding({ top: 8 }).copyOption(CopyOptions.LocalDevice)
      this.Label('问题详情')
      Text(this.item.description).fontSize(15).lineHeight(26).fontColor(SUPPORT_TEXT).copyOption(CopyOptions.LocalDevice)
      if (this.item.cattleId) { this.Label('牛只 / 栏位'); Text(this.item.cattleId).fontSize(15).fontColor(SUPPORT_TEXT) }
      if (this.item.contact) { this.Label('联系方式'); Text(this.item.contact).fontSize(15).fontColor(SUPPORT_TEXT) }
      this.Label('受理进度')
      SupportNotice({ text: this.item.status === 'cancelled' ? '咨询已撤回。' : '平台已保存咨询单，尚未分配专家，暂无人工回复。' })
      if (this.item.status === 'pending') {
        SupportButton({ label: this.cancelling ? '正在撤回' : '撤回咨询', secondary: true, isEnabled: !this.cancelling, onPress: this.onCancel })
      }
    }.width('100%').alignItems(HorizontalAlign.Start)
  }
}
