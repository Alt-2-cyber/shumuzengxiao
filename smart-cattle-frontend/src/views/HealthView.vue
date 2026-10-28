<template>
  <div class="health-screen-page grid page-stack">
    <section class="health-live-strip" :class="`quality-${qualityClass}`">
      <div class="health-live-identity">
        <span class="health-live-dot"></span>
        <div>
          <strong>实时健康筛查</strong>
          <span>{{ screen.targetId || latest?.deviceId || '等待 ESP32 节点' }}</span>
        </div>
      </div>
      <div class="health-live-stat">
        <CircleDashed :size="17" />
        <span>{{ modeLabel }}</span>
      </div>
      <div class="health-live-stat">
        <DatabaseZap :size="17" />
        <span>{{ baselineLabel }}</span>
      </div>
      <div class="health-live-stat">
        <ShieldCheck :size="17" />
        <span>{{ qualityLabel }}</span>
      </div>
    </section>

    <section class="health-screen-summary">
      <article class="card pad health-score-card" :class="`severity-${screen.riskLevel || 'NORMAL'}`">
        <div class="section-title">
          <h2>健康风险筛查</h2>
          <SeverityPill :value="screen.riskLevel || 'NORMAL'" />
        </div>
        <div class="health-score-readout">
          <div class="health-score-icon">
            <ShieldAlert v-if="screen.riskLevel === 'WARNING'" :size="31" />
            <ShieldCheck v-else :size="31" />
          </div>
          <div>
            <strong>{{ riskHeadline }}</strong>
            <span>{{ screen.version || 'health-screen-v1' }}</span>
          </div>
          <div class="health-score-number">{{ scorePercent }}<small>%</small></div>
        </div>
        <div class="health-score-track" aria-label="健康风险筛查分数">
          <span :style="{ width: `${scorePercent}%` }"></span>
        </div>
        <p class="health-screen-message">{{ screen.message || '正在等待实时健康遥测' }}</p>
        <div class="screen-detail-grid">
          <div>
            <span>当前窗口</span>
            <strong>{{ fixed(screen.currentWindowMinutes, 0, ' min') }}</strong>
          </div>
          <div>
            <span>有效行为</span>
            <strong>{{ screen.current?.behaviorSamples ?? '-' }}</strong>
          </div>
          <div>
            <span>风险证据</span>
            <strong>{{ risks.length }}</strong>
          </div>
          <div>
            <span>数据质量</span>
            <strong>{{ qualityLabel }}</strong>
          </div>
        </div>
      </article>

      <article class="card pad baseline-card">
        <div class="section-title">
          <h2>个体基线</h2>
          <span class="baseline-chip">{{ baselineState }}</span>
        </div>
        <div class="baseline-readout">
          <div>
            <span>有效历史</span>
            <strong>{{ fixed(baselineHours, 1, ' h') }}</strong>
          </div>
          <div>
            <span>目标保留</span>
            <strong>{{ screen.baselineRetentionDays || 7 }} 天</strong>
          </div>
          <div>
            <span>总观察门槛</span>
            <strong>{{ screen.minimumObservationMinutes || 90 }} min</strong>
          </div>
        </div>
        <div class="baseline-trend-grid">
          <div>
            <span>采食基线</span>
            <strong>{{ percent(screen.baseline?.grazingRatio) }}</strong>
          </div>
          <div>
            <span>反刍基线</span>
            <strong>{{ percent(screen.baseline?.ruminationRatio) }}</strong>
          </div>
          <div>
            <span>活动基线</span>
            <strong>{{ fixed(screen.baseline?.activity, 2) }}</strong>
          </div>
          <div>
            <span>体表温度</span>
            <strong>{{ fixed(screen.baseline?.surfaceTemperature, 1, '°C') }}</strong>
          </div>
        </div>
        <p class="baseline-note">基线保存在当前后端运行会话中；重启后会重新学习。</p>
      </article>
    </section>

    <section class="health-signal-grid">
      <article class="card pad health-signal-card">
        <div class="health-signal-head">
          <span class="health-signal-icon signal-behavior"><Wheat :size="20" /></span>
          <span>行为与采食</span>
        </div>
        <strong>{{ behaviorLabel(latest?.behavior?.state) }}</strong>
        <div class="signal-pair"><span>采食</span><b>{{ percent(screen.current?.grazingRatio) }}</b></div>
        <div class="signal-pair"><span>反刍</span><b>{{ percent(screen.current?.ruminationRatio) }}</b></div>
      </article>

      <article class="card pad health-signal-card">
        <div class="health-signal-head">
          <span class="health-signal-icon signal-vision"><ScanSearch :size="20" /></span>
          <span>视觉复核证据</span>
        </div>
        <strong>{{ activeVisionEvidence.length ? `${activeVisionEvidence.length} 项` : '无有效证据' }}</strong>
        <div class="signal-pair"><span>有效窗口</span><b>{{ screen.vision?.maximumAgeMinutes || '-' }} min</b></div>
        <div class="signal-pair"><span>病灶/步态</span><b>{{ visionEvidenceText }}</b></div>
      </article>

      <article class="card pad health-signal-card">
        <div class="health-signal-head">
          <span class="health-signal-icon signal-motion"><Activity :size="20" /></span>
          <span>活动与姿态</span>
        </div>
        <strong>{{ fixed(screen.current?.activity, 2) }}</strong>
        <div class="signal-pair"><span>卧姿比例</span><b>{{ percent(screen.current?.lyingRatio) }}</b></div>
        <div class="signal-pair"><span>行走比例</span><b>{{ percent(screen.current?.walkingRatio) }}</b></div>
        <div class="signal-pair"><span>IMU 跛行模型</span><b>{{ lamenessStatus }}</b></div>
      </article>

      <article class="card pad health-signal-card">
        <div class="health-signal-head">
          <span class="health-signal-icon signal-temperature"><Thermometer :size="20" /></span>
          <span>体表温度</span>
        </div>
        <strong>{{ fixed(screen.current?.surfaceTemperature, 1, '°C') }}</strong>
        <div class="signal-pair"><span>B-1 状态</span><b>{{ b1Status }}</b></div>
        <div class="signal-pair"><span>温度样本</span><b>{{ screen.current?.temperatureSamples ?? '-' }}</b></div>
      </article>

      <article class="card pad health-signal-card">
        <div class="health-signal-head">
          <span class="health-signal-icon signal-audio"><Mic2 :size="20" /></span>
          <span>声音候选</span>
        </div>
        <strong>{{ percent(screen.current?.vocalizationRate) }}</strong>
        <div class="signal-pair"><span>麦克风</span><b>{{ microphoneStatus }}</b></div>
        <div class="signal-pair"><span>音频样本</span><b>{{ screen.current?.microphoneSamples ?? '-' }}</b></div>
        <div class="signal-pair"><span>异常鸣叫模型</span><b>{{ percent(screen.current?.abnormalVocalizationCandidateRate) }}</b></div>
        <div class="signal-pair"><span>声音模型样本</span><b>{{ screen.current?.audioModelSamples ?? '-' }}</b></div>
      </article>
    </section>

    <section class="card pad health-source-panel">
      <div class="section-title health-source-title">
        <div>
          <h2>多源融合证据矩阵</h2>
          <span class="muted">视觉 / 声音 / 运动为主要边缘来源，温度和临床记录作为复核证据</span>
        </div>
        <span class="fusion-chip" :class="fusionStateClass">{{ fusionStateLabel }}</span>
      </div>
      <div class="table-scroll">
        <table class="table health-source-table">
          <thead>
            <tr>
              <th>来源</th>
              <th>在线</th>
              <th>新鲜度</th>
              <th>模型 / 复核</th>
              <th>当前融合</th>
              <th>状态说明</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="source in sourceRows" :key="source.key">
              <td>
                <strong>{{ source.label }}</strong>
                <small>{{ source.device }}</small>
              </td>
              <td><span class="source-status" :class="booleanClass(source.online)">{{ onlineLabel(source.online) }}</span></td>
              <td><span class="source-status" :class="freshClass(source)">{{ freshLabel(source) }}</span></td>
              <td><span class="source-status" :class="approvalClass(source)">{{ approvalLabel(source) }}</span></td>
              <td><span class="source-status" :class="participationClass(source)">{{ participationLabel(source) }}</span></td>
              <td><span class="source-note">{{ source.note || '等待来源状态' }}</span></td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card pad health-evidence-panel">
      <div class="section-title">
        <h2>当前风险证据</h2>
        <span class="muted">仅用于人工复核</span>
      </div>
      <div v-if="risks.length" class="table-scroll">
        <table class="table health-evidence-table">
          <thead>
            <tr>
              <th>等级</th>
              <th>筛查项</th>
              <th>分数</th>
              <th>证据</th>
              <th>复核建议</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="risk in risks" :key="risk.type">
              <td><SeverityPill :value="risk.level" /></td>
              <td><strong>{{ risk.label || healthRiskLabel(risk.type) }}</strong></td>
              <td>{{ percent(risk.score) }}</td>
              <td>
                <ul class="evidence-list">
                  <li v-for="item in risk.evidence || []" :key="item">{{ item }}</li>
                </ul>
              </td>
              <td>{{ risk.suggestion }}</td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="health-empty-state">
        <ShieldCheck :size="23" />
        <span>{{ noRiskMessage }}</span>
      </div>
    </section>

    <section class="health-boundary">
      <BadgeInfo :size="19" />
      <p>筛查结果需结合临床体温、采食记录和兽医检查确认。B-1 为体表温度，异常发声候选不是咳嗽或喘鸣诊断；口蹄疫分诊必须由兽医和法定实验室流程确认。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Activity,
  BadgeInfo,
  CircleDashed,
  DatabaseZap,
  Mic2,
  ScanSearch,
  ShieldAlert,
  ShieldCheck,
  Thermometer,
  Wheat
} from 'lucide-vue-next'
import SeverityPill from '../components/SeverityPill.vue'
import { useTelemetryStore } from '../stores/telemetry'
import { behaviorLabel, fixed, healthRiskLabel, percent } from '../utils/format'

const telemetry = useTelemetryStore()
const { latest } = storeToRefs(telemetry)

const waitingScreen = {
  version: 'disease-screen-v1',
  mode: 'WAITING_FOR_TELEMETRY',
  riskLevel: 'NORMAL',
  score: 0,
  dataQuality: 'INVALID',
  message: '等待 ESP32 行为与健康遥测数据',
  risks: [],
  current: {},
  baseline: {}
}

const screen = computed(() => latest.value?.healthScreen || waitingScreen)
const risks = computed(() => Array.isArray(screen.value?.risks) ? screen.value.risks : [])
const activeVisionEvidence = computed(() => Object.entries(screen.value?.vision?.activeEvents || {}))
const visionEvidenceText = computed(() => activeVisionEvidence.value.length
  ? activeVisionEvidence.value.map(([type]) => healthRiskLabel(type)).join('、')
  : '等待审核')
const scorePercent = computed(() => Math.round(Number(screen.value?.score || 0) * 100))
const baselineHours = computed(() => Number(screen.value?.baselineMinutes || 0) / 60)
const qualityClass = computed(() => String(screen.value?.dataQuality || 'INVALID').toLowerCase())
const sourceRows = computed(() => {
  const sources = screen.value?.sources || {}
  const definitions = [
    { key: 'motion', label: '运动 / 姿态', device: 'ESP32-S3 · 颈 / 背 / 腿' },
    { key: 'vision', label: '视觉', device: 'MaixCAM · 牛只事件' },
    { key: 'audio', label: '声音', device: 'INMP441 · ESP32-S3' },
    { key: 'surfaceTemperature', label: '体表温度', device: 'B-1 · UART' },
    { key: 'clinical', label: '临床复核', device: '人工记录 · 核心体温 / 检查' }
  ]
  return definitions.map((definition) => ({
    ...definition,
    ...(sources[definition.key] || {})
  }))
})
const fusionStateLabel = computed(() => {
  if (['WAITING_FOR_TELEMETRY', 'DATA_UNAVAILABLE'].includes(screen.value?.mode)) return '证据不足'
  const count = Number(screen.value?.fusion?.evidenceCount || 0)
  return count > 0 ? `${count} 项参与` : '待证据'
})
const fusionStateClass = computed(() => fusionStateLabel.value === '证据不足' ? 'fusion-limited' : 'fusion-ready')

const modeLabel = computed(() => ({
  SCREENING: '实时筛查中',
  BASELINE_LEARNING: '正在学习基线',
  DATA_UNAVAILABLE: '运动数据不足',
  WAITING_FOR_TELEMETRY: '等待遥测'
}[screen.value?.mode] || '状态未知'))

const qualityLabel = computed(() => ({
  GOOD: '数据完整',
  LIMITED: '数据有限',
  INVALID: '数据无效'
}[screen.value?.dataQuality] || '数据未知'))

const baselineState = computed(() => screen.value?.mode === 'SCREENING' ? '已启用' : '学习中')
const baselineLabel = computed(() => `${fixed(baselineHours.value, 1, ' h')} 基线`)
const riskHeadline = computed(() => {
  if (screen.value?.mode === 'BASELINE_LEARNING') return '个体基线学习中'
  if (screen.value?.mode === 'DATA_UNAVAILABLE') return '等待完整运动数据'
  if (screen.value?.mode === 'WAITING_FOR_TELEMETRY') return '等待健康遥测'
  return risks.value.length ? '发现待复核风险' : '未见持续异常'
})
const noRiskMessage = computed(() => screen.value?.mode === 'SCREENING'
  ? '当前窗口未发现相对个体基线的持续异常'
  : (screen.value?.message || '正在等待筛查条件满足'))
const b1Status = computed(() => latest.value?.b1Infrared?.temperatureValid ? '有效' : '等待')
const lamenessStatus = computed(() => {
  const lameness = latest.value?.lamenessScreen
  if (!lameness) return '等待'
  if (lameness.modelStatus === 'feature_only') return '特征采集'
  if (lameness.rejected) return '拒识'
  if (lameness.candidate) return '待视觉复核'
  return lameness.modelStatus === 'deployed' ? '未见候选' : lameness.modelStatus || '等待'
})
const microphoneStatus = computed(() => {
  const microphone = latest.value?.microphone
  if (!microphone?.initialized) return '离线'
  return microphone.status === 'ok' ? '有效' : '信号无效'
})

function onlineLabel(value) {
  return value === true ? '在线' : '无记录'
}

function freshLabel(source) {
  if (source.fresh === true) return '新鲜'
  return source.online === true ? '已过期' : '无数据'
}

function approvalLabel(source) {
  if (source.modelApprovalRequired !== true) {
    return source.key === 'clinical' ? '人工复核' : '不适用'
  }
  return source.modelApproved === true ? '服务端已批准' : '待批准'
}

function participationLabel(source) {
  if (source.participating === true) return '参与筛查'
  if (source.observed === true) return '已采集，未纳入'
  return '未参与'
}

function booleanClass(value) {
  return value === true ? 'source-good' : 'source-muted'
}

function participationClass(source) {
  if (source.participating === true) return 'source-good'
  if (source.observed === true) return 'source-warn'
  return 'source-muted'
}

function freshClass(source) {
  if (source.fresh === true) return 'source-good'
  return source.online === true ? 'source-warn' : 'source-muted'
}

function approvalClass(source) {
  if (source.modelApprovalRequired !== true) return 'source-neutral'
  return source.modelApproved === true ? 'source-good' : 'source-warn'
}

onMounted(() => {
  telemetry.loadSnapshot()
  telemetry.connect()
})
</script>

<style scoped>
.health-screen-page { min-width: 0; }

.health-live-strip {
  display: grid;
  grid-template-columns: minmax(240px, 1.35fr) repeat(3, minmax(150px, .72fr));
  align-items: center;
  min-height: 66px;
  border: 1px solid rgba(248, 242, 223, .16);
  border-left: 3px solid var(--green);
  background: rgba(12, 18, 14, .76);
}

.health-live-strip.quality-limited { border-left-color: var(--gold); }
.health-live-strip.quality-invalid { border-left-color: var(--red); }

.health-live-identity,
.health-live-stat {
  display: flex;
  align-items: center;
  min-width: 0;
  gap: 10px;
  padding: 12px 16px;
}

.health-live-stat {
  min-height: 40px;
  color: var(--muted);
  border-left: 1px solid var(--line);
}

.health-live-stat span {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.health-live-identity > div { display: grid; min-width: 0; }
.health-live-identity strong { font-size: 15px; }
.health-live-identity span:not(.health-live-dot) { color: var(--muted); font-size: 13px; }

.health-live-dot {
  flex: 0 0 auto;
  width: 9px;
  height: 9px;
  border-radius: 50%;
  background: var(--green);
  box-shadow: 0 0 0 6px rgba(142, 240, 160, .12);
}

.quality-limited .health-live-dot { background: var(--gold); box-shadow: 0 0 0 6px rgba(229, 184, 92, .12); }
.quality-invalid .health-live-dot { background: var(--red); box-shadow: 0 0 0 6px rgba(255, 110, 87, .12); }

.health-screen-summary {
  display: grid;
  grid-template-columns: minmax(390px, 1.08fr) minmax(360px, .92fr);
  gap: 18px;
}

.health-score-card { min-height: 330px; border-top: 3px solid var(--green); }
.health-score-card.severity-OBSERVE { border-top-color: var(--gold); }
.health-score-card.severity-WARNING { border-top-color: var(--red); }

.health-score-readout {
  display: grid;
  grid-template-columns: 58px minmax(0, 1fr) auto;
  align-items: center;
  gap: 14px;
  padding: 22px 0 16px;
}

.health-score-icon {
  display: grid;
  width: 56px;
  height: 56px;
  place-items: center;
  color: #071009;
  background: var(--green);
}

.severity-OBSERVE .health-score-icon { background: var(--gold); }
.severity-WARNING .health-score-icon { color: #fff; background: var(--red); }

.health-score-readout > div:nth-child(2) { display: grid; min-width: 0; gap: 4px; }
.health-score-readout > div:nth-child(2) strong { overflow-wrap: anywhere; font-family: "Noto Serif SC", serif; font-size: 28px; line-height: 1.2; }
.health-score-readout > div:nth-child(2) span { color: var(--muted); font-family: Consolas, monospace; font-size: 12px; }

.health-score-number { color: var(--green); font-size: 38px; font-weight: 900; font-variant-numeric: tabular-nums; }
.severity-OBSERVE .health-score-number { color: var(--gold); }
.severity-WARNING .health-score-number { color: var(--red); }
.health-score-number small { font-size: 16px; }

.health-score-track { overflow: hidden; height: 7px; background: rgba(248, 242, 223, .11); }
.health-score-track span { display: block; min-width: 0; height: 100%; background: linear-gradient(90deg, var(--green), var(--gold)); transition: width .35s ease; }
.severity-WARNING .health-score-track span { background: linear-gradient(90deg, var(--gold), var(--red)); }

.health-screen-message { min-height: 42px; margin: 15px 0 0; color: var(--muted); line-height: 1.55; }

.screen-detail-grid,
.baseline-trend-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 1px;
  margin-top: 14px;
  border: 1px solid var(--line);
  background: var(--line);
}

.screen-detail-grid > div,
.baseline-trend-grid > div { min-width: 0; padding: 10px; background: #111813; }
.screen-detail-grid span,
.screen-detail-grid strong,
.baseline-trend-grid span,
.baseline-trend-grid strong { display: block; }
.screen-detail-grid span,
.baseline-trend-grid span { color: var(--muted); font-size: 11px; }
.screen-detail-grid strong,
.baseline-trend-grid strong { margin-top: 4px; overflow-wrap: anywhere; font-size: 16px; font-variant-numeric: tabular-nums; }

.baseline-card { min-height: 330px; }
.baseline-chip { padding: 5px 8px; color: var(--green); border: 1px solid rgba(142, 240, 160, .24); background: rgba(142, 240, 160, .08); font-size: 12px; font-weight: 800; }

.baseline-readout { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 12px; margin-top: 23px; }
.baseline-readout > div { display: grid; min-width: 0; gap: 5px; padding-bottom: 12px; border-bottom: 1px solid var(--line); }
.baseline-readout span { color: var(--muted); font-size: 12px; }
.baseline-readout strong { overflow-wrap: anywhere; font-size: 21px; font-variant-numeric: tabular-nums; }
.baseline-note { margin: 13px 0 0; color: var(--muted); font-size: 12px; line-height: 1.5; }

.health-signal-grid { display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }
.health-signal-card { min-width: 0; min-height: 168px; }
.health-signal-head { display: flex; align-items: center; gap: 9px; color: var(--muted); font-size: 13px; font-weight: 800; }
.health-signal-icon { display: grid; width: 36px; height: 36px; place-items: center; color: var(--green); border: 1px solid rgba(142, 240, 160, .24); background: rgba(142, 240, 160, .08); }
.signal-motion { color: var(--blue); border-color: rgba(124, 183, 255, .28); background: rgba(124, 183, 255, .08); }
.signal-temperature { color: var(--red); border-color: rgba(255, 110, 87, .28); background: rgba(255, 110, 87, .08); }
.signal-audio { color: var(--gold); border-color: rgba(229, 184, 92, .28); background: rgba(229, 184, 92, .08); }
.signal-vision { color: #b89cff; border-color: rgba(184, 156, 255, .28); background: rgba(184, 156, 255, .08); }
.health-signal-card > strong { display: block; min-height: 31px; margin: 16px 0 12px; overflow-wrap: anywhere; font-family: "Noto Serif SC", serif; font-size: 21px; }
.signal-pair { display: flex; justify-content: space-between; gap: 8px; padding-top: 7px; color: var(--muted); border-top: 1px solid var(--line); font-size: 12px; }
.signal-pair + .signal-pair { margin-top: 7px; }
.signal-pair b { color: var(--text); font-variant-numeric: tabular-nums; }

.health-evidence-panel { min-width: 0; }
.health-source-panel { min-width: 0; }
.health-source-title { align-items: center; }
.health-source-title > div { display: grid; gap: 3px; min-width: 0; }
.fusion-chip { flex: 0 0 auto; padding: 5px 8px; border: 1px solid rgba(229, 184, 92, .3); background: rgba(229, 184, 92, .08); color: var(--gold); font-size: 12px; font-weight: 800; }
.fusion-chip.fusion-ready { border-color: rgba(142, 240, 160, .3); background: rgba(142, 240, 160, .08); color: var(--green); }
.health-source-table { min-width: 940px; }
.health-source-table td { vertical-align: middle; }
.health-source-table td:first-child { min-width: 180px; }
.health-source-table strong,
.health-source-table small { display: block; }
.health-source-table small { margin-top: 4px; color: var(--muted); font-size: 11px; }
.source-status { display: inline-flex; width: max-content; padding: 4px 7px; border: 1px solid rgba(248, 242, 223, .14); background: rgba(248, 242, 223, .05); color: var(--muted); font-size: 12px; white-space: nowrap; }
.source-status.source-good { border-color: rgba(142, 240, 160, .28); background: rgba(142, 240, 160, .08); color: var(--green); }
.source-status.source-warn { border-color: rgba(229, 184, 92, .3); background: rgba(229, 184, 92, .08); color: var(--gold); }
.source-status.source-neutral { border-color: rgba(124, 183, 255, .24); background: rgba(124, 183, 255, .07); color: var(--blue); }
.source-note { display: block; min-width: 220px; max-width: 430px; color: var(--muted); line-height: 1.45; }
.health-evidence-table { min-width: 920px; }
.evidence-list { display: grid; gap: 4px; margin: 0; padding-left: 17px; color: var(--muted); }
.health-empty-state { display: flex; align-items: center; gap: 10px; min-height: 115px; color: var(--muted); border: 1px dashed var(--line); padding: 16px; }
.health-empty-state svg { color: var(--green); }

.health-boundary { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; color: #d5ddd7; border-left: 3px solid var(--gold); background: rgba(229, 184, 92, .08); }
.health-boundary svg { flex: 0 0 auto; margin-top: 2px; color: var(--gold); }
.health-boundary p { margin: 0; line-height: 1.55; }

@media (max-width: 1180px) {
  .health-live-strip { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .health-live-stat:nth-child(3) { border-top: 1px solid var(--line); border-left: 0; }
  .health-live-stat:nth-child(4) { border-top: 1px solid var(--line); }
  .health-screen-summary { grid-template-columns: 1fr; }
  .health-signal-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}

@media (max-width: 680px) {
  .health-live-strip,
  .health-signal-grid { grid-template-columns: 1fr; }
  .health-live-stat { border-top: 1px solid var(--line); border-left: 0; }
  .health-score-readout { grid-template-columns: 48px minmax(0, 1fr); }
  .health-score-icon { width: 46px; height: 46px; }
  .health-score-readout > div:nth-child(2) strong { font-size: 23px; }
  .health-score-number { grid-column: 1 / -1; font-size: 32px; }
  .screen-detail-grid,
  .baseline-trend-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .baseline-readout { grid-template-columns: 1fr; gap: 8px; }
}
</style>
