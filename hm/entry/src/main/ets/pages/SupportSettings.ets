import { APP_FIELD, APP_PRIMARY, APP_PRIMARY_SOFT } from '../support/AppTheme';
import { common } from '@kit.AbilityKit';
import { SupportService, errorMessage } from '../support/SupportService';
import { SUPPORT_BG, SUPPORT_MUTED, SUPPORT_TEXT, SupportButton, SupportHeader, SupportNotice } from '../support/SupportUI';

@Entry
@Component
struct SupportSettings {
  @State baseUrl: string = '';
  @State apiKey: string = '';
  @State testing: boolean = false;
  @State error: string = '';
  @State message: string = '';

  aboutToAppear(): void { this.initialize(); }
  async initialize(): Promise<void> {
    try {
      await SupportService.init(getContext(this) as common.UIAbilityContext);
      const settings = SupportService.getSettings();
      this.baseUrl = settings.baseUrl;
      this.apiKey = settings.apiKey;
    } catch (error) { this.error = '本机设置读取失败'; }
  }
  async save(): Promise<void> {
    if (this.testing) { return; }
    this.error = ''; this.message = '';
    try { await SupportService.saveSettings(this.baseUrl, this.apiKey); }
    catch (error) { this.error = errorMessage(error as Error); return; }
    this.testing = true;
    try {
      const info = await SupportService.catalog();
      this.message = `设置已保存，服务连接正常 · ${info.mode === 'llm' ? 'DeepSeek 问答' : '知识库模式'}`;
    } catch (error) { this.error = `设置已保存。${errorMessage(error as Error)}`; }
    finally { this.testing = false; }
  }

  build() {
    Column() {
      SupportHeader({ title: '服务设置', settingsVisible: false })
      Scroll() {
        Column({ space: 14 }) {
          Row({ space: 12 }) {
            SymbolGlyph($r('sys.symbol.wifi')).fontSize(27).fontColor([APP_PRIMARY])
              .width(52).height(52).backgroundColor(APP_PRIMARY_SOFT).borderRadius(8)
            Column({ space: 5 }) {
              Text('连接数牧服务').fontSize(19).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT)
              Text('AI 问答 · 专家咨询 · 养牛资讯').fontSize(12).fontColor(SUPPORT_MUTED)
            }.alignItems(HorizontalAlign.Start).layoutWeight(1)
          }.width('100%').padding({ top: 18, bottom: 8 })
          Text('平台服务地址').fontSize(15).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).padding({ top: 18 })
          TextInput({ text: this.baseUrl, placeholder: 'https://你的服务域名' }).height(52).fontSize(15).fontColor(SUPPORT_TEXT).placeholderColor(SUPPORT_MUTED)
            .backgroundColor(APP_FIELD).borderRadius(6).maxLength(240).enabled(!this.testing).onChange((value: string) => { this.baseUrl = value; })
          Text('平台访问凭证（选填）').fontSize(15).fontWeight(FontWeight.Medium).fontColor(SUPPORT_TEXT).padding({ top: 18 })
          TextInput({ text: this.apiKey, placeholder: '已启用访问控制时填写' }).type(InputType.Password).height(52).fontSize(15).fontColor(SUPPORT_TEXT)
            .placeholderColor(SUPPORT_MUTED).backgroundColor(APP_FIELD).borderRadius(6).maxLength(240).enabled(!this.testing).onChange((value: string) => { this.apiKey = value; })
          SupportNotice({ text: '真机填写可访问的服务器地址。更换设备或清除应用数据后，本机咨询身份和会话无法自动恢复。' })
          if (this.error) { SupportNotice({ text: this.error, error: true }) }
          if (this.message) { SupportNotice({ text: this.message }) }
          SupportButton({ label: this.testing ? '正在测试连接' : '保存并测试连接', isEnabled: !this.testing, onPress: () => this.save() })
        }.width('100%').alignItems(HorizontalAlign.Start)
      }.width('100%').layoutWeight(1).align(Alignment.TopStart)
    }.width('100%').height('100%').padding({ left: 18, right: 18 }).backgroundColor(SUPPORT_BG)
  }
}
