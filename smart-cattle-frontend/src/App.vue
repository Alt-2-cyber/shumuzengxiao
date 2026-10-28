<template>
  <div class="app-shell" :key="route.fullPath">
    <aside class="sidebar">
      <div class="brand-block">
        <div class="brand-mark">牧</div>
        <div>
          <div class="brand-name">数牧增效</div>
          <div class="brand-subtitle">Smart Cattle OS</div>
        </div>
      </div>

      <nav class="nav-list">
        <RouterLink v-for="item in navItems" :key="item.path" :to="item.path" class="nav-item">
          <component :is="item.icon" :size="18" />
          <span>{{ item.label }}</span>
        </RouterLink>
      </nav>

      <div class="edge-card">
      <div class="edge-card-title">边缘状态</div>
      <div class="edge-row">
        <span>ESP32 · {{ telemetry.port }}</span>
        <strong :class="edgeConnected ? 'edge-online' : 'edge-offline'">
          {{ edgeStatusLabel }}
        </strong>
        </div>
        <div class="edge-row"><span>行为模型</span><strong>{{ behaviorLabel(telemetry.latest?.behavior?.state) }}</strong></div>
        <div class="edge-row"><span>MaixCam</span><strong>{{ maixCamStatus }}</strong></div>
        <div class="edge-row"><span>WebSocket</span><strong>{{ telemetry.websocketConnected ? '已连接' : '重连中' }}</strong></div>
      </div>
    </aside>

    <main class="main-panel">
      <header class="topbar">
        <div>
          <p class="eyebrow">农户普惠型肉牛养殖监测专家</p>
          <h1>{{ routeTitle }}</h1>
        </div>
        <div class="topbar-actions">
          <button class="icon-button" title="刷新数据" @click="reload">
            <RefreshCcw :size="18" />
          </button>
          <div class="operator-badge">天津试点牛舍 01</div>
        </div>
      </header>

      <div v-if="dashboard.error" class="error-banner">{{ dashboard.error }}</div>
      <div v-if="dashboard.loading && !dashboard.data" class="loading-panel">正在加载牛舍监测数据...</div>
      <RouterView v-else v-slot="{ Component }">
        <Transition name="route-fade" mode="out-in">
          <component :is="Component" :key="route.fullPath" />
        </Transition>
      </RouterView>
    </main>
  </div>
</template>

<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, watch } from 'vue'
import { RouterLink, RouterView, useRoute } from 'vue-router'
import { Activity, AudioLines, BrainCircuit, Camera, Gauge, HeartPulse, LayoutDashboard, RefreshCcw, Router, Sparkles } from 'lucide-vue-next'
import { useDashboardStore } from './stores/dashboard'
import { useTelemetryStore } from './stores/telemetry'
import { behaviorLabel } from './utils/format'
import { runPremiumEffects } from './effects/premiumEffects'

const route = useRoute()
const dashboard = useDashboardStore()
const telemetry = useTelemetryStore()

const navItems = [
  { path: '/', label: '项目介绍', icon: Sparkles },
  { path: '/dashboard', label: '总览驾驶舱', icon: LayoutDashboard },
  { path: '/environment', label: '环境监测', icon: Gauge },
  { path: '/health', label: '健康风险', icon: HeartPulse },
  { path: '/vision', label: '视觉证据', icon: Camera },
  { path: '/audio', label: '声音筛查', icon: AudioLines },
  { path: '/behavior', label: '牛体行为', icon: Activity },
  { path: '/devices', label: '设备控制', icon: Router },
  { path: '/models', label: 'AI 模型', icon: BrainCircuit }
]

const routeTitle = computed(() => navItems.find((item) => item.path === route.path)?.label || '项目介绍')
const edgeConnected = computed(() => telemetry.serialConnected || telemetry.networkConnected)
const edgeStatusLabel = computed(() => {
  if (telemetry.networkConnected && telemetry.serialConnected && telemetry.dataFresh) return 'WiFi+串口'
  if (telemetry.networkConnected && telemetry.dataFresh) return 'WiFi实时'
  if (telemetry.serialConnected && telemetry.dataFresh) return '串口实时'
  if (telemetry.serialConnected || telemetry.networkConnected) return '链路已打开，等待数据'
  return '离线'
})
const maixCamStatus = computed(() => {
  const camera = telemetry.latest?.maixCam || telemetry.latest?.vision
  const fps = Number(camera?.fps)
  return Number.isFinite(fps) ? `${fps.toFixed(1)} FPS` : '未上报'
})
let refreshTimer
let effects

function reload() {
  dashboard.load()
  telemetry.loadSnapshot()
}

onMounted(() => {
  dashboard.load()
  telemetry.loadSnapshot()
  telemetry.connect()
  refreshTimer = window.setInterval(() => dashboard.load(), 15000)
  effects = runPremiumEffects()
})

watch(
  () => route.fullPath,
  async () => {
    await nextTick()
    effects?.refresh()
  },
  { flush: 'post' }
)

watch(
  () => [dashboard.loading, Boolean(dashboard.data)],
  async () => {
    await nextTick()
    effects?.refresh()
  },
  { flush: 'post' }
)

onBeforeUnmount(() => {
  window.clearInterval(refreshTimer)
  telemetry.disconnect()
  effects?.cleanup()
})
</script>
