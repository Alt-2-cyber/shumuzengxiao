<template>
  <div class="behavior-page grid page-stack">
    <section class="telemetry-livebar" :class="{ 'is-live': isLive, 'is-offline': !isLive }">
      <div class="live-identity">
        <span class="live-dot"></span>
        <div>
          <strong>{{ liveLabel }}</strong>
          <span>{{ latest?.deviceId || '等待 ESP32 节点' }}</span>
        </div>
      </div>
      <div class="live-stat">
        <Radio :size="17" />
        <span>{{ telemetry.port }} · {{ telemetry.baudRate }}</span>
      </div>
      <div class="live-stat">
        <Clock3 :size="17" />
        <span>{{ ageLabel }}</span>
      </div>
      <div class="live-stat">
        <DatabaseZap :size="17" />
        <span>{{ telemetry.history.length }} 条缓存</span>
      </div>
    </section>

    <div v-if="telemetry.error" class="error-banner">{{ telemetry.error }}</div>
    <div v-if="missingSensorCount" class="motion-warning">
      <TriangleAlert :size="18" />
      <span>三位置运动链路有 {{ missingSensorCount }} 个节点离线，当前行为结果不可用于健康判断。</span>
    </div>

    <section class="behavior-overview">
      <article class="card pad behavior-focus" :class="`state-${behaviorState}`">
        <div class="section-title">
          <h2>当前行为</h2>
          <span class="model-chip"><Cpu :size="15" /> {{ behavior.model || '模型等待中' }}</span>
        </div>
        <div class="behavior-readout">
          <div class="behavior-symbol">
            <Footprints v-if="behaviorState === 'walking'" :size="32" />
            <Wheat v-else-if="behaviorState === 'grazing'" :size="32" />
            <Activity v-else :size="32" />
          </div>
          <div>
            <strong>{{ behaviorLabel(behaviorState) }}</strong>
            <span>颈部模型：{{ behaviorLabel(behavior.neckModelState) }}</span>
          </div>
          <div class="confidence-number">{{ confidencePercent }}<small>%</small></div>
        </div>
        <div class="confidence-track" aria-label="行为识别置信度">
          <span :style="{ width: `${confidencePercent}%` }"></span>
        </div>
        <div class="evidence-grid">
          <div>
            <span>窗口样本</span>
            <strong>{{ behavior.windowSamples ?? '-' }}</strong>
          </div>
          <div>
            <span>背部倾角</span>
            <strong>{{ fixed(behavior.bodyTiltDeg, 1, '°') }}</strong>
          </div>
          <div>
            <span>腿部活动</span>
            <strong>{{ fixed(behavior.legActivity, 2) }}</strong>
          </div>
          <div>
            <span>颈部置信度</span>
            <strong>{{ percent(behavior.neckModelConfidence) }}</strong>
          </div>
        </div>
        <div class="model-footline">
          <span>{{ behavior.fusion || 'neck_ml+body_tilt+leg_activity' }}</span>
          <span>序号 {{ latest?.seq ?? '-' }}</span>
        </div>
      </article>

      <article class="card pad motion-chart-panel">
        <div class="section-title">
          <h2>三位置活动趋势</h2>
          <span class="muted">最近 {{ chartRows.length }} 个窗口</span>
        </div>
        <MotionTrendChart :rows="chartRows" />
      </article>
    </section>

    <section>
      <div class="section-title behavior-section-heading">
        <h2>牛体运动节点</h2>
        <span class="muted">在线 {{ onlineSensorCount }}/3</span>
      </div>
      <div class="position-sensor-grid">
        <article
          v-for="sensor in sensors"
          :key="sensor.id"
          class="card pad position-sensor-card"
          :class="[`sensor-${sensor.id}`, { 'is-unavailable': !sensor.online }]"
        >
          <div class="position-head">
            <div class="position-icon"><component :is="sensor.icon" :size="21" /></div>
            <div>
              <strong>{{ sensor.name }}</strong>
              <span>{{ sensor.hardware }}</span>
            </div>
            <span class="sensor-status"><i></i>{{ sensor.online ? '在线' : '离线' }}</span>
          </div>
          <div class="axis-section">
            <span class="axis-title">加速度 m/s²</span>
            <div class="axis-grid">
              <div v-for="axis in accelerationAxes" :key="axis.key">
                <span>{{ axis.label }}</span>
                <strong>{{ fixed(sensor.reading?.[axis.key], 2) }}</strong>
              </div>
            </div>
          </div>
          <div class="axis-section" :class="{ 'is-muted': !sensor.hasGyro }">
            <span class="axis-title">{{ sensor.hasGyro ? '角速度 °/s' : '角速度' }}</span>
            <div v-if="sensor.hasGyro" class="axis-grid">
              <div v-for="axis in gyroAxes" :key="axis.key">
                <span>{{ axis.label }}</span>
                <strong>{{ fixed(sensor.reading?.[axis.key], 1) }}</strong>
              </div>
            </div>
            <span v-else class="sensor-capability">ADXL345 仅采集三轴加速度</span>
          </div>
        </article>
      </div>
    </section>

    <section class="telemetry-detail-grid">
      <article class="card pad telemetry-detail">
        <div class="detail-icon climate"><Thermometer :size="21" /></div>
        <div>
          <span>牛舍温湿度</span>
          <strong>{{ fixed(latest?.temperature, 1, '℃') }} / {{ fixed(latest?.humidity, 1, '%') }}</strong>
          <small>{{ latest?.climateSource || '-' }}</small>
        </div>
      </article>
      <article class="card pad telemetry-detail">
        <div class="detail-icon pulse"><HeartPulse :size="21" /></div>
        <div>
          <span>心率与血氧</span>
          <strong>{{ fixed(latest?.heartRate, 0, ' bpm') }} / {{ fixed(latest?.spo2, 0, '%') }}</strong>
          <small>{{ latest?.maxStatus || '-' }}</small>
        </div>
      </article>
      <article class="card pad telemetry-detail">
        <div class="detail-icon audio"><Mic2 :size="21" /></div>
        <div>
          <span>声音状态</span>
          <strong>{{ fixed(latest?.microphone?.dbfs, 1, ' dBFS') }}</strong>
          <small>{{ latest?.microphone?.vocalizationCandidate ? '疑似牛叫' : (latest?.microphone?.status || '-') }}</small>
        </div>
      </article>
      <article class="card pad telemetry-detail">
        <div class="detail-icon infrared"><ScanLine :size="21" /></div>
        <div>
          <span>红外表面温度</span>
          <strong>{{ b1Temperature }}</strong>
          <small>{{ latest?.b1Infrared?.status || '-' }}</small>
        </div>
      </article>
      <article class="card pad telemetry-detail">
        <div class="detail-icon light"><Sun :size="21" /></div>
        <div>
          <span>光照与空气趋势</span>
          <strong>{{ fixed(latest?.lightLux, 0, ' lx') }} / MQ {{ latest?.mqRaw ?? '-' }}</strong>
          <small>{{ latest?.level || '-' }}</small>
        </div>
      </article>
      <article class="card pad telemetry-detail">
        <div class="detail-icon safety"><Flame :size="21" /></div>
        <div>
          <span>安全与执行器</span>
          <strong>{{ latest?.flame ? '检测到火焰' : '无火焰' }} / 风扇{{ latest?.fan ? '开' : '关' }}</strong>
          <small>{{ latest?.fanMode || 'auto' }}</small>
        </div>
      </article>
    </section>

    <section class="card pad behavior-history-panel">
      <div class="section-title">
        <h2>实时识别记录</h2>
        <span class="muted">最新 12 条</span>
      </div>
      <div class="table-scroll">
        <table class="table behavior-table">
          <thead>
            <tr>
              <th>接收时间</th>
              <th>行为</th>
              <th>置信度</th>
              <th>颈部</th>
              <th>背部</th>
              <th>腿部</th>
              <th>传感器</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="row in recentRows" :key="`${row.deviceId}-${row.seq}-${row.receivedAt}`">
              <td>{{ formatClock(row.receivedAt) }}</td>
              <td><strong>{{ behaviorLabel(row.behavior?.state) }}</strong></td>
              <td>{{ percent(row.behavior?.confidence) }}</td>
              <td>{{ fixed(row.behavior?.neckActivity, 2) }}</td>
              <td>{{ fixed(row.behavior?.bodyActivity, 2) }}</td>
              <td>{{ fixed(row.behavior?.legActivity, 2) }}</td>
              <td>{{ Number(Boolean(row.mpu0)) + Number(Boolean(row.adxl345)) + Number(Boolean(row.mpu1)) }}/3</td>
            </tr>
            <tr v-if="recentRows.length === 0">
              <td colspan="7" class="muted">等待牛身节点遥测数据</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import {
  Activity,
  Clock3,
  Cpu,
  DatabaseZap,
  Flame,
  Footprints,
  Gauge,
  HeartPulse,
  Mic2,
  Move3d,
  Radio,
  ScanLine,
  Sun,
  Thermometer,
  TriangleAlert,
  Wheat
} from 'lucide-vue-next'
import MotionTrendChart from '../components/MotionTrendChart.vue'
import { useTelemetryStore } from '../stores/telemetry'
import { behaviorLabel, fixed, percent } from '../utils/format'

const telemetry = useTelemetryStore()
const { latest, history } = storeToRefs(telemetry)
const now = ref(Date.now())
let clockTimer

const accelerationAxes = [
  { key: 'ax', label: 'X' },
  { key: 'ay', label: 'Y' },
  { key: 'az', label: 'Z' }
]
const gyroAxes = [
  { key: 'gx', label: 'X' },
  { key: 'gy', label: 'Y' },
  { key: 'gz', label: 'Z' }
]

const behavior = computed(() => latest.value?.behavior || {})
const behaviorState = computed(() => behavior.value.state || 'waiting')
const confidencePercent = computed(() => Math.round(Number(behavior.value.confidence || 0) * 100))
const dataAgeMs = computed(() => {
  const timestamp = new Date(telemetry.lastReceivedAt || latest.value?.receivedAt || 0).getTime()
  return timestamp ? Math.max(0, now.value - timestamp) : Number.POSITIVE_INFINITY
})
const edgeConnected = computed(() => telemetry.serialConnected || telemetry.networkConnected)
const isLive = computed(() => telemetry.websocketConnected && edgeConnected.value && dataAgeMs.value < 7000)
const liveLabel = computed(() => {
  if (!telemetry.websocketConnected) return '网页实时通道重连中'
  if (!edgeConnected.value) return 'ESP32 实时链路离线'
  if (dataAgeMs.value >= 7000) return '数据已停止更新'
  return '实时数据流'
})
const ageLabel = computed(() => {
  if (!Number.isFinite(dataAgeMs.value)) return '尚未收到数据'
  const seconds = Math.floor(dataAgeMs.value / 1000)
  if (seconds < 2) return '刚刚更新'
  if (seconds < 60) return `${seconds} 秒前更新`
  return `${Math.floor(seconds / 60)} 分钟前更新`
})

const sensors = computed(() => [
  {
    id: 'neck',
    name: '颈部节点',
    hardware: 'MPU-9250/6500 · 0x68',
    online: Boolean(latest.value?.mpu0),
    reading: latest.value?.mpu0Data,
    hasGyro: true,
    icon: Activity
  },
  {
    id: 'body',
    name: '背部节点',
    hardware: 'ADXL345 · 0x53',
    online: Boolean(latest.value?.adxl345),
    reading: latest.value?.adxl,
    hasGyro: false,
    icon: Move3d
  },
  {
    id: 'leg',
    name: '腿部节点',
    hardware: 'MPU-9250/6500 · 0x69',
    online: Boolean(latest.value?.mpu1),
    reading: latest.value?.mpu1Data,
    hasGyro: true,
    icon: Gauge
  }
])
const onlineSensorCount = computed(() => sensors.value.filter((sensor) => sensor.online).length)
const missingSensorCount = computed(() => latest.value ? 3 - onlineSensorCount.value : 0)
const chartRows = computed(() => history.value.filter((row) => row?.behavior))
const recentRows = computed(() => [...chartRows.value].reverse().slice(0, 12))
const b1Temperature = computed(() => {
  const b1 = latest.value?.b1Infrared
  return b1?.temperatureValid ? fixed(b1.surfaceTemperature, 1, '℃') : '-'
})

function formatClock(value) {
  if (!value) return '-'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleTimeString('zh-CN', { hour12: false })
}

onMounted(() => {
  telemetry.loadSnapshot()
  telemetry.connect()
  clockTimer = window.setInterval(() => { now.value = Date.now() }, 1000)
})

onBeforeUnmount(() => {
  window.clearInterval(clockTimer)
})
</script>
