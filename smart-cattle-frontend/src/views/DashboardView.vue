<template>
  <div class="grid page-stack">
    <section class="grid cols-4">
      <article class="metric-card card">
        <div class="metric-label">当前牛只</div>
        <div class="metric-value metric-value-id">{{ cattleId }}</div>
        <div class="metric-foot">实时遥测对应的个体标识</div>
      </article>
      <article class="metric-card card">
        <div class="metric-label">三位置运动</div>
        <div class="metric-value">{{ motionNodeCount }}/3</div>
        <div class="metric-foot">颈部 / 背部 / 腿部传感器在线</div>
      </article>
      <article class="metric-card card">
        <div class="metric-label">健康筛查</div>
        <div class="metric-value" :class="{ danger: screen.riskLevel === 'WARNING' }">{{ screeningHeadline }}</div>
        <div class="metric-foot">{{ screen.version || 'health-screen-v1' }}，仅供人工复核</div>
      </article>
      <article class="metric-card card">
        <div class="metric-label">实时链路</div>
        <div class="metric-value">{{ telemetry.port }}</div>
        <div class="metric-foot">{{ telemetry.dataFresh && telemetry.networkConnected ? 'ESP32 WiFi 数据持续接收' : telemetry.dataFresh && telemetry.serialConnected ? 'ESP32 串口数据持续接收' : telemetry.serialConnected || telemetry.networkConnected ? '链路已打开，等待 ESP32 数据' : '等待 ESP32 数据' }}</div>
      </article>
    </section>

    <section class="grid cols-2 dashboard-main">
        <article class="card pad">
          <div class="section-title">
            <h2>牛舍 3D 态势</h2>
            <span class="muted">仅映射当前实时筛查证据</span>
          </div>
          <BarnScene :risks="liveRisks" />
        </article>

      <div class="grid">
        <article class="card pad">
          <div class="section-title">
            <h2>当前环境</h2>
            <SeverityPill :value="environmentSeverity" />
          </div>
          <div class="sensor-grid">
            <div class="sensor-tile">
              <span>温度</span>
              <strong>{{ fixed(environmentLatest?.temperature, 1, '℃') }}</strong>
            </div>
            <div class="sensor-tile">
              <span>湿度</span>
              <strong>{{ fixed(environmentLatest?.humidity, 1, '%') }}</strong>
            </div>
            <div class="sensor-tile">
              <span>氨气</span>
              <strong>{{ fixed(environmentLatest?.ammonia, 1, 'ppm') }}</strong>
            </div>
            <div class="sensor-tile">
              <span>火焰/烟雾</span>
              <strong>{{ environmentLatest ? (environmentFireState ? '异常' : '正常') : '--' }}</strong>
            </div>
          </div>
        </article>

        <article class="card pad">
          <div class="section-title">
            <h2>风险队列</h2>
            <span class="muted">{{ liveRisks.length }} 条实时证据</span>
          </div>
          <div v-if="liveRisks.length" class="event-list">
            <div v-for="risk in liveRisks" :key="risk.type" class="event-row">
              <div>
                <strong>{{ risk.label || healthRiskLabel(risk.type) }}</strong>
                <p>{{ evidenceText(risk.evidence) }}</p>
              </div>
              <SeverityPill :value="risk.level" />
            </div>
          </div>
          <div v-else class="dashboard-empty-state">{{ screen.message || '等待实时健康筛查数据' }}</div>
        </article>
      </div>
    </section>

    <section class="grid cols-2">
        <article class="card pad">
          <div class="section-title">
            <h2>实时环境趋势</h2>
            <span class="muted">最近 {{ liveTrendRows.length }} 帧</span>
          </div>
          <TrendChart
            v-if="liveTrendRows.length"
            :rows="liveTrendRows"
            third-key="smoke"
            third-label="烟雾百分比"
          />
          <div v-else class="dashboard-empty-state">等待 ESP32 实时环境数据</div>
        </article>

        <article class="card pad">
          <div class="section-title">
            <h2>实时数据状态</h2>
            <span class="muted">不使用历史演示记录</span>
          </div>
          <table class="table">
            <thead>
              <tr>
                <th>级别</th>
                <th>模块</th>
                <th>状态</th>
                <th>说明</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="check in liveChecks" :key="check.title">
                <td><SeverityPill :value="check.level" /></td>
                <td>{{ check.title }}</td>
                <td>{{ check.status }}</td>
                <td>{{ check.detail }}</td>
              </tr>
            </tbody>
          </table>
        </article>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import BarnScene from '../components/BarnScene.vue'
import SeverityPill from '../components/SeverityPill.vue'
import TrendChart from '../components/TrendChart.vue'
import { useTelemetryStore } from '../stores/telemetry'
import { useDashboardStore } from '../stores/dashboard'
import { fixed, healthRiskLabel } from '../utils/format'

const telemetry = useTelemetryStore()
const { latest, latestEnvironment: liveEnvironmentLatest, environmentHistory } = storeToRefs(telemetry)
const dashboard = useDashboardStore()
const { data: dashboardData } = storeToRefs(dashboard)

const waitingScreen = {
  version: 'health-screen-v1',
  mode: 'WAITING_FOR_TELEMETRY',
  riskLevel: 'NORMAL',
  message: '等待 ESP32 行为与健康遥测数据',
  risks: []
}

const screen = computed(() => latest.value?.healthScreen || waitingScreen)
const cattleId = computed(() => latest.value?.cattleId || latest.value?.deviceId || '等待节点')
const motionNodeCount = computed(() => [latest.value?.mpu0, latest.value?.adxl345, latest.value?.mpu1]
  .filter(Boolean).length)
const liveRisks = computed(() => Array.isArray(screen.value?.risks) ? screen.value.risks : [])
function rowTime(row) {
  return new Date(row?.recordedAt || row?.receivedAt || 0).getTime()
}

function mergeEnvironmentRows(persisted, live) {
  const unique = new Map()
  for (const row of [...persisted, ...live]) {
    if (!row) continue
    unique.set(`${row.deviceId || 'env'}:${rowTime(row)}`, row)
  }
  return [...unique.values()].sort((a, b) => rowTime(a) - rowTime(b)).slice(-48)
}

const environmentLatest = computed(() => {
  const persisted = dashboardData.value?.latestEnvironment
  const live = liveEnvironmentLatest.value
  return [persisted, live].filter(Boolean).sort((a, b) => rowTime(a) - rowTime(b)).at(-1) || null
})
const environmentFireState = computed(() => Boolean(
  environmentLatest.value?.flame || Number(environmentLatest.value?.smoke) >= 60
))
const liveTrendRows = computed(() => mergeEnvironmentRows(
  dashboardData.value?.environmentTrend || [],
  environmentHistory.value
))
const screeningHeadline = computed(() => ({
  WAITING_FOR_TELEMETRY: '等待数据',
  DATA_UNAVAILABLE: '数据不足',
  BASELINE_LEARNING: '学习中',
  SCREENING: liveRisks.value.length ? '待复核' : '无异常'
}[screen.value?.mode] || '未知'))
const environmentSeverity = computed(() => {
  if (!environmentLatest.value) return 'NORMAL'
  if (environmentFireState.value) return 'WARNING'
  if (environmentLatest.value.temperature >= 30 || environmentLatest.value.humidity >= 80 || environmentLatest.value.ammonia >= 25) return 'OBSERVE'
  return 'NORMAL'
})
const liveChecks = computed(() => {
  const b1 = latest.value?.b1Infrared
  const microphone = latest.value?.microphone
  const motionDetail = motionNodeCount.value === 3
    ? '颈部、背部、腿部运动节点均在线'
    : '缺失节点时不生成健康风险筛查结果'
  const b1Valid = Boolean(b1?.temperatureValid)
  const microphoneValid = microphone?.status === 'ok'
  return [
    {
      level: motionNodeCount.value === 3 ? 'NORMAL' : 'OBSERVE',
      title: '三位置运动',
      status: `${motionNodeCount.value}/3 在线`,
      detail: motionDetail
    },
    {
      level: b1Valid ? 'NORMAL' : 'OBSERVE',
      title: 'B-1 体表温度',
      status: b1Valid ? '数据有效' : (b1?.status || '等待上报'),
      detail: b1Valid ? `${fixed(b1.surfaceTemperature, 1, '℃')}，需用临床体温复核` : '无有效温度帧时不参与温度筛查'
    },
    {
      level: microphoneValid ? 'NORMAL' : 'OBSERVE',
      title: 'INMP441 麦克风',
      status: microphoneValid ? '信号有效' : (microphone?.status || '等待上报'),
      detail: microphoneValid ? '仅输出异常发声候选，不判定咳嗽或喘鸣' : '无效信号不参与声音筛查'
    },
    {
      level: screen.value?.riskLevel || 'NORMAL',
      title: '健康筛查',
      status: screeningHeadline.value,
      detail: screen.value?.message || '等待个体基线学习'
    }
  ]
})

function evidenceText(evidence) {
  return Array.isArray(evidence) ? evidence.join('；') : (evidence || '-')
}

onMounted(() => {
  telemetry.loadSnapshot()
  telemetry.connect()
  dashboard.startPolling()
})

onBeforeUnmount(() => dashboard.stopPolling())
</script>
