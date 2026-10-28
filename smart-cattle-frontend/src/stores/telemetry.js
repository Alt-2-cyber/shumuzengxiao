import { defineStore } from 'pinia'
import { getAudioEvents, getTelemetrySnapshot } from '../api/client'

const MAX_HISTORY = 120
const browserApiKey = import.meta.env.VITE_API_KEY
let socket = null
let reconnectTimer = null
let manualClose = false

function rowKey(row) {
  return `${row?.deviceId || 'unknown'}:${row?.seq ?? 'none'}:${row?.receivedAt || 'none'}`
}

function isCattleTelemetry(row) {
  const deviceId = String(row?.deviceId || '').toLowerCase()
  return deviceId.startsWith('cow') || deviceId.startsWith('cattle') ||
    Boolean(row?.behavior || row?.mpu0 || row?.mpu1 || row?.adxl345 || row?.b1Infrared || row?.microphone)
}

function isEnvironmentTelemetry(row) {
  const deviceId = String(row?.deviceId || '').toLowerCase()
  return String(row?.type || '').toLowerCase() === 'environment' ||
    deviceId.startsWith('env') || (row?.lightLux !== undefined && !isCattleTelemetry(row))
}

function environmentRow(row) {
  if (!row) return null
  return {
    ...row,
    recordedAt: row.recordedAt || row.receivedAt || new Date().toISOString()
  }
}

function mergeHistory(current, incoming) {
  const unique = new Map()
  for (const row of [...current, ...incoming]) {
    if (row) unique.set(rowKey(row), row)
  }
  return [...unique.values()]
    .sort((a, b) => new Date(a.receivedAt || 0) - new Date(b.receivedAt || 0))
    .slice(-MAX_HISTORY)
}

function mergeAudioEvents(current, incoming) {
  const unique = new Map()
  for (const event of [...current, ...incoming]) {
    if (event?.id !== null && event?.id !== undefined) unique.set(event.id, event)
  }
  return [...unique.values()]
    .sort((a, b) => new Date(b.recordedAt || 0) - new Date(a.recordedAt || 0))
    .slice(0, 40)
}

export const useTelemetryStore = defineStore('telemetry', {
  state: () => ({
    latest: null,
    latestEnvironment: null,
    history: [],
    environmentHistory: [],
    serialConnected: false,
    networkConnected: false,
    websocketConnected: false,
    status: 'starting',
    port: 'COM5,COM9',
    baudRate: 115200,
    lastReceivedAt: null,
    dataFresh: false,
    dataAgeMs: null,
    lastCommandAck: null,
    audioEvents: [],
    lastError: null,
    loading: false,
    error: ''
  }),
  actions: {
    async loadSnapshot() {
      this.loading = true
      try {
        const snapshot = await getTelemetrySnapshot(60)
        const hasSerialState = Object.prototype.hasOwnProperty.call(snapshot, 'serialConnected')
        this.serialConnected = hasSerialState ? Boolean(snapshot.serialConnected) : Boolean(snapshot.connected)
        this.networkConnected = Boolean(snapshot.networkConnected)
        this.status = snapshot.status || 'unknown'
        this.port = snapshot.port || this.port
        this.baudRate = snapshot.baudRate || this.baudRate
        this.lastReceivedAt = snapshot.lastReceivedAt || this.lastReceivedAt
        this.dataFresh = Boolean(snapshot.dataFresh)
        this.dataAgeMs = snapshot.dataAgeMs ?? this.dataAgeMs
        this.lastError = snapshot.lastError || null
        this.lastCommandAck = snapshot.lastCommandAck || this.lastCommandAck
        this.history = mergeHistory(this.history, snapshot.history || [])
        const snapshotEnvironment = snapshot.latestEnvironment ||
          (isEnvironmentTelemetry(snapshot.latest) ? snapshot.latest : null)
        if (snapshotEnvironment) this.latestEnvironment = environmentRow(snapshotEnvironment)
        const snapshotCattle = snapshot.latestCattle ||
          (isCattleTelemetry(snapshot.latest) ? snapshot.latest : null)
        if (snapshotCattle) this.latest = snapshotCattle
        this.environmentHistory = mergeHistory(
          this.environmentHistory,
          (snapshot.history || []).filter(isEnvironmentTelemetry).map(environmentRow)
        )
        this.error = ''
      } catch (error) {
        this.error = error?.message || '无法读取 ESP32 实时数据'
      } finally {
        this.loading = false
      }
    },
    async loadAudioEvents() {
      try {
        this.audioEvents = mergeAudioEvents(this.audioEvents, await getAudioEvents())
      } catch (error) {
        this.error = error?.message || '无法读取声音事件'
      }
    },
    connect() {
      manualClose = false
      if (socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) return

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      // Native browser WebSockets cannot attach Authorization. The backend only
      // accepts this query credential when its API-key gate is enabled.
      const credential = browserApiKey ? `?apiKey=${encodeURIComponent(browserApiKey)}` : ''
      socket = new WebSocket(`${protocol}//${window.location.host}/ws/telemetry${credential}`)
      socket.addEventListener('open', () => {
        this.websocketConnected = true
        this.error = ''
      })
      socket.addEventListener('message', (event) => {
        let payload
        try {
          payload = JSON.parse(event.data)
        } catch {
          return
        }
        if (payload.type === 'telemetry' && payload.data) {
          const data = payload.data
          const receivedVia = String(data.receivedVia || '').toLowerCase()
          const isNetwork = receivedVia === 'wifi_http' ||
            (!receivedVia && String(data.transport || '').includes('wifi'))
          const isSerial = receivedVia === 'usb_serial' || receivedVia === 'serial'
          if (isNetwork) this.networkConnected = true
          if (isSerial) this.serialConnected = true
          this.lastReceivedAt = data.receivedAt || new Date().toISOString()
          this.dataFresh = true
          this.dataAgeMs = 0
          this.status = 'streaming'
          this.lastError = null
          this.history = mergeHistory(this.history, [data])
          if (isEnvironmentTelemetry(data)) {
            this.latestEnvironment = environmentRow(data)
            this.environmentHistory = mergeHistory(this.environmentHistory, [environmentRow(data)])
          } else if (isCattleTelemetry(data)) {
            this.latest = data
          }
        } else if (payload.type === 'environment' && payload.data) {
          const data = environmentRow(payload.data)
          this.latestEnvironment = data
          this.environmentHistory = mergeHistory(this.environmentHistory, [data])
          this.networkConnected = true
          this.lastReceivedAt = data.receivedAt || data.recordedAt || new Date().toISOString()
          this.dataFresh = true
          this.dataAgeMs = 0
          this.status = 'streaming'
          this.lastError = null
        } else if (payload.type === 'status') {
          const hasSerialState = Object.prototype.hasOwnProperty.call(payload, 'serialConnected')
          this.serialConnected = hasSerialState
            ? Boolean(payload.serialConnected)
            : Boolean(payload.portConnected ?? payload.connected)
          this.networkConnected = Boolean(payload.networkConnected)
          this.status = payload.status || 'unknown'
          this.port = payload.port || this.port
          this.baudRate = payload.baudRate || this.baudRate
          this.dataFresh = Boolean(payload.dataFresh)
          this.dataAgeMs = payload.dataAgeMs ?? null
          this.lastReceivedAt = payload.lastReceivedAt || this.lastReceivedAt
          this.lastError = payload.lastError || null
        } else if (payload.type === 'command_ack' && payload.data) {
          this.lastCommandAck = payload.data
        } else if (payload.type === 'audio_event' && payload.data) {
          this.audioEvents = mergeAudioEvents(this.audioEvents, [payload.data])
        }
      })
      socket.addEventListener('close', () => {
        this.websocketConnected = false
        socket = null
        if (!manualClose) {
          window.clearTimeout(reconnectTimer)
          reconnectTimer = window.setTimeout(() => this.connect(), 2000)
        }
      })
      socket.addEventListener('error', () => {
        this.websocketConnected = false
      })
    },
    disconnect() {
      manualClose = true
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
      socket?.close()
      socket = null
      this.websocketConnected = false
    }
  }
})
