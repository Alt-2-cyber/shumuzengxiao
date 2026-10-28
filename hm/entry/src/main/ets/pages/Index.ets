import { common } from '@kit.AbilityKit';
import { preferences } from '@kit.ArkData';
import { promptAction } from '@kit.ArkUI';
import { photoAccessHelper } from '@kit.MediaLibraryKit';
import { NewsService, unreadNews } from '../news/NewsService';
import { APP_BACKGROUND, APP_SURFACE, APP_TEXT, APP_MUTED, APP_LINE, APP_PRIMARY, APP_PRIMARY_SOFT,
  APP_SUCCESS, APP_SUCCESS_SOFT, APP_WARNING, APP_WARNING_SOFT, APP_DANGER, APP_DANGER_SOFT, APP_FIELD } from '../support/AppTheme';

type RiskLevel = 'normal' | 'observe' | 'warning' | 'urgent';
type DeviceStatus = 'online' | 'offline' | 'maintenance';
type ActionTone = 'green' | 'gold' | 'red';

interface DiagnosisRecord {
  id: string;
  imagePath: string;
  createdAt: string;
  cowId: string;
  riskLevel: RiskLevel;
  score: number;
  conclusion: string;
  findings: string[];
  suggestions: string[];
  modelVersion: string;
}

interface MetricCard {
  label: string;
  value: string;
  note: string;
}

interface DeviceState {
  id: string;
  name: string;
  type: string;
  status: DeviceStatus;
  value: string;
}

interface AlertItem {
  id: string;
  title: string;
  source: string;
  level: RiskLevel;
  time: string;
}

interface AdminAction {
  id: string;
  title: string;
  subtitle: string;
  tone: ActionTone;
}

interface CommandLog {
  id: string;
  title: string;
  time: string;
}

const STORE_NAME = 'smart_cattle_store';
const RECORDS_KEY = 'diagnosis_records';
const PAGE_BG = APP_BACKGROUND;
const CARD_BG = APP_SURFACE;
const CARD_BG_SOFT = APP_FIELD;
const LINE = APP_LINE;
const TEXT = APP_TEXT;
const MUTED = APP_MUTED;
const GREEN = APP_SUCCESS;
const GOLD = APP_WARNING;
const RED = APP_DANGER;
const CREAM = APP_TEXT;

const FINDING_POOL: string[] = [
  '眼鼻区域未见明显分泌物，精神状态初步稳定',
  '皮毛反光较均匀，未见大面积脱毛或破损',
  '站姿稳定，未识别到明显跛行姿态',
  '鼻镜区域偏暗，建议补拍近距离头部照片',
  '腹部轮廓清晰，未见异常鼓胀迹象',
  '局部皮肤纹理不清，可能受光照或遮挡影响',
  '耳部姿态正常，仍需结合现场采食情况判断',
  '口鼻附近存在疑似湿润区域，建议人工复核'
];

const NORMAL_SUGGESTIONS: string[] = ['继续日常巡检', '保持牛舍通风与饮水', '按计划记录体温和采食情况'];
const OBSERVE_SUGGESTIONS: string[] = ['补拍眼鼻和皮肤局部照片', '观察 2 小时内活动量变化', '检查同栏牛只是否有类似表现'];
const WARNING_SUGGESTIONS: string[] = ['安排人工近距离复核', '记录体温、采食和呼吸频率', '必要时隔离观察并保留截图证据'];
const URGENT_SUGGESTIONS: string[] = ['立即通知管理员现场处理', '建议隔离疑似异常牛只', '联系兽医复核并同步环境数据'];

function pad(value: number): string {
  return value < 10 ? `0${value}` : `${value}`;
}

function formatTime(date: Date = new Date()): string {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

function riskText(level: RiskLevel): string {
  if (level === 'observe') {
    return '关注';
  }
  if (level === 'warning') {
    return '疑似异常';
  }
  if (level === 'urgent') {
    return '高风险';
  }
  return '健康';
}

function riskColor(level: RiskLevel): string {
  if (level === 'observe') {
    return APP_PRIMARY_SOFT;
  }
  if (level === 'warning') {
    return APP_WARNING_SOFT;
  }
  if (level === 'urgent') {
    return APP_DANGER_SOFT;
  }
  return APP_SUCCESS_SOFT;
}

function riskTextColor(level: RiskLevel): string {
  return level === 'urgent' ? APP_DANGER : level === 'warning' ? APP_WARNING : level === 'observe' ? APP_PRIMARY : APP_SUCCESS;
}

function deviceStatusText(status: DeviceStatus): string {
  if (status === 'maintenance') {
    return '维护';
  }
  if (status === 'offline') {
    return '离线';
  }
  return '在线';
}

function deviceStatusColor(status: DeviceStatus): string {
  if (status === 'maintenance') {
    return GOLD;
  }
  if (status === 'offline') {
    return APP_MUTED;
  }
  return GREEN;
}

function suggestionsFor(level: RiskLevel): string[] {
  if (level === 'observe') {
    return OBSERVE_SUGGESTIONS;
  }
  if (level === 'warning') {
    return WARNING_SUGGESTIONS;
  }
  if (level === 'urgent') {
    return URGENT_SUGGESTIONS;
  }
  return NORMAL_SUGGESTIONS;
}

function createMockAnalysis(imagePath: string): DiagnosisRecord {
  let seed = Date.now() % 97;
  for (let index = 0; index < imagePath.length; index++) {
    seed += imagePath.charCodeAt(index);
  }

  const score = 58 + (seed % 39);
  let riskLevel: RiskLevel = 'urgent';
  if (score >= 86) {
    riskLevel = 'normal';
  } else if (score >= 74) {
    riskLevel = 'observe';
  } else if (score >= 64) {
    riskLevel = 'warning';
  }

  const findingStart = seed % (FINDING_POOL.length - 2);
  const findings: string[] = [
    FINDING_POOL[findingStart],
    FINDING_POOL[findingStart + 1],
    FINDING_POOL[findingStart + 2]
  ];

  let conclusion = '多项图像特征偏离正常范围，建议立即现场处理。';
  if (riskLevel === 'normal') {
    conclusion = '图像特征整体稳定，未发现明显疾病风险。';
  } else if (riskLevel === 'observe') {
    conclusion = '存在轻微信号不确定性，建议补拍局部并持续观察。';
  } else if (riskLevel === 'warning') {
    conclusion = '识别到疑似异常体征，需要人工复核确认。';
  }

  return {
    id: `diag_${Date.now()}`,
    imagePath,
    createdAt: formatTime(),
    cowId: `C-${pad((seed % 86) + 1).padStart(3, '0')}`,
    riskLevel,
    score,
    conclusion,
    findings,
    suggestions: suggestionsFor(riskLevel),
    modelVersion: 'CattleVision-Mini v0.8'
  };
}

function getDevices(): DeviceState[] {
  return [
    { id: 'esp32_env_01', name: 'ESP32-S3 环境节点', type: '主控采集', status: 'online', value: '26.9℃ / 67%' },
    { id: 'maixcam_01', name: 'MaixCam 视觉节点', type: 'AI 摄像头', status: 'online', value: '9.8 FPS' },
    { id: 'mic_i2s_01', name: 'INMP441 声音节点', type: 'I2S 麦克风', status: 'online', value: 'VAD 正常' },
    { id: 'relay_box_01', name: '继电器控制箱', type: '执行器', status: 'online', value: '自动模式' }
  ];
}

function getAdminActions(): AdminAction[] {
  return [
    { id: 'fan', title: '开启风扇', subtitle: '通风 20 分钟', tone: 'green' },
    { id: 'capture', title: '触发抓拍', subtitle: '调用视觉节点', tone: 'gold' },
    { id: 'alarm', title: '声光提醒', subtitle: '通知现场巡检', tone: 'red' },
    { id: 'sync', title: '同步模型', subtitle: '更新识别参数', tone: 'green' }
  ];
}

@Entry
@Component
struct Index {
  @State newsUnread: number = 0;
  @State newsDailyTitle: string = '养牛新闻与每日小知识';
  private newsPoll: number = -1;

  onPageShow(): void {
    this.refreshNews();
    if (this.newsPoll >= 0) { clearInterval(this.newsPoll); }
    this.newsPoll = setInterval(() => this.refreshNews(), 60000);
  }
  onPageHide(): void { if (this.newsPoll >= 0) { clearInterval(this.newsPoll); this.newsPoll = -1; } }
  async refreshNews(): Promise<void> {
    try {
      await NewsService.init(getContext(this) as common.UIAbilityContext);
      const cached = await NewsService.cachedFeed();
      this.newsUnread = unreadNews(await NewsService.state());
      if (cached) { this.newsDailyTitle = cached.articles.find(item => item.id === cached.dailyKnowledgeId)?.title ?? this.newsDailyTitle; }
      const feed = await NewsService.refresh();
      this.newsUnread = unreadNews(await NewsService.state());
      this.newsDailyTitle = feed.articles.find(item => item.id === feed.dailyKnowledgeId)?.title ?? '养牛新闻与每日小知识';
    } catch (error) { /* Existing cached recommendations remain available. */ }
  }
  @State currentTab: number = 0;
  @State records: DiagnosisRecord[] = [];
  @State metrics: MetricCard[] = [];
  @State alerts: AlertItem[] = [];
  @State imagePath: string = '';
  @State analyzing: boolean = false;
  @State progress: number = 0;
  @State result: DiagnosisRecord | null = null;
  @State commandLogs: CommandLog[] = [];

  private analysisTimer: number = -1;
  private pageScroller: Scroller = new Scroller();

  aboutToAppear(): void {
    this.loadRecords();
    this.refreshDashboard();
  }

  toast(message: string, duration: number = 1500): void {
    try {
      promptAction.showToast({ message, duration });
    } catch (error) {
      console.info(message);
    }
  }

  async loadRecords(): Promise<void> {
    try {
      const context = getContext(this) as common.UIAbilityContext;
      const store = await preferences.getPreferences(context, STORE_NAME);
      const value = await store.get(RECORDS_KEY, '[]');
      if (typeof value === 'string') {
        this.records = JSON.parse(value) as DiagnosisRecord[];
        this.refreshDashboard();
      }
    } catch (error) {
      this.toast('本地记录读取失败，已使用空记录', 1800);
    }
  }

  async persistRecords(): Promise<void> {
    try {
      const context = getContext(this) as common.UIAbilityContext;
      const store = await preferences.getPreferences(context, STORE_NAME);
      await store.put(RECORDS_KEY, JSON.stringify(this.records));
      await store.flush();
    } catch (error) {
      this.toast('记录保存失败，请稍后重试', 1800);
    }
  }

  refreshDashboard(): void {
    const warningCount = this.records.filter((item: DiagnosisRecord) => item.riskLevel === 'warning' || item.riskLevel === 'urgent').length;
    const observeCount = this.records.filter((item: DiagnosisRecord) => item.riskLevel === 'observe').length;
    this.metrics = [
      { label: '在栏牛只', value: '86', note: '核心棚区' },
      { label: '设备在线', value: '4/4', note: '采集链路' },
      { label: '风险识别', value: `${warningCount}`, note: '需复核' },
      { label: '关注项', value: `${observeCount}`, note: '持续观察' }
    ];

    const recordAlerts: AlertItem[] = this.records
      .filter((item: DiagnosisRecord) => item.riskLevel !== 'normal')
      .slice(0, 5)
      .map((item: DiagnosisRecord): AlertItem => {
        return {
          id: item.id,
          title: `${item.cowId} ${riskText(item.riskLevel)}识别`,
          source: 'AI 照片分析',
          level: item.riskLevel,
          time: item.createdAt
        };
      });
    const staticAlerts: AlertItem[] = [
      { id: 'env_001', title: '氨气趋势偏高', source: '环境节点', level: 'observe', time: formatTime(new Date(Date.now() - 1000 * 60 * 38)) },
      { id: 'dev_001', title: 'MaixCam 在线', source: '设备状态', level: 'normal', time: formatTime(new Date(Date.now() - 1000 * 60 * 64)) }
    ];
    const allAlerts: AlertItem[] = recordAlerts.concat(staticAlerts);
    this.alerts = allAlerts.slice(0, 6);
  }

  async chooseImage(): Promise<void> {
    try {
      const picker = new photoAccessHelper.PhotoViewPicker();
      const options = new photoAccessHelper.PhotoSelectOptions();
      options.MIMEType = photoAccessHelper.PhotoViewMIMETypes.IMAGE_TYPE;
      options.maxSelectNumber = 1;
      options.isPhotoTakingSupported = true;
      const picked = await picker.select(options);
      if (picked.photoUris.length > 0) {
        this.imagePath = picked.photoUris[0];
        this.result = null;
        this.progress = 0;
      }
    } catch (error) {
      this.toast('未选择照片');
    }
  }

  analyzeImage(): void {
    if (this.imagePath.length === 0) {
      this.toast('请先上传牛只照片');
      return;
    }
    if (this.analyzing) {
      return;
    }

    this.analyzing = true;
    this.progress = 12;
    if (this.analysisTimer >= 0) {
      clearInterval(this.analysisTimer);
    }
    this.analysisTimer = setInterval(() => {
      this.progress = Math.min(this.progress + 18, 92);
    }, 180);

    setTimeout(() => {
      if (this.analysisTimer >= 0) {
        clearInterval(this.analysisTimer);
        this.analysisTimer = -1;
      }
      const analysis = createMockAnalysis(this.imagePath);
      this.result = analysis;
      this.records = [analysis].concat(this.records).slice(0, 50);
      this.analyzing = false;
      this.progress = 100;
      this.refreshDashboard();
      this.persistRecords();
      this.toast('分析完成');
    }, 1100);
  }

  resetImage(): void {
    this.imagePath = '';
    this.result = null;
    this.analyzing = false;
    this.progress = 0;
    if (this.analysisTimer >= 0) {
      clearInterval(this.analysisTimer);
      this.analysisTimer = -1;
    }
  }

  clearAllRecords(): void {
    if (this.records.length === 0) {
      this.toast('暂无记录');
      return;
    }

    AlertDialog.show({
      title: '清空识别记录',
      message: '本地保存的 AI 识牛记录会被清空，是否继续？',
      primaryButton: {
        value: '取消',
        action: () => {
        }
      },
      secondaryButton: {
        value: '清空',
        fontColor: RED,
        action: () => {
          this.records = [];
          this.result = null;
          this.refreshDashboard();
          this.persistRecords();
          this.toast('已清空');
        }
      }
    });
  }

  runAction(action: AdminAction): void {
    const now = new Date();
    const log: CommandLog = {
      id: `${Date.now()}`,
      title: action.title,
      time: `${pad(now.getHours())}:${pad(now.getMinutes())}`
    };
    this.commandLogs = [log].concat(this.commandLogs).slice(0, 4);
    this.toast(`${action.title}：本地演示已记录`);
  }

  openTab(index: number): void {
    this.currentTab = index;
    this.refreshDashboard();
    setTimeout((): void => { this.pageScroller.scrollEdge(Edge.Top); }, 40);
  }

  @Builder
  Eyebrow(text: string) {
    Text(text)
      .fontSize(12)
      .fontWeight(FontWeight.Bold)
      .fontColor(GREEN)
      .maxLines(1)
      .textOverflow({ overflow: TextOverflow.Ellipsis })
  }

  @Builder
  PageTitle(title: string, subtitle: string) {
    Column({ space: 6 }) {
      Text(title)
        .fontSize(26)
        .fontWeight(FontWeight.Bold)
        .fontColor(TEXT)
      Text(subtitle)
        .fontSize(13)
        .lineHeight(20)
        .fontColor(MUTED)
    }
    .alignItems(HorizontalAlign.Start)
    .width('100%')
  }

  @Builder
  SectionHead(title: string, note: string = '') {
    Row() {
      Text(title)
        .fontSize(18)
        .fontWeight(FontWeight.Bold)
        .fontColor(TEXT)
        .layoutWeight(1)
      if (note.length > 0) {
        Text(note)
          .fontSize(12)
          .fontColor(MUTED)
      }
    }
    .width('100%')
    .margin({ top: 8, bottom: 4 })
  }

  @Builder
  Pill(label: string, level: RiskLevel) {
    Text(label)
      .fontSize(12)
      .fontWeight(FontWeight.Bold)
      .fontColor(riskTextColor(level))
      .padding({ left: 10, right: 10, top: 5, bottom: 5 })
      .backgroundColor(riskColor(level))
      .borderRadius(4)
      .maxLines(1)
  }

  @Builder
  StatusPill(status: DeviceStatus) {
    Text(deviceStatusText(status))
      .fontSize(12)
      .fontWeight(FontWeight.Bold)
      .fontColor(status === 'online' ? APP_SUCCESS : status === 'maintenance' ? APP_WARNING : APP_MUTED)
      .padding({ left: 10, right: 10, top: 5, bottom: 5 })
      .backgroundColor(status === 'online' ? APP_SUCCESS_SOFT : status === 'maintenance' ? APP_WARNING_SOFT : APP_FIELD)
      .borderRadius(4)
  }

  @Builder
  Metric(item: MetricCard) {
    Column({ space: 10 }) {
      Row() {
        Text(item.label).fontSize(13).fontColor(MUTED).layoutWeight(1)
        if (item.label === '在栏牛只') {
          SymbolGlyph($r('sys.symbol.heart')).fontSize(17).fontColor([APP_PRIMARY])
        } else if (item.label === '设备在线') {
          SymbolGlyph($r('sys.symbol.wifi')).fontSize(17).fontColor([APP_SUCCESS])
        } else if (item.label === '风险识别') {
          SymbolGlyph($r('sys.symbol.bell')).fontSize(17).fontColor([APP_DANGER])
        } else {
          SymbolGlyph($r('sys.symbol.eye')).fontSize(17).fontColor([APP_WARNING])
        }
      }.width('100%')
      Row({ space: 8 }) {
        Text(item.value).fontSize(30).fontWeight(FontWeight.Bold).fontColor(TEXT).layoutWeight(1)
        Text(item.note).fontSize(11).fontColor(MUTED).maxLines(1)
      }.width('100%').alignItems(VerticalAlign.Bottom)
    }
    .alignItems(HorizontalAlign.Start)
    .padding(14)
    .height(102)
    .width('100%')
    .backgroundColor(CARD_BG)
    .borderRadius(8)
  }

  @Builder
  DeviceCard(device: DeviceState) {
    Column({ space: 10 }) {
      Row({ space: 8 }) {
        Text(device.name)
          .fontSize(14)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT)
          .layoutWeight(1)
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
        this.StatusPill(device.status)
      }
      .width('100%')
      Text(device.type)
        .fontSize(12)
        .fontColor(MUTED)
      Text(device.value)
        .fontSize(20)
        .fontWeight(FontWeight.Bold)
        .fontColor(GOLD)
    }
    .alignItems(HorizontalAlign.Start)
    .padding(14)
    .height(128)
    .width('100%')
    .backgroundColor(CARD_BG)
    .border({ width: 1, color: LINE })
    .borderRadius(8)
  }

  @Builder
  AlertRow(alert: AlertItem) {
    Row({ space: 12 }) {
      Column({ space: 6 }) {
        Text(alert.title)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT)
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
        Text(`${alert.source} · ${alert.time}`)
          .fontSize(12)
          .fontColor(MUTED)
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1)
      this.Pill(riskText(alert.level), alert.level)
    }
    .alignItems(VerticalAlign.Top)
    .padding(14)
    .width('100%')
    .backgroundColor(CARD_BG)
    .border({ width: 1, color: LINE })
    .borderRadius(8)
  }

  @Builder
  PrimaryButton(label: string, enabled: boolean = true) {
    Text(label)
      .fontSize(15)
      .fontWeight(FontWeight.Bold)
      .fontColor(APP_SURFACE)
      .textAlign(TextAlign.Center)
      .height(48)
      .width('100%')
      .borderRadius(8)
      .backgroundColor(enabled ? APP_PRIMARY : APP_LINE)
      .opacity(enabled ? 1 : 0.65)
      .align(Alignment.Center)
  }

  @Builder
  GhostButton(label: string) {
    Text(label)
      .fontSize(15)
      .fontWeight(FontWeight.Bold)
      .fontColor(APP_PRIMARY)
      .textAlign(TextAlign.Center)
      .height(48)
      .width('100%')
      .borderRadius(8)
      .backgroundColor(APP_PRIMARY_SOFT)
      .align(Alignment.Center)
  }

  @Builder
  SupportShortcuts() {
    Row({ space: 12 }) {
      this.Shortcut('AI 助手', '巡检问答', $r('sys.symbol.wand_and_stars'), APP_PRIMARY, APP_PRIMARY_SOFT, 'pages/Assistant')
      this.Shortcut('专家咨询', '问题与回执', $r('sys.symbol.person_2'), APP_SUCCESS, APP_SUCCESS_SOFT, 'pages/Consultation')
      this.Shortcut('养牛资讯', this.newsUnread > 0 ? `${this.newsUnread} 条未读` : '每日小知识',
        $r('sys.symbol.book'), APP_WARNING, APP_WARNING_SOFT, 'pages/News')
    }.width('100%').padding({ top: 4, bottom: 4 })
  }

  @Builder
  Shortcut(title: string, subtitle: string, icon: Resource, color: string, background: string, route: string) {
    Button({ type: ButtonType.Normal }) {
      Column({ space: 8 }) {
        SymbolGlyph(icon).fontSize(25).fontColor([color]).width(48).height(48)
          .backgroundColor(background).borderRadius(8)
        Text(title).fontSize(14).fontWeight(FontWeight.Medium).fontColor(TEXT).maxLines(1)
        Text(subtitle).fontSize(11).fontColor(MUTED).maxLines(1).textOverflow({ overflow: TextOverflow.Ellipsis })
      }.width('100%').padding({ top: 6, bottom: 6 })
    }.layoutWeight(1).padding(0).backgroundColor(Color.Transparent).borderRadius(8)
      .onClick(() => this.getUIContext().getRouter().pushUrl({ url: route }))
  }

  @Builder
  DashboardPage() {
    Column({ space: 16 }) {
      Row({ space: 12 }) {
        Column({ space: 6 }) {
          Text('数牧增效').fontSize(27).fontWeight(FontWeight.Bold).fontColor(TEXT)
          Text('牛舍智能巡检工作台').fontSize(13).fontColor(MUTED)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Button({ type: ButtonType.Normal }) {
          SymbolGlyph($r('sys.symbol.gearshape')).fontSize(22).fontColor([TEXT])
        }.width(42).height(42).padding(0).borderRadius(8).backgroundColor(APP_SURFACE)
          .accessibilityText('服务设置').onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/SupportSettings' }))
      }.width('100%').padding({ bottom: 4 })

      Row() {
        Text('巡检概览').fontSize(17).fontWeight(FontWeight.Bold).fontColor(TEXT).layoutWeight(1)
        Text('养殖场与设备为示例数据').fontSize(11).fontColor(MUTED)
      }.width('100%')

      Grid() {
        ForEach(this.metrics, (item: MetricCard) => {
          GridItem() {
            this.Metric(item)
          }
        }, (item: MetricCard) => item.label)
      }
      .columnsTemplate('1fr 1fr')
      .columnsGap(10)
      .rowsGap(10)
      .height(214)
      .width('100%')

      Button({ type: ButtonType.Normal }) {
        Row({ space: 14 }) {
          SymbolGlyph($r('sys.symbol.camera')).fontSize(30).fontColor([APP_PRIMARY])
            .width(54).height(54).backgroundColor(APP_PRIMARY_SOFT).borderRadius(8)
          Column({ space: 5 }) {
            Text('拍照巡检').fontSize(19).fontWeight(FontWeight.Bold).fontColor(TEXT)
            Text('牛只照片 · 本地演示分析').fontSize(12).fontColor(MUTED)
          }.layoutWeight(1).alignItems(HorizontalAlign.Start)
          SymbolGlyph($r('sys.symbol.arrow_right')).fontSize(22).fontColor([APP_PRIMARY])
        }.width('100%').padding(16)
      }.width('100%').padding(0).backgroundColor(APP_SURFACE).borderRadius(8)
        .onClick(() => { this.openTab(1); })

      this.SectionHead('巡检服务')
      this.SupportShortcuts()

      Row({ space: 10 }) {
        Text('今日知识').fontSize(11).fontWeight(FontWeight.Medium).fontColor(APP_SUCCESS)
          .padding({ left: 7, right: 7, top: 5, bottom: 5 }).backgroundColor(APP_SUCCESS_SOFT).borderRadius(4)
        Text(this.newsDailyTitle).fontSize(13).fontColor(TEXT).maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis }).layoutWeight(1)
        SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(13).fontColor([MUTED])
      }.width('100%').padding({ top: 12, bottom: 12 }).border({ width: { top: 1, bottom: 1 }, color: LINE })
        .onClick(() => this.getUIContext().getRouter().pushUrl({ url: 'pages/News' }))

      this.SectionHead('最近巡检', `${this.records.length} 条本机记录`)
      if (this.records.length > 0) {
        this.LatestRecord(this.records[0])
      } else {
        this.EmptyState('今天，从一次巡检开始', '暂无本机照片记录', '上传照片分析', 1)
      }

      this.SectionHead('设备概况', '本地示例')
      Grid() {
        ForEach(getDevices(), (item: DeviceState) => {
          GridItem() {
            this.DeviceCard(item)
          }
        }, (item: DeviceState) => item.id)
      }
      .columnsTemplate('1fr 1fr')
      .columnsGap(10)
      .rowsGap(10)
      .height(266)
      .width('100%')

      this.SectionHead('告警动态', '本机记录 / 示例事件')
      ForEach(this.alerts.slice(0, 4), (item: AlertItem) => {
        this.AlertRow(item)
      }, (item: AlertItem) => item.id)
    }
    .width('100%')
  }

  @Builder
  LatestRecord(record: DiagnosisRecord) {
    Row({ space: 12 }) {
      Image(record.imagePath)
        .width(108)
        .height(108)
        .objectFit(ImageFit.Cover)
        .borderRadius(8)
        .backgroundColor(APP_FIELD)
      Column({ space: 8 }) {
        Row({ space: 8 }) {
          Text(record.cowId)
            .fontSize(19)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT)
            .layoutWeight(1)
          this.Pill(riskText(record.riskLevel), record.riskLevel)
        }
        .width('100%')
        Text(`${record.score}`)
          .fontSize(42)
          .fontWeight(FontWeight.Bold)
          .fontColor(GREEN)
        Text(record.conclusion)
          .fontSize(13)
          .fontColor(MUTED)
          .maxLines(2)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
        Text(record.createdAt)
          .fontSize(11)
          .fontColor(APP_MUTED)
      }
      .alignItems(HorizontalAlign.Start)
      .layoutWeight(1)
    }
    .padding(12)
    .width('100%')
    .backgroundColor(CARD_BG)
    .border({ width: 1, color: LINE })
    .borderRadius(8)
  }

  @Builder
  EmptyState(title: string, body: string, action: string, tab: number) {
    Column({ space: 12 }) {
      SymbolGlyph($r('sys.symbol.doc_text')).fontSize(30).fontColor([APP_PRIMARY])
      Text(title)
        .fontSize(16)
        .fontWeight(FontWeight.Bold)
        .fontColor(TEXT)
        .textAlign(TextAlign.Center)
      Text(body)
        .fontSize(14)
        .lineHeight(22)
        .fontColor(MUTED)
        .textAlign(TextAlign.Center)
      Button({ type: ButtonType.Normal }) {
        this.PrimaryButton(action)
      }
      .width('80%')
      .backgroundColor(Color.Transparent)
      .onClick(() => {
        this.openTab(tab);
      })
    }
    .padding(24)
    .width('100%')
    .backgroundColor(Color.Transparent)
  }

  @Builder
  DiagnosisPage() {
    Column({ space: 16 }) {
      this.PageTitle('拍照巡检', '牛只影像记录')

      Row({ space: 8 }) {
        SymbolGlyph($r('sys.symbol.info_circle')).fontSize(16).fontColor([APP_WARNING])
        Text('本地演示分析，结果不作为疾病诊断依据').fontSize(12).lineHeight(20).fontColor(APP_WARNING).layoutWeight(1)
      }.width('100%').padding(12).backgroundColor(APP_WARNING_SOFT).borderRadius(8)

      Stack() {
        if (this.imagePath.length > 0) {
          Image(this.imagePath)
            .width('100%')
            .height('100%')
            .objectFit(ImageFit.Cover)
            .borderRadius(8)
        } else {
          Column({ space: 16 }) {
            SymbolGlyph($r('sys.symbol.camera')).fontSize(40).fontColor([APP_PRIMARY])
              .width(80).height(80).backgroundColor(APP_PRIMARY_SOFT).borderRadius(8)
            Text('上传或拍摄牛只照片')
              .fontSize(19)
              .fontWeight(FontWeight.Bold)
              .fontColor(TEXT)
          }
          .alignItems(HorizontalAlign.Center)
          .padding(24)
        }
      }
      .height(300)
      .width('100%')
      .backgroundColor(CARD_BG)
      .border({ width: 1, color: LINE, style: BorderStyle.Dashed })
      .borderRadius(8)
      .onClick(() => {
        this.chooseImage();
      })

      if (this.analyzing || this.progress > 0) {
        Column({ space: 8 }) {
          Progress({ value: this.progress, total: 100, type: ProgressType.Linear })
            .width('100%')
            .color(GREEN)
            .backgroundColor(APP_FIELD)
          Text(this.analyzing ? '正在扫描图像特征...' : '分析完成')
            .fontSize(12)
            .fontColor(MUTED)
        }
        .width('100%')
      }

      Row({ space: 10 }) {
        Button({ type: ButtonType.Normal }) {
          this.PrimaryButton(this.analyzing ? '分析中...' : '开始 AI 分析', !this.analyzing)
        }
        .layoutWeight(1)
        .backgroundColor(Color.Transparent)
        .enabled(!this.analyzing && this.imagePath.length > 0)
        .opacity(this.imagePath.length > 0 ? 1 : 0.45)
        .onClick(() => {
          this.analyzeImage();
        })

        Button({ type: ButtonType.Normal }) {
          this.GhostButton('重新选择')
        }
        .layoutWeight(1)
        .backgroundColor(Color.Transparent)
        .enabled(!this.analyzing)
        .onClick(() => { this.chooseImage(); })
      }
      .width('100%')

      if (this.result !== null) {
        this.ResultPanel(this.result)
      }
    }
    .width('100%')
  }

  @Builder
  ResultPanel(record: DiagnosisRecord | null) {
    if (record !== null) {
      Column({ space: 14 }) {
        Row() {
          Column({ space: 6 }) {
            Text('健康评分')
              .fontSize(13)
              .fontWeight(FontWeight.Bold)
              .fontColor(MUTED)
            Text(`${record.score}`)
              .fontSize(56)
              .fontWeight(FontWeight.Bold)
              .fontColor(GREEN)
          }
          .alignItems(HorizontalAlign.Start)
          .layoutWeight(1)
          Column({ space: 8 }) {
            this.Pill(riskText(record.riskLevel), record.riskLevel)
            Text(record.modelVersion)
              .fontSize(11)
              .fontColor(APP_MUTED)
          }
          .alignItems(HorizontalAlign.End)
        }
        .width('100%')

        Text(record.conclusion)
          .fontSize(15)
          .lineHeight(23)
          .fontColor(TEXT)
          .padding(12)
          .width('100%')
          .backgroundColor(APP_FIELD)
          .borderRadius(8)

        this.SectionHead('识别特征')
        ForEach(record.findings, (item: string) => {
          Row({ space: 10 }) {
            Circle()
              .width(7)
              .height(7)
              .fill(GOLD)
              .margin({ top: 8 })
            Text(item)
              .fontSize(14)
              .lineHeight(22)
              .fontColor(APP_TEXT)
              .layoutWeight(1)
          }
          .width('100%')
          .alignItems(VerticalAlign.Top)
        }, (item: string) => item)

        this.SectionHead('处理建议')
        Flex({ wrap: FlexWrap.Wrap, justifyContent: FlexAlign.Start }) {
          ForEach(record.suggestions, (item: string) => {
            Text(item)
              .fontSize(12)
              .fontWeight(FontWeight.Bold)
              .fontColor(APP_SUCCESS)
              .padding({ left: 10, right: 10, top: 8, bottom: 8 })
              .margin({ right: 8, bottom: 8 })
              .backgroundColor(APP_SUCCESS_SOFT)
              .borderRadius(8)
          }, (item: string) => item)
        }
        .width('100%')

        Button({ type: ButtonType.Normal }) {
          this.GhostButton('查看全部记录')
        }
        .width('100%')
        .backgroundColor(Color.Transparent)
        .onClick(() => {
          this.openTab(2);
        })
      }
      .alignItems(HorizontalAlign.Start)
      .padding({ top: 16, bottom: 16 })
      .width('100%')
      .backgroundColor(Color.Transparent)
    }
  }

  @Builder
  RecordsPage() {
    Column({ space: 16 }) {
      Row({ space: 10 }) {
        Column({ space: 6 }) {
          Text('识别记录')
            .fontSize(26)
            .fontWeight(FontWeight.Bold)
            .fontColor(TEXT)
          Text(`${this.records.length} 条本机记录`).fontSize(13).fontColor(MUTED)
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
        Button({ type: ButtonType.Normal }) {
          SymbolGlyph($r('sys.symbol.trash')).fontSize(21).fontColor([RED])
        }.height(42).width(42).padding(0).borderRadius(8).backgroundColor(APP_DANGER_SOFT)
          .accessibilityText('清空记录').enabled(this.records.length > 0).opacity(this.records.length > 0 ? 1 : 0.4)
          .onClick(() => {
            this.clearAllRecords();
          })
      }
      .width('100%')

      if (this.records.length === 0) {
        this.EmptyState('还没有保存的识别结果', '本机照片记录将保存在这里', '去上传照片', 1)
      } else {
        ForEach(this.records, (item: DiagnosisRecord) => {
          this.RecordCard(item)
        }, (item: DiagnosisRecord) => item.id)
      }
    }
    .width('100%')
  }

  @Builder
  RecordCard(record: DiagnosisRecord) {
    Column({ space: 12 }) {
      Row({ space: 12 }) {
        Image(record.imagePath)
          .width(96)
          .height(116)
          .objectFit(ImageFit.Cover)
          .borderRadius(8)
          .backgroundColor(APP_FIELD)
        Column({ space: 8 }) {
          Row({ space: 8 }) {
            Text(record.cowId)
              .fontSize(18)
              .fontWeight(FontWeight.Bold)
              .fontColor(TEXT)
              .layoutWeight(1)
            this.Pill(riskText(record.riskLevel), record.riskLevel)
          }
          .width('100%')
          Row({ space: 8 }) {
            Text(`${record.score}`)
              .fontSize(34)
              .fontWeight(FontWeight.Bold)
              .fontColor(GREEN)
            Text('健康评分')
              .fontSize(12)
              .fontWeight(FontWeight.Bold)
              .fontColor(MUTED)
          }
          Text(record.conclusion)
            .fontSize(13)
            .lineHeight(20)
            .fontColor(APP_TEXT)
            .maxLines(2)
            .textOverflow({ overflow: TextOverflow.Ellipsis })
          Text(record.createdAt)
            .fontSize(11)
            .fontColor(APP_MUTED)
        }
        .alignItems(HorizontalAlign.Start)
        .layoutWeight(1)
      }
      .width('100%')

      Text(record.findings.join('；')).fontSize(12).fontColor(MUTED).lineHeight(21).maxLines(3)
        .textOverflow({ overflow: TextOverflow.Ellipsis }).width('100%')
    }
    .padding(12)
    .width('100%')
    .backgroundColor(CARD_BG)
    .border({ width: 1, color: LINE })
    .borderRadius(8)
  }

  @Builder
  AdminPage() {
    Column({ space: 16 }) {
      Row() {
        Column({ space: 6 }) {
          Text('设备管理').fontSize(26).fontWeight(FontWeight.Bold).fontColor(TEXT)
          Text('设备概况与本地控制记录').fontSize(13).fontColor(MUTED)
        }.layoutWeight(1).alignItems(HorizontalAlign.Start)
        Button({ type: ButtonType.Normal }) {
          SymbolGlyph($r('sys.symbol.arrow_clockwise')).fontSize(21).fontColor([APP_PRIMARY])
        }.width(42).height(42).padding(0).backgroundColor(APP_SURFACE).borderRadius(8).accessibilityText('刷新')
          .onClick(() => { this.refreshDashboard(); this.toast('已刷新看板'); })
      }.width('100%')

      Row({ space: 10 }) {
        SymbolGlyph($r('sys.symbol.info_circle')).fontSize(18).fontColor([APP_PRIMARY])
        Text('设备状态与控制为本地演示').fontSize(13).fontColor(APP_PRIMARY).layoutWeight(1)
      }.width('100%').padding(14).backgroundColor(APP_PRIMARY_SOFT).borderRadius(8)

      this.SupportShortcuts()

      this.SectionHead('设备控制', '演示操作')
      Grid() {
        ForEach(getAdminActions(), (item: AdminAction) => {
          GridItem() {
            this.ActionCard(item)
          }
        }, (item: AdminAction) => item.id)
      }
      .columnsTemplate('1fr 1fr')
      .columnsGap(10)
      .rowsGap(10)
      .height(214)
      .width('100%')

      this.SectionHead('设备状态', '4 个示例节点')
      ForEach(getDevices(), (device: DeviceState) => {
        Row({ space: 12 }) {
          Circle()
            .width(10)
            .height(10)
            .fill(deviceStatusColor(device.status))
          Column({ space: 6 }) {
            Text(device.name)
              .fontSize(15)
              .fontWeight(FontWeight.Bold)
              .fontColor(TEXT)
            Text(`${device.type} · ${device.value}`)
              .fontSize(12)
              .fontColor(MUTED)
          }
          .alignItems(HorizontalAlign.Start)
          .layoutWeight(1)
          this.StatusPill(device.status)
        }
        .padding(14)
        .width('100%')
        .backgroundColor(CARD_BG)
        .border({ width: 1, color: LINE })
        .borderRadius(8)
      }, (device: DeviceState) => device.id)

      this.SectionHead('告警队列', '本机记录 / 示例事件')
      ForEach(this.alerts.slice(0, 5), (item: AlertItem) => {
        this.AlertRow(item)
      }, (item: AlertItem) => item.id)

      if (this.commandLogs.length > 0) {
        this.SectionHead('本地操作记录')
        Column() {
          ForEach(this.commandLogs, (item: CommandLog) => {
            Row() {
              Text(item.title)
                .fontSize(14)
                .fontWeight(FontWeight.Bold)
                .fontColor(TEXT)
                .layoutWeight(1)
              Text(item.time)
                .fontSize(13)
                .fontWeight(FontWeight.Bold)
                .fontColor(GREEN)
            }
            .padding(14)
            .width('100%')
            .border({ width: { bottom: 1 }, color: APP_LINE })
          }, (item: CommandLog) => item.id)
        }
        .width('100%')
        .backgroundColor(APP_FIELD)
        .borderRadius(8)
        .border({ width: 1, color: LINE })
      }
    }
    .width('100%')
  }

  @Builder
  ActionCard(action: AdminAction) {
    Button({ type: ButtonType.Normal }) {
      Column({ space: 10 }) {
        Row() {
          if (action.id === 'capture') {
            SymbolGlyph($r('sys.symbol.camera')).fontSize(23).fontColor([APP_PRIMARY])
          } else if (action.id === 'alarm') {
            SymbolGlyph($r('sys.symbol.bell')).fontSize(23).fontColor([APP_DANGER])
          } else if (action.id === 'sync') {
            SymbolGlyph($r('sys.symbol.arrow_clockwise')).fontSize(23).fontColor([APP_PRIMARY])
          } else {
            SymbolGlyph($r('sys.symbol.wind')).fontSize(23).fontColor([APP_SUCCESS])
          }
          Blank()
          SymbolGlyph($r('sys.symbol.chevron_right')).fontSize(13).fontColor([MUTED])
        }.width('100%')
        Text(action.title)
          .fontSize(15)
          .fontWeight(FontWeight.Bold)
          .fontColor(TEXT)
          .maxLines(1)
          .textOverflow({ overflow: TextOverflow.Ellipsis })
      }
      .alignItems(HorizontalAlign.Start)
      .justifyContent(FlexAlign.SpaceBetween)
      .padding(14)
      .height(102)
      .width('100%')
      .backgroundColor(APP_SURFACE)
      .borderRadius(8)
    }
    .backgroundColor(Color.Transparent)
    .onClick(() => {
      this.runAction(action);
    })
  }

  @Builder
  TabBar() {
    Row() {
      this.TabItem(0, '总览', $r('sys.symbol.house'))
      this.TabItem(1, '巡检', $r('sys.symbol.camera'))
      this.TabItem(2, '记录', $r('sys.symbol.doc_text'))
      this.TabItem(3, '管理', $r('sys.symbol.square_grid_2x2'))
    }
    .padding({ left: 12, right: 12, top: 6, bottom: 8 })
    .width('100%')
    .backgroundColor(APP_SURFACE)
    .border({ width: { top: 1 }, color: LINE })
  }

  @Builder
  TabItem(index: number, label: string, icon: Resource) {
    Button({ type: ButtonType.Normal }) {
      Column({ space: 5 }) {
        SymbolGlyph(icon).fontSize(23).fontColor([this.currentTab === index ? APP_PRIMARY : MUTED])
        Text(label).fontSize(11).fontWeight(this.currentTab === index ? FontWeight.Bold : FontWeight.Regular)
          .fontColor(this.currentTab === index ? APP_PRIMARY : MUTED)
      }.width('100%').height(54).justifyContent(FlexAlign.Center)
    }
    .layoutWeight(1)
    .padding(0)
    .borderRadius(8)
    .backgroundColor(Color.Transparent)
    .onClick(() => {
      this.openTab(index);
    })
  }

  build() {
    Stack({ alignContent: Alignment.Bottom }) {
      Scroll(this.pageScroller) {
        Column({ space: 18 }) {
          if (this.currentTab === 0) {
            this.DashboardPage()
          } else if (this.currentTab === 1) {
            this.DiagnosisPage()
          } else if (this.currentTab === 2) {
            this.RecordsPage()
          } else {
            this.AdminPage()
          }
        }
        .width('100%')
        .padding({ left: 20, right: 20, top: 20, bottom: 100 })
      }
      .width('100%')
      .height('100%')
      .backgroundColor(PAGE_BG)
      .align(Alignment.TopStart)
      .scrollBar(BarState.Off)

      this.TabBar()
    }
    .height('100%')
    .width('100%')
    .backgroundColor(PAGE_BG)
  }
}
