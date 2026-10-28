import { APP_DANGER, APP_FIELD, APP_LINE, APP_MUTED, APP_PRIMARY, APP_PRIMARY_SOFT, APP_TEXT, APP_WARNING } from '../support/AppTheme';
import { common } from '@kit.AbilityKit';
import { promptAction } from '@kit.ArkUI';
import { hilog } from '@kit.PerformanceAnalysisKit';
import { Consultation, ConsultationDraft, SupportCategory, SupportPriority, SUPPORT_CATEGORIES, SUPPORT_PRIORITIES,
  SupportService, categoryName, displayTime, draftError, errorMessage, newDraft, priorityName } from '../support/SupportService';
import { SUPPORT_BG, SUPPORT_PRIMARY, SUPPORT_LINE, SUPPORT_MUTED, SUPPORT_TEXT, SupportButton, SupportHeader, SupportNotice } from '../support/SupportUI';
import { ConsultationDetail } from '../support/ConsultationDetail';

interface ConsultationParams { question?: string; category?: string; }

@Entry
@Component
struct ConsultationPage {
  @State tab: number = 0;
  @State draft: ConsultationDraft = newDraft();
  @State records: Consultation[] = [];
  @State selected: Consultation | null = null;
  @State sending: boolean = false;
  @State loading: boolean = false;
  @State cancelling: boolean = false;
  @State error: string = '';
  @State notice: string = '';
  private contentScroller: Scroller = new Scroller();

  aboutToAppear(): void { this.initialize(); }

  async initialize(): Promise<void> {
    const params = this.getUIContext().getRouter().getParams() as ConsultationParams;
    try {
      await SupportService.init(getContext(this) as common.UIAbilityContext);
      this.draft = await SupportService.readDraft();
      this.records = await SupportService.readCache();
      if (params?.question) {
        if (this.draft.subject || this.draft.description) {
          const result = await promptAction.showDialog({ title: '保留已有草稿？', message: '替换后将带入 AI 会话中的问题。',
            buttons: [{ text: '保留草稿', color: APP_MUTED }, { text: '带入问题', color: APP_PRIMARY }] });
          if (result.index !== 1) { return; }
        }
        this.draft = newDraft();
        this.draft.subject = params.question.slice(0, 80);
        this.draft.description = params.question.slice(0, 2000);
        this.draft.category = params.category || 'health';
        await SupportService.saveDraft(this.draft);
      }
    } catch (error) { this.error = '本机草稿读取失败，请检查存储空间'; }
  }

  async saveDraft(): Promise<void> {
    try { await SupportService.saveDraft(this.draft); }
    catch (error) { this.error = '草稿未能保存到本机，请检查存储空间'; }
  }

  changeTab(tab: number): void {
    this.tab = tab; this.selected = null; this.error = ''; this.notice = '';
    this.scrollToTop();
    if (tab === 1) { this.refresh(); }
  }

  scrollToTop(): void {
    setTimeout((): void => { this.contentScroller.scrollEdge(Edge.Top); }, 40);
  }

  async refresh(): Promise<void> {
    if (this.loading) { return; }
    this.loading = true; this.error = ''; this.notice = '';
    try {
      this.records = await SupportService.consultations();
      await SupportService.cache(this.records);
    } catch (error) {
      this.error = errorMessage(error as Error);
      if (this.records.length > 0) { this.notice = '以下为本机缓存，当前状态尚未刷新'; }
    } finally { this.loading = false; }
  }

  async submit(): Promise<void> {
    if (this.sending) { return; }
    this.error = draftError(this.draft);
    if (this.error) { this.scrollToTop(); return; }
    this.sending = true; this.notice = '';
    try {
      await SupportService.saveDraft(this.draft);
      const item = await SupportService.submit(this.draft);
      this.records = [item].concat(this.records.filter(record => record.id !== item.id));
      this.selected = item;
      this.tab = 1;
      this.draft = newDraft();
      this.notice = '平台已收件，等待受理；尚未分配专家。';
      this.scrollToTop();
      try { await SupportService.clearDraft(); await SupportService.cache(this.records); } catch (error) { /* Receipt is saved on the server. */ }
    } catch (error) { this.error = `${errorMessage(error as Error)}；草稿已保留，可使用原咨询编号重试。`; }
    finally { this.sending = false; }
  }

  async resetDraft(): Promise<void> {
    const result = await promptAction.showDialog({ title: '清空草稿？', message: '尚未提交的内容会被清空。',
      buttons: [{ text: '取消', color: APP_MUTED }, { text: '清空', color: APP_PRIMARY }] });
    if (result.index === 1) { this.draft = newDraft(); this.error = ''; await this.saveDraft(); }
  }

  async cancel(item: Consultation): Promise<void> {
    if (this.cancelling) { return; }
    hilog.info(0x1200, 'CattleSupport', 'cancel: opened');
    const result = await promptAction.showDialog({ title: '撤回这条咨询？', message: '记录会保留，状态改为已撤回。',
      buttons: [{ text: '取消', color: APP_MUTED }, { text: '撤回', color: APP_DANGER }] });
    hilog.info(0x1200, 'CattleSupport', 'cancel: dialog index=%{public}d', result.index);
    if (result.index !== 1) { return; }
    this.cancelling = true; this.error = '';
    try {
      const changed = await SupportService.cancel(item.id);
      hilog.info(0x1200, 'CattleSupport', 'cancel: response=%{public}s', changed.status);
      this.records = this.records.map(record => record.id === changed.id ? changed : record);
      this.selected = changed;
      hilog.info(0x1200, 'CattleSupport', 'cancel: selected=%{public}s', this.selected.status);
      this.notice = changed.status === 'cancelled' ? '咨询已撤回。' : '';
      await SupportService.cache(this.records);
    } catch (error) { this.error = errorMessage(error as Error); }
    finally { this.cancelling = false; }
  }

  @Builder
  Label(text: string) { Text(text).fontSize(15).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).padding({ top: 22, bottom: 10 }) }

  @Builder
  Form() {
    Row({ space: 10 }) {
      SymbolGlyph($r('sys.symbol.person_2')).fontSize(24).fontColor([APP_PRIMARY])
      Column({ space: 4 }) {
        Text('咨询信息').fontSize(18).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT)
        Text('平台收件后等待受理').fontSize(12).fontColor(SUPPORT_MUTED)
      }.alignItems(HorizontalAlign.Start).layoutWeight(1)
    }.width('100%').padding({ top: 22, bottom: 4 })
    this.Label('咨询方向')
    Grid() {
      ForEach(SUPPORT_CATEGORIES, (category: SupportCategory) => {
        GridItem() {
          Button(category.name, { type: ButtonType.Normal }).width('100%').height(44).fontSize(14)
            .fontColor(this.draft.category === category.id ? APP_PRIMARY : APP_TEXT)
            .backgroundColor(this.draft.category === category.id ? APP_PRIMARY_SOFT : APP_FIELD).borderRadius(6)
            .border({ width: 1, color: this.draft.category === category.id ? SUPPORT_PRIMARY : APP_LINE }).borderRadius(8).enabled(!this.sending)
            .onClick(() => { this.draft.category = category.id; this.saveDraft(); })
        }
      }, (category: SupportCategory) => category.id)
    }.columnsTemplate('1fr 1fr').columnsGap(8).rowsGap(8).height(96).width('100%')
    this.Label('紧急程度')
    Row({ space: 8 }) {
      ForEach(SUPPORT_PRIORITIES, (priority: SupportPriority) => {
        Button(priority.name, { type: ButtonType.Normal }).layoutWeight(1).height(42).fontSize(14)
          .fontColor(this.draft.priority === priority.id ? APP_PRIMARY : APP_TEXT)
          .backgroundColor(this.draft.priority === priority.id ? APP_PRIMARY_SOFT : APP_FIELD).borderRadius(6)
          .border({ width: 1, color: this.draft.priority === priority.id ? SUPPORT_PRIMARY : APP_LINE }).borderRadius(8).enabled(!this.sending)
          .onClick(() => { this.draft.priority = priority.id; this.saveDraft(); })
      }, (priority: SupportPriority) => priority.id)
    }.width('100%')
    if (this.draft.priority === 'urgent') { SupportNotice({ text: '呼吸困难、不能起立或疑似传染病时，请立即联系当地兽医，不要等待线上回复。', error: true }) }
    this.Label('牛只耳标 / 栏位（选填）')
    TextInput({ text: this.draft.cattleId, placeholder: '耳标或所在栏位' }).height(48).fontSize(15).fontColor(SUPPORT_TEXT).placeholderColor(APP_MUTED)
      .backgroundColor(APP_FIELD).borderRadius(6).maxLength(80).enabled(!this.sending).onChange((value: string) => { this.draft.cattleId = value; this.saveDraft(); })
    this.Label('问题标题 *')
    TextInput({ text: this.draft.subject, placeholder: '例如：牛只连续两天行走跛行' }).height(48).fontSize(15).fontColor(SUPPORT_TEXT).placeholderColor(APP_MUTED)
      .backgroundColor(APP_FIELD).borderRadius(6).maxLength(80).enabled(!this.sending).onChange((value: string) => { this.draft.subject = value; this.saveDraft(); })
    Text(`${this.draft.subject.length} / 80`).fontSize(11).fontColor(SUPPORT_MUTED).width('100%').textAlign(TextAlign.End).padding({ top: 6 })
    this.Label('问题详情 *')
    TextArea({ text: this.draft.description, placeholder: '异常表现、开始时间、体温、采食与活动情况' }).height(168).fontSize(15).fontColor(SUPPORT_TEXT).placeholderColor(APP_MUTED)
      .backgroundColor(APP_FIELD).borderRadius(6).maxLength(2000).enabled(!this.sending).onChange((value: string) => { this.draft.description = value; this.saveDraft(); })
    Text(`${this.draft.description.length} / 2000`).fontSize(11).fontColor(SUPPORT_MUTED).width('100%').textAlign(TextAlign.End).padding({ top: 6 })
    this.Label('联系方式（选填）')
    TextInput({ text: this.draft.contact, placeholder: '电话或其他回访方式' }).height(48).fontSize(15).fontColor(SUPPORT_TEXT).placeholderColor(APP_MUTED)
      .backgroundColor(APP_FIELD).borderRadius(6).maxLength(80).enabled(!this.sending).onChange((value: string) => { this.draft.contact = value; this.saveDraft(); })
    SupportNotice({ text: '咨询单提交至平台待受理队列，专家接入后方可提供人工回复。草稿仅保存在本机。' })
    Row({ space: 10 }) {
      SupportButton({ label: '清空草稿', secondary: true, isEnabled: !this.sending, onPress: () => this.resetDraft() }).layoutWeight(1)
      SupportButton({ label: this.sending ? '正在提交' : '提交咨询', isEnabled: !this.sending, onPress: () => this.submit() }).layoutWeight(1)
    }.width('100%').padding({ bottom: 24 })
  }

  @Builder
  RecordList() {
    Row() {
      Text(`最近 ${this.records.length} 条`).fontSize(13).fontColor(SUPPORT_MUTED).layoutWeight(1)
      Button(this.loading ? '刷新中…' : '刷新', { type: ButtonType.Normal }).fontSize(14).fontColor(APP_PRIMARY)
        .backgroundColor(Color.Transparent).enabled(!this.loading).onClick(() => this.refresh())
    }.width('100%')
    if (this.records.length === 0) {
      Text(this.loading ? '正在读取咨询记录…' : '还没有已提交的咨询').fontSize(15).fontColor(SUPPORT_MUTED).width('100%').textAlign(TextAlign.Center).padding({ top: 50, bottom: 50 })
    }
    ForEach(this.records, (item: Consultation) => {
      Column({ space: 10 }) {
        Row({ space: 10 }) {
          Text(item.subject).fontSize(17).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).lineHeight(25).layoutWeight(1)
          Text(item.status === 'cancelled' ? '已撤回' : '待受理').fontSize(12).fontColor(item.status === 'cancelled' ? SUPPORT_MUTED : APP_WARNING)
        }.width('100%')
        Text(`${categoryName(item.category)} · ${priorityName(item.priority)} · ${displayTime(item.createdAt)}`).fontSize(12).fontColor(SUPPORT_MUTED)
        Text(item.description).fontSize(14).lineHeight(23).fontColor(APP_MUTED).maxLines(2).textOverflow({ overflow: TextOverflow.Ellipsis })
      }.width('100%').alignItems(HorizontalAlign.Start).padding({ top: 18, bottom: 18 }).border({ width: { bottom: 1 }, color: SUPPORT_LINE })
        .onClick(() => { this.selected = item; this.error = ''; this.notice = ''; this.scrollToTop(); })
    }, (item: Consultation) => `${item.id}-${item.status}-${item.updatedAt}`)
  }

  build() {
    Column() {
      SupportHeader({ title: '专家咨询' })
      Row({ space: 4 }) {
        Button('发起咨询', { type: ButtonType.Normal }).layoutWeight(1).height(48).fontSize(15).fontColor(this.tab === 0 ? SUPPORT_PRIMARY : SUPPORT_MUTED)
          .backgroundColor(this.tab === 0 ? APP_PRIMARY_SOFT : Color.Transparent).borderRadius(8).fontWeight(this.tab === 0 ? FontWeight.Bold : FontWeight.Regular)
          .enabled(!this.sending).onClick(() => this.changeTab(0))
        Button('我的咨询', { type: ButtonType.Normal }).layoutWeight(1).height(48).fontSize(15).fontColor(this.tab === 1 ? SUPPORT_PRIMARY : SUPPORT_MUTED)
          .backgroundColor(this.tab === 1 ? APP_PRIMARY_SOFT : Color.Transparent).borderRadius(8).fontWeight(this.tab === 1 ? FontWeight.Bold : FontWeight.Regular)
          .enabled(!this.sending).onClick(() => this.changeTab(1))
      }.width('100%').padding(4).backgroundColor(APP_FIELD).borderRadius(8)
      Scroll(this.contentScroller) {
        Column() {
          if (this.error) { SupportNotice({ text: this.error, error: true }) }
          if (this.notice) { SupportNotice({ text: this.notice }) }
          if (this.tab === 0) { this.Form() }
          else if (this.selected !== null) {
            ConsultationDetail({ item: this.selected, cancelling: this.cancelling,
              onBack: () => { this.selected = null; this.scrollToTop(); },
              onCancel: () => { if (this.selected !== null) { this.cancel(this.selected); } } })
          }
          else { this.RecordList() }
        }.width('100%').alignItems(HorizontalAlign.Start).padding({ bottom: 30 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off).align(Alignment.TopStart)
    }.width('100%').height('100%').padding({ left: 18, right: 18 }).backgroundColor(SUPPORT_BG)
  }
}
