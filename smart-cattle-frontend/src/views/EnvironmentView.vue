<template>
  <div class="grid page-stack">
    <section class="grid cols-4">
      <article v-for="metric in metrics" :key="metric.label" class="metric-card card">
        <div class="metric-label">{{ metric.label }}</div>
        <div class="metric-value" :class="{ danger: metric.danger }">{{ metric.value }}</div>
        <div class="metric-foot">{{ metric.foot }}</div>
      </article>
    </section>

    <section class="grid cols-2">
      <article class="card pad">
        <div class="section-title">
          <h2>环境曲线</h2>
          <span class="muted">最近 48 小时</span>
        </div>
        <TrendChart :rows="rows" />
      </article>

      <article class="card pad">
        <div class="section-title">
          <h2>联动状态</h2>
          <span class="muted">ESP32-S3 本地规则</span>
        </div>
        <div class="control-state-grid">
          <div class="control-state" :class="{ active: latest?.fanOn }">
            <Wind :size="22" />
            <div>
              <strong>风扇</strong>
              <span>{{ latest?.fanOn ? '已开启' : '关闭' }}</span>
            </div>
          </div>
          <div class="control-state" :class="{ active: latest?.atomizerOn }">
            <Droplets :size="22" />
            <div>
              <strong>雾化器</strong>
              <span>{{ latest?.atomizerOn ? '已开启' : '关闭' }}</span>
            </div>
          </div>
          <div class="control-state" :class="{ active: latest?.ammonia >= 22 }">
            <Siren :size="22" />
            <div>
              <strong>氨气规则</strong>
              <span>{{ latest?.ammonia >= 22 ? '触发通风' : '未触发' }}</span>
            </div>
          </div>
          <div class="control-state" :class="{ active: fireActive }">
            <Flame :size="22" />
            <div>
              <strong>火焰/烟雾</strong>
              <span>{{ fireActive ? '异常' : '正常' }}</span>
            </div>
          </div>
        </div>
      </article>
    </section>

    <section class="card pad">
      <div class="section-title">
        <h2>采集明细</h2>
        <span class="muted">设备 {{ latest?.deviceId || '-' }}</span>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>时间</th>
            <th>温度</th>
            <th>湿度</th>
            <th>氨气</th>
            <th>NH3原始</th>
            <th>光照</th>
            <th>烟雾</th>
            <th>烟雾原始</th>
            <th>火焰</th>
            <th>风扇</th>
            <th>风扇模式</th>
            <th>雾化</th>
            <th>信号</th>
          </tr>
        </thead>
        <tbody>
            <tr v-for="row in latestRows" :key="`${row.deviceId || 'env'}-${row.id || row.seq || row.recordedAt}`">
            <td>{{ formatFullTime(row.recordedAt) }}</td>
            <td>{{ fixed(row.temperature, 1, '℃') }}</td>
            <td>{{ fixed(row.humidity, 1, '%') }}</td>
            <td>{{ fixed(row.ammonia, 1, 'ppm') }}</td>
            <td>{{ row.nh3Raw ?? '-' }}</td>
            <td>{{ fixed(row.lightLux, 0, 'lx') }}</td>
            <td>{{ fixed(row.smoke, 1, '%') }}</td>
            <td>{{ row.smokeRaw ?? '-' }}</td>
            <td>{{ row.flame ? '是' : '否' }}</td>
            <td>{{ row.fanOn ? '开' : '关' }}</td>
            <td>{{ row.fanMode || '-' }}</td>
            <td>{{ row.atomizerOn ? '开' : '关' }}</td>
            <td>{{ row.rssi ?? '-' }} dBm</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import { Droplets, Flame, Siren, Wind } from 'lucide-vue-next'
import TrendChart from '../components/TrendChart.vue'
import { useDashboardStore } from '../stores/dashboard'
import { useTelemetryStore } from '../stores/telemetry'
import { fixed, formatFullTime } from '../utils/format'

const store = useDashboardStore()
const { data } = storeToRefs(store)
const telemetry = useTelemetryStore()
const { latestEnvironment: liveEnvironmentLatest, environmentHistory } = storeToRefs(telemetry)

function rowTime(row) {
  return new Date(row?.recordedAt || row?.receivedAt || 0).getTime()
}

const rows = computed(() => {
  const unique = new Map()
  for (const row of [...(data.value?.environmentTrend || []), ...environmentHistory.value]) {
    if (row) unique.set(`${row.deviceId || 'env'}:${rowTime(row)}`, row)
  }
  return [...unique.values()].sort((a, b) => rowTime(a) - rowTime(b)).slice(-48)
})
const latest = computed(() => {
  const persisted = data.value?.latestEnvironment
  const live = liveEnvironmentLatest.value
  return [persisted, live].filter(Boolean).sort((a, b) => rowTime(a) - rowTime(b)).at(-1) || null
})
const latestRows = computed(() => [...rows.value].reverse().slice(0, 16))
const fireActive = computed(() => Boolean(latest.value?.flame || Number(latest.value?.smoke) >= 60))
const metrics = computed(() => [
  {
    label: '温度',
    value: fixed(latest.value?.temperature, 1, '℃'),
    foot: '建议 10-30℃，过高联动降温',
    danger: latest.value?.temperature >= 30
  },
  {
    label: '湿度',
    value: fixed(latest.value?.humidity, 1, '%'),
    foot: '建议 50-75%，过高增加呼吸道风险',
    danger: latest.value?.humidity >= 80
  },
  {
    label: '氨气',
    value: fixed(latest.value?.ammonia, 1, 'ppm'),
    foot: '超过 20ppm 自动通风',
    danger: latest.value?.ammonia >= 25
  },
  {
    label: '光照',
    value: fixed(latest.value?.lightLux, 0, 'lx'),
    foot: '用于昼夜节律与补光判断',
    danger: false
  }
])

onMounted(() => {
  store.startPolling()
})

onBeforeUnmount(() => store.stopPolling())
</script>
