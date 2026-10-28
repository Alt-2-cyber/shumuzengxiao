<template>
  <div class="grid page-stack">
    <section class="grid cols-4">
      <article v-for="device in devices" :key="device.id" class="card pad device-card">
        <div class="device-head">
          <div>
            <strong>{{ device.name }}</strong>
            <span>{{ deviceTypeLabel(device.type) }}</span>
          </div>
          <span class="status-dot" :class="device.status?.toLowerCase()"></span>
        </div>
        <div class="device-meta">
          <span>电量 {{ device.battery }}%</span>
          <span>信号 {{ device.signalStrength }} dBm</span>
          <span>{{ formatTime(device.lastSeen) }}</span>
        </div>
      </article>
    </section>

    <section class="grid cols-2">
      <article class="card pad">
        <div class="section-title">
          <h2>执行器控制</h2>
          <span class="actuator-connection" :class="{ online: controlReady }">
            <i></i>{{ controlTransport }} {{ controlReady ? '已连接' : (telemetry.serialConnected || telemetry.networkConnected ? '等待数据' : '离线') }}
          </span>
        </div>

        <div class="actuator-state-strip">
          <div>
            <span>目标设备</span>
            <strong>{{ actualDeviceId }}</strong>
          </div>
          <div>
            <span>风扇模式</span>
            <strong>{{ fanModeLabel }}</strong>
          </div>
          <div>
            <span>声光报警</span>
            <strong :class="{ danger: currentControl.manualAlarm }">
              {{ currentControl.manualAlarm ? '报警中' : '已解除' }}
            </strong>
          </div>
        </div>

        <div class="actuator-control-row">
          <div class="actuator-label">
            <Wind :size="20" />
            <div><strong>通风风扇</strong><span>GPIO14</span></div>
          </div>
          <div class="segmented-control">
            <button
              title="强制开启风扇"
              :class="{ active: currentControl.fanMode === 'on' }"
              :disabled="!controlReady || Boolean(sendingAction)"
              @click="control('fan', true)"
            ><Wind :size="17" /> 开</button>
            <button
              title="强制关闭风扇"
              :class="{ active: currentControl.fanMode === 'off' }"
              :disabled="!controlReady || Boolean(sendingAction)"
              @click="control('fan', false)"
            ><Power :size="17" /> 关</button>
            <button
              title="恢复温湿度和 MQ 自动联动"
              :class="{ active: currentControl.fanMode === 'auto' }"
              :disabled="!controlReady || Boolean(sendingAction)"
              @click="control('fan_auto', true)"
            ><RefreshCcw :size="17" /> 自动</button>
          </div>
        </div>

        <div class="actuator-control-row">
          <div class="actuator-label">
            <Siren :size="20" />
            <div><strong>红灯与蜂鸣器</strong><span>GPIO16 / GPIO21</span></div>
          </div>
          <div class="alarm-actions">
            <button
              class="command-button warning"
              :disabled="!controlReady || Boolean(sendingAction)"
              @click="control('alarm', true)"
            ><Siren :size="18" /> 触发报警</button>
            <button
              class="command-button secondary"
              :disabled="!controlReady || Boolean(sendingAction)"
              @click="control('alarm', false)"
            ><BellOff :size="18" /> 解除报警</button>
          </div>
        </div>

        <div class="unavailable-control-grid">
          <button disabled><Droplets :size="18" /><span>雾化器<small>未接线</small></span></button>
          <button disabled><Camera :size="18" /><span>MaixCam 抓拍<small>未建立控制链路</small></span></button>
        </div>

        <div v-if="commandMessage" class="command-result" :class="commandResultClass">
          {{ commandMessage }}
        </div>
      </article>

      <article class="card pad">
        <div class="section-title">
          <h2>硬件数据链路</h2>
          <span class="muted">现场端到平台端</span>
        </div>
        <div class="flow-list">
          <div class="flow-step">ESP32 采集环境、健康、声音和三位置运动数据</div>
          <div class="flow-step">MaixCam 本地执行 YOLO 姿态、皮肤、眼鼻异常推理</div>
          <div class="flow-step">USB 串口 JSON 双向传输遥测、控制命令和执行确认</div>
          <div class="flow-step">Spring Boot 维护实时快照、命令记录和 WebSocket 推送</div>
          <div class="flow-step">Vue3 看板显示设备实态，只开放已接线的执行器</div>
        </div>
      </article>
    </section>

    <section class="card pad">
      <div class="section-title">
        <h2>设备清单</h2>
        <span class="muted">牛舍 barn_01</span>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>设备 ID</th>
            <th>名称</th>
            <th>类型</th>
            <th>状态</th>
            <th>电量</th>
            <th>信号</th>
            <th>最后在线</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="device in devices" :key="device.id">
            <td>{{ device.deviceId }}</td>
            <td>{{ device.name }}</td>
            <td>{{ deviceTypeLabel(device.type) }}</td>
            <td>{{ statusLabel(device.status) }}</td>
            <td>{{ device.battery }}%</td>
            <td>{{ device.signalStrength }} dBm</td>
            <td>{{ formatFullTime(device.lastSeen) }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <section class="card pad">
      <div class="section-title">
        <h2>命令历史</h2>
        <span class="muted">最近 20 条控制下发记录</span>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>设备</th>
            <th>动作</th>
            <th>目标状态</th>
            <th>队列状态</th>
            <th>时间</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="command in commands" :key="command.id">
            <td>{{ command.deviceId }}</td>
            <td>{{ actionLabel(command.action) }}</td>
            <td>{{ targetState(command) }}</td>
            <td><span class="command-status" :class="command.status">{{ commandStatusLabel(command.status) }}</span></td>
            <td>{{ formatFullTime(command.queuedAt) }}</td>
          </tr>
          <tr v-if="commands.length === 0">
            <td colspan="5" class="muted">暂无命令记录</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { storeToRefs } from 'pinia'
import { BellOff, Camera, Droplets, Power, RefreshCcw, Siren, Wind } from 'lucide-vue-next'
import { getCommandHistory, sendCommand } from '../api/client'
import { useDashboardStore } from '../stores/dashboard'
import { useTelemetryStore } from '../stores/telemetry'
import { deviceTypeLabel, formatFullTime, formatTime, statusLabel } from '../utils/format'

const store = useDashboardStore()
const telemetry = useTelemetryStore()
const { data } = storeToRefs(store)
const lastCommand = ref(null)
const commandError = ref('')
const sendingAction = ref('')
const commands = ref([])
const devices = computed(() => data.value?.devices || [])
const currentControl = computed(() => {
  const environment = telemetry.latestEnvironment || {}
  const control = environment.control || {}
  const ack = telemetry.lastCommandAck || {}
  const acknowledgedFanMode = ack.action === 'fan_auto'
    ? 'auto'
    : ack.action === 'fan' ? (ack.enabled ? 'on' : 'off') : undefined
  return {
    ...control,
    fan: control.fan ?? environment.fan ?? environment.fanOn,
    fanMode: acknowledgedFanMode ?? control.fanMode ?? environment.fanMode,
    manualAlarm: control.manualAlarm ?? environment.alarm ?? environment.alarmOn,
    atomizer: control.atomizer ?? environment.atomizer ?? environment.atomizerOn
  }
})
const controlReady = computed(() => telemetry.websocketConnected && telemetry.dataFresh &&
  (telemetry.serialConnected || telemetry.networkConnected))
const controlTransport = computed(() => {
  if (telemetry.networkConnected && telemetry.serialConnected) return 'WiFi+串口'
  if (telemetry.networkConnected) return 'WiFi'
  if (telemetry.serialConnected && telemetry.dataFresh) return 'USB串口'
  if (telemetry.serialConnected) return '串口已打开'
  return telemetry.port
})
const actualDeviceId = computed(() => devices.value.find(device => device.deviceId === 'env_01')?.deviceId || 'env_01')
const fanModeLabel = computed(() => ({ on: '强制开启', off: '强制关闭', auto: '自动联动' })[currentControl.value.fanMode] || '-')
const commandApplied = computed(() => {
  if (!lastCommand.value) return false
  const commandId = Number(lastCommand.value.id)
  return Number(telemetry.lastCommandAck?.commandId) === commandId ||
    Number(currentControl.value.lastCommandId) === commandId
})
const commandMessage = computed(() => {
  if (commandError.value) return commandError.value
  if (!lastCommand.value) return ''
  if (lastCommand.value.status === 'failed') return `命令发送失败：${telemetry.lastError || '设备未上线或控制链路不可用'}`
  if (lastCommand.value.status === 'queued') return `命令已进入 WiFi 轮询队列，等待 ${actualDeviceId.value} 执行`
  if (lastCommand.value.status === 'unsupported') return '该执行器没有可用的硬件控制链路'
  if (commandApplied.value) return `设备已执行 ${actionLabel(lastCommand.value.action)}，当前端口 ${telemetry.port}`
  return `命令已通过 ${controlTransport.value} 发送，等待 ESP32 确认`
})
const commandResultClass = computed(() => ({
  success: commandApplied.value,
  error: Boolean(commandError.value) || ['failed', 'unsupported'].includes(lastCommand.value?.status)
}))

async function control(action, enabled) {
  if (!controlReady.value || sendingAction.value) return
  sendingAction.value = `${action}:${enabled}`
  commandError.value = ''
  try {
    lastCommand.value = await sendCommand({ deviceId: actualDeviceId.value, action, enabled })
    await loadCommands()
  } catch (error) {
    commandError.value = error?.response?.data?.message || error?.message || '命令发送失败'
  } finally {
    sendingAction.value = ''
  }
}

async function loadCommands() {
  commands.value = await getCommandHistory()
}

function actionLabel(action) {
  return {
    fan: '风扇',
    fan_auto: '风扇自动模式',
    atomizer: '雾化器',
    alarm: '声光报警',
    snapshot: '视觉抓拍'
  }[action] || action
}

function targetState(command) {
  if (command.action === 'fan_auto') return '自动联动'
  return command.enabled ? '开启/执行' : '关闭/解除'
}

function commandStatusLabel(status) {
  return {
    queued: '排队中',
    sent: '已发送',
    failed: '发送失败',
    unsupported: '不支持'
  }[status] || status
}

onMounted(() => {
  if (!data.value) store.load()
  telemetry.loadSnapshot()
  telemetry.connect()
  loadCommands()
})
</script>
