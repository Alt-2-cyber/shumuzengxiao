import { APP_FIELD, APP_MUTED, APP_PRIMARY, APP_PRIMARY_SOFT, APP_SUCCESS, APP_SUCCESS_SOFT, APP_SURFACE, APP_TEXT } from '../support/AppTheme';
import { common } from '@kit.AbilityKit';
import { promptAction } from '@kit.ArkUI';
import { ChatMessage, SupportReference, SupportService, copySupportText, displayTime, errorMessage, newSupportId } from '../support/SupportService';
import { SUPPORT_BG, SUPPORT_PRIMARY, SUPPORT_LINE, SUPPORT_MUTED, SUPPORT_TEXT, SupportHeader, SupportNotice } from '../support/SupportUI';

interface ConsultationParams { question: string; category: string; }
interface QuestionParams { question?: string; }

@Entry
@Component
struct Assistant {
  @State messages: ChatMessage[] = [];
  @State input: string = '';
  @State sending: boolean = false;
  @State mode: string = '连接中';
  @State error: string = '';
  private scroller: Scroller = new Scroller();
  private alive: boolean = true;
  private prompts: string[] = ['牛走路跛行要观察什么？', '牛咳嗽需要记录哪些信息？', 'B-1 红外体温偏高怎么办？', '牛舍风扇不转怎么排查？'];

  aboutToAppear(): void { this.alive = true; this.initialize(); }
  aboutToDisappear(): void { this.alive = false; }
  onPageShow(): void { this.refreshMode(); }

  async initialize(): Promise<void> {
    try {
      await SupportService.init(getContext(this) as common.UIAbilityContext);
      this.messages = await SupportService.readChat();
      const params = this.getUIContext().getRouter().getParams() as QuestionParams;
      if (params?.question) { this.input = params.question.slice(0, 1000); }
      await this.refreshMode();
      this.scrollEnd();
    } catch (error) { this.error = '本机会话读取失败，请检查存储空间'; }
  }

  async refreshMode(): Promise<void> {
    try {
      const catalog = await SupportService.catalog();
      if (this.alive) { this.mode = catalog.mode === 'llm' ? 'DeepSeek 问答' : '知识库模式'; }
    } catch (error) { if (this.alive) { this.mode = '服务未连接'; } }
  }

  scrollEnd(): void {
    setTimeout(() => { if (this.alive) { this.scroller.scrollEdge(Edge.Bottom); } }, 80);
  }

  async persist(messages: ChatMessage[]): Promise<void> {
    await SupportService.saveChat(messages);
    this.messages = messages;
    this.scrollEnd();
  }

  async send(): Promise<void> {
    if (this.sending || !this.input.trim()) { return; }
    const question = this.input.trim();
    const user: ChatMessage = { id: newSupportId(), role: 'user', content: question, time: displayTime(new Date().toISOString()),
      mode: '', model: '', category: '', references: [], status: 'pending', error: '' };
    const history = this.messages.filter(item => item.status === 'done');
    this.sending = true;
    this.error = '';
    this.input = '';
    try {
      await this.persist(this.messages.concat([user]).slice(-39));
      await this.fetchAnswer(user, history);
    } catch (error) { this.error = errorMessage(error as Error); }
    finally { this.sending = false; }
  }

  async fetchAnswer(user: ChatMessage, history: ChatMessage[]): Promise<void> {
    try {
      const response = await SupportService.ask(user.content, history);
      const messages = this.messages.map((item: ChatMessage): ChatMessage => {
        if (item.id === user.id) { item.status = 'done'; item.error = ''; }
        return item;
      });
      const answer: ChatMessage = { id: newSupportId(), role: 'assistant', content: response.answer,
        time: displayTime(new Date().toISOString()), mode: response.mode, model: response.model,
        category: response.category, references: response.references, status: 'done', error: '' };
      await this.persist(messages.concat([answer]).slice(-40));
      this.mode = response.mode === 'llm' ? 'DeepSeek 问答' : '知识库模式';
      this.error = response.notice;
    } catch (error) {
      const messages = this.messages.map((item: ChatMessage): ChatMessage => {
        if (item.id === user.id) { item.status = 'failed'; item.error = errorMessage(error as Error); }
        return item;
      });
      await this.persist(messages);
    }
  }

  async retry(user: ChatMessage): Promise<void> {
    if (this.sending) { return; }
    const index = this.messages.findIndex(item => item.id === user.id);
    this.sending = true;
    this.error = '';
    try { await this.fetchAnswer(user, this.messages.slice(0, index)); }
    catch (error) { this.error = errorMessage(error as Error); }
    finally { this.sending = false; }
  }

  async clearChat(): Promise<void> {
    const result = await promptAction.showDialog({ title: '清空当前会话？', message: '本机问答将被删除，已提交的咨询单会保留。',
      buttons: [{ text: '取消', color: APP_MUTED }, { text: '清空', color: APP_PRIMARY }] });
    if (result.index === 1) {
      try { await this.persist([]); this.error = ''; }
      catch (error) { this.error = '清空失败，请重试'; }
    }
  }

  async copy(text: string): Promise<void> {
    try { await copySupportText(text); promptAction.showToast({ message: '已复制' }); }
    catch (error) { promptAction.showToast({ message: '复制失败' }); }
  }

  consult(item: ChatMessage): void {
    const index = this.messages.findIndex(message => message.id === item.id);
    const question = this.messages.slice(0, index).reverse().find(message => message.role === 'user');
    const params: ConsultationParams = { question: question?.content ?? '', category: item.category };
    this.getUIContext().getRouter().pushUrl({ url: 'pages/Consultation', params: params });
  }

  @Builder
  Message(item: ChatMessage) {
    Column({ space: 10 }) {
      Row({ space: 8 }) {
        if (item.role === 'assistant') {
          SymbolGlyph($r('sys.symbol.wand_and_stars')).fontSize(16).fontColor([APP_PRIMARY])
        }
        Text(item.role === 'user' ? '我的问题' : '数牧助手').fontSize(12).fontWeight(FontWeight.Medium).fontColor(APP_PRIMARY).layoutWeight(1)
        Text(item.time).fontSize(11).fontColor(SUPPORT_MUTED)
      }.width('100%')
      Text(item.content).fontSize(15).lineHeight(26).fontColor(SUPPORT_TEXT).width('100%').copyOption(CopyOptions.LocalDevice)
      if (item.status === 'pending') { Text('正在回答…').fontSize(13).fontColor(SUPPORT_MUTED) }
      if (item.status === 'failed') {
        SupportNotice({ text: item.error, error: true })
        Button('重试', { type: ButtonType.Normal }).fontSize(14).fontColor(APP_PRIMARY).backgroundColor(Color.Transparent)
          .enabled(!this.sending).onClick(() => this.retry(item))
      }
      if (item.role === 'assistant') {
        Text(`${item.mode === 'llm' ? 'DeepSeek' : '知识库'} · ${item.model}`).fontSize(11).fontColor(SUPPORT_MUTED)
        ForEach(item.references, (reference: SupportReference) => {
          Text(`${reference.title} ↗`).fontSize(12).fontColor(APP_PRIMARY).lineHeight(20).onClick(() => this.copy(reference.url))
        }, (reference: SupportReference) => reference.url)
        Row({ space: 20 }) {
          Button({ type: ButtonType.Normal }) {
            SymbolGlyph($r('sys.symbol.doc_text_on_doc_text')).fontSize(18).fontColor([APP_MUTED])
          }.width(36).height(36).padding(0).backgroundColor(APP_FIELD).borderRadius(8)
            .accessibilityText('复制回答').onClick(() => this.copy(item.content))
          Button('转专家咨询 ↗', { type: ButtonType.Normal }).fontSize(13).fontColor(APP_PRIMARY).padding(0).backgroundColor(Color.Transparent).onClick(() => this.consult(item))
        }
      }
    }.alignItems(HorizontalAlign.Start).width('100%').padding(16).margin({ top: 12, bottom: 4 })
      .backgroundColor(item.role === 'user' ? APP_PRIMARY_SOFT : APP_FIELD).borderRadius(8)
  }

  build() {
    Column() {
      SupportHeader({ title: 'AI 助手' })
      Row({ space: 8 }) {
        Circle().width(6).height(6).fill(this.mode === '服务未连接' ? APP_MUTED : APP_SUCCESS)
        Text(this.mode).fontSize(12).fontColor(this.mode === '服务未连接' ? APP_MUTED : APP_SUCCESS).layoutWeight(1)
        Button({ type: ButtonType.Normal }) {
          SymbolGlyph($r('sys.symbol.trash')).fontSize(19).fontColor([SUPPORT_MUTED])
        }.width(36).height(36).padding(0).backgroundColor(Color.Transparent).accessibilityText('清空会话')
          .enabled(!this.sending && this.messages.length > 0).opacity(this.messages.length > 0 ? 1 : 0.35).onClick(() => this.clearChat())
      }.width('100%').padding({ bottom: 12 }).border({ width: { bottom: 1 }, color: SUPPORT_LINE })
      Scroll(this.scroller) {
        Column() {
          if (this.messages.length === 0) {
            SymbolGlyph($r('sys.symbol.wand_and_stars')).fontSize(34).fontColor([APP_PRIMARY])
              .width(64).height(64).backgroundColor(APP_PRIMARY_SOFT).borderRadius(8).margin({ top: 30, bottom: 18 })
            Text('今天的巡检，有什么发现？').fontSize(22).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT).lineHeight(32).padding({ bottom: 20 })
            ForEach(this.prompts, (question: string) => {
              Button({ type: ButtonType.Normal }) {
                Row({ space: 12 }) {
                  Text(question).fontSize(14).fontColor(APP_TEXT).layoutWeight(1).lineHeight(22)
                  SymbolGlyph($r('sys.symbol.arrow_up_right')).fontSize(16).fontColor([APP_PRIMARY])
                }.width('100%').padding(14)
              }.width('100%').padding(0).margin({ bottom: 10 }).borderRadius(8).backgroundColor(APP_FIELD)
                .onClick(() => { this.input = question; })
            }, (question: string) => question)
          }
          ForEach(this.messages, (message: ChatMessage) => { this.Message(message) }, (message: ChatMessage) => `${message.id}-${message.status}-${message.error}`)
        }.width('100%').alignItems(HorizontalAlign.Start).padding({ bottom: 20 })
      }.layoutWeight(1).width('100%').scrollBar(BarState.Off).align(Alignment.TopStart)
      Column({ space: 8 }) {
        if (this.error) { SupportNotice({ text: this.error, error: true }) }
        Row({ space: 10 }) {
          TextArea({ text: this.input, placeholder: '描述牛只、环境或设备问题' }).fontSize(15).fontColor(SUPPORT_TEXT).placeholderColor(APP_MUTED)
            .height(64).layoutWeight(1).maxLength(1000).backgroundColor(APP_FIELD).borderRadius(8).enabled(!this.sending)
            .onChange((value: string) => { this.input = value; })
          Button({ type: ButtonType.Normal }) {
            if (this.sending) { LoadingProgress().width(20).height(20).color(APP_SURFACE) }
            else { SymbolGlyph($r('sys.symbol.arrow_up')).fontSize(24).fontColor([APP_SURFACE]) }
          }.width(46).height(46).borderRadius(8).backgroundColor(SUPPORT_PRIMARY).enabled(!this.sending && this.input.trim().length > 0)
            .opacity(!this.sending && this.input.trim().length > 0 ? 1 : 0.4)
            .accessibilityText('发送问题').onClick(() => this.send())
        }.width('100%').alignItems(VerticalAlign.Bottom)
        Text('健康建议供巡检参考，疾病需由兽医确认').fontSize(11).fontColor(APP_MUTED).width('100%')
      }.width('100%').padding({ top: 12, bottom: 14 }).border({ width: { top: 1 }, color: SUPPORT_LINE })
    }.width('100%').height('100%').padding({ left: 18, right: 18 }).backgroundColor(SUPPORT_BG)
  }
}
