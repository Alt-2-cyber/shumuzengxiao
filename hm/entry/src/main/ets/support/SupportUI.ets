import { APP_SURFACE, APP_TEXT, APP_MUTED, APP_PRIMARY, APP_PRIMARY_SOFT, APP_LINE,
  APP_DANGER, APP_DANGER_SOFT } from './AppTheme';

export const SUPPORT_BG = APP_SURFACE;
export const SUPPORT_TEXT = APP_TEXT;
export const SUPPORT_MUTED = APP_MUTED;
export const SUPPORT_PRIMARY = APP_PRIMARY;
export const SUPPORT_LINE = APP_LINE;

@Component
export struct SupportHeader {
  @Prop title: string = '';
  @Prop settingsVisible: boolean = true;
  build() {
    Row({ space: 8 }) {
      Button({ type: ButtonType.Normal }) {
        SymbolGlyph($r('sys.symbol.chevron_backward')).fontSize(22).fontColor([SUPPORT_TEXT])
      }.width(36).height(44).padding(0).borderRadius(8).backgroundColor(Color.Transparent).accessibilityText('返回')
        .onClick(() => this.getUIContext().getRouter().back())
      Text(this.title).fontSize(22).fontWeight(FontWeight.Bold).fontColor(SUPPORT_TEXT).layoutWeight(1)
        .maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
      if (this.settingsVisible) {
        Button({ type: ButtonType.Normal }) {
          SymbolGlyph($r('sys.symbol.gearshape')).fontSize(21).fontColor([APP_MUTED])
        }.width(40).height(40).padding(0).borderRadius(8).backgroundColor(APP_PRIMARY_SOFT).accessibilityText('服务设置')
          .onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/SupportSettings' }))
      }
    }.width('100%').height(68).padding({ top: 8, bottom: 12 })
  }
}

@Component
export struct SupportButton {
  @Prop label: string = '';
  @Prop secondary: boolean = false;
  @Prop isEnabled: boolean = true;
  onPress: () => void = () => {};
  build() {
    Button(this.label, { type: ButtonType.Normal })
      .width('100%').constraintSize({ minHeight: 46 }).padding({ top: 12, bottom: 12, left: 14, right: 14 })
      .fontSize(15).fontWeight(FontWeight.Medium).fontColor(this.secondary ? APP_PRIMARY : APP_SURFACE)
      .backgroundColor(this.secondary ? APP_PRIMARY_SOFT : APP_PRIMARY).borderRadius(8)
      .enabled(this.isEnabled).opacity(this.isEnabled ? 1 : 0.45).onClick(this.onPress)
  }
}

@Component
export struct SupportNotice {
  @Prop text: string = '';
  @Prop error: boolean = false;
  build() {
    Text(this.text).fontSize(13).lineHeight(21).fontColor(this.error ? APP_DANGER : SUPPORT_MUTED)
      .width('100%').padding({ top: 12, bottom: 12, left: this.error ? 12 : 0, right: 0 })
      .backgroundColor(this.error ? APP_DANGER_SOFT : Color.Transparent).borderRadius(8)
  }
}
