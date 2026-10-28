<template>
  <div class="audio-page grid page-stack">
    <section class="audio-livebar" :class="`signal-${signalClass}`">
      <div class="audio-live-identity">
        <span class="audio-live-dot"></span>
        <div>
          <strong>实时声音筛查</strong>
          <span>{{ latest?.cattleId || latest?.deviceId || '等待 ESP32 节点' }}</span>
        </div>
      </div>
      <div class="audio-live-stat">
        <Radio :size="17" />
        <span>{{ signalLabel }}</span>
      </div>
      <div class="audio-live-stat">
        <Cpu :size="17" />
        <span>{{ modelLabel }}</span>
      </div>
      <button
        class="audio-capture-button"
        :disabled="!canCapture || capturePending || microphone?.captureInProgress"
        :title="canCapture ? '采集 2 秒声音样本' : '麦克风信号有效后可采集'"
        @click="captureAudio"
      >
        <Mic :size="18" />
        <span>{{ captureButtonLabel }}</span>
      </button>
    </section>

    <section class="audio-metric-grid">
      <article class="card pad audio-meter-card">
        <div class="section-title">
          <h2>输入信号</h2>
          <span class="audio-channel">{{ microphone?.channel || '-' }}</span>
        </div>
        <div class="audio-db-readout">
          <strong>{{ fixed(microphone?.dbfs, 1, ' dBFS') }}</strong>
          <span>RMS {{ fixed(microphone?.rms, 4) }}</span>
        </div>
        <div class="audio-level-track" aria-label="当前麦克风信号强度">
          <span :style="{ width: `${levelPercent}%` }"></span>
        </div>
        <div class="audio-mini-grid">
          <div><span>饱和</span><strong>{{ percent(microphone?.saturationRatio) }}</strong></div>
          <div><span>信噪比</span><strong>{{ fixed(microphone?.snrDb, 1, ' dB') }}</strong></div>
          <div><span>采样</span><strong>{{ microphone?.samples ?? '-' }}</strong></div>
        </div>
      </article>

      <article class="card pad audio-model-card">
        <div class="section-title">
          <h2>边缘模型</h2>
          <span class="model-state" :class="`state-${modelState}`">{{ modelStateLabel }}</span>
        </div>
        <div class="audio-model-readout">
          <div class="model-icon"><BrainCircuit :size="28" /></div>
          <div>
            <strong>{{ eventLabel(microphone?.eventLabel) }}</strong>
            <span>{{ microphone?.modelVersion || '等待固件上报' }}</span>
          </div>
          <b>{{ percent(microphone?.eventScore) }}</b>
        </div>
        <div class="audio-band-list">
          <div><span>低频</span><i><b :style="{ width: bandWidth(microphone?.lowBandRatio) }"></b></i><strong>{{ percent(microphone?.lowBandRatio) }}</strong></div>
          <div><span>中频</span><i><b :style="{ width: bandWidth(microphone?.midBandRatio) }"></b></i><strong>{{ percent(microphone?.midBandRatio) }}</strong></div>
          <div><span>高频</span><i><b :style="{ width: bandWidth(microphone?.highBandRatio) }"></b></i><strong>{{ percent(microphone?.highBandRatio) }}</strong></div>
        </div>
      </article>

      <article class="card pad audio-screen-card" :class="{ 'is-candidate': audioCandidate }">
        <div class="section-title">
          <h2>筛查状态</h2>
          <ShieldAlert v-if="audioCandidate" :size="20" />
          <ShieldCheck v-else :size="20" />
        </div>
        <strong>{{ screeningHeadline }}</strong>
        <div class="screen-line"><span>发声候选</span><b>{{ microphone?.vocalizationCandidate ? '有' : '无' }}</b></div>
        <div class="screen-line"><span>呼吸声候选</span><b>{{ microphone?.respiratoryCandidate ? '待复核' : '无' }}</b></div>
        <div class="screen-line"><span>异常鸣叫模型</span><b>{{ microphone?.abnormalVocalizationCandidate ? '待复核' : '无' }}</b></div>
        <div class="screen-line"><span>当前采集</span><b>{{ microphone?.captureInProgress ? '进行中' : '空闲' }}</b></div>
      </article>
    </section>

    <section class="card pad audio-event-panel">
      <div class="section-title audio-event-title">
        <div>
          <h2>声音事件与复核</h2>
          <span class="muted">{{ audioEvents.length }} 条真实边缘记录</span>
        </div>
        <button class="icon-button" title="刷新声音事件" @click="refreshEvents">
          <RefreshCcw :size="18" />
        </button>
      </div>
      <div v-if="audioEvents.length" class="table-scroll">
        <table class="table audio-event-table">
          <thead>
            <tr>
              <th>时间</th>
              <th>事件</th>
              <th>置信度</th>
              <th>特征</th>
              <th>音频</th>
              <th>人工复核</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in audioEvents" :key="event.id">
              <td>{{ formatFullTime(event.recordedAt) }}</td>
              <td>
                <strong>{{ eventLabel(event.label || event.eventType) }}</strong>
                <small>{{ event.modelStatus || 'feature_only' }}</small>
                <small v-if="event.clipAvailable" class="audio-research-result" :title="researchResults[event.id]?.model_version || ''">
                  {{ researchText(event.id) }}
                </small>
              </td>
              <td>{{ percent(event.score) }}</td>
              <td>
                <span>RMS {{ fixed(event.rms, 4) }}</span>
                <small>SNR {{ fixed(event.snr, 1, ' dB') }}</small>
              </td>
              <td>
                <audio v-if="event.clipAvailable && clipUrls[event.id]" controls preload="metadata" :src="clipUrls[event.id]"></audio>
                <span v-else class="muted">{{ event.clipAvailable ? '音频加载中' : '特征事件' }}</span>
              </td>
              <td>
                <div class="review-fields">
                  <select v-model="reviewDraft(event).status" aria-label="复核状态">
                    <option value="pending">待复核</option>
                    <option value="confirmed">确认候选</option>
                    <option value="rejected">排除</option>
                    <option value="normal">正常</option>
                  </select>
                  <select v-model="reviewDraft(event).label" aria-label="声音标签">
                    <option value="">未标注</option>
                    <option value="normal">正常</option>
                    <option value="moo">牛叫</option>
                    <option value="cough_suspect">咳嗽候选</option>
                    <option value="wheeze_suspect">喘鸣候选</option>
                    <option value="abnormal_vocalization_suspect">异常鸣叫候选</option>
                    <option value="barn_noise">背景声</option>
                  </select>
                  <input v-model.trim="reviewDraft(event).note" maxlength="1200" placeholder="复核备注" aria-label="复核备注" />
                </div>
                <details class="clinical-signoff">
                  <summary>{{ event.clinicallyVerifiedAt ? `兽医签核 ${formatFullTime(event.clinicallyVerifiedAt)}` : '兽医临床签核（疾病训练必填）' }}</summary>
                  <div class="clinical-signoff-grid">
                    <label><input v-model="reviewDraft(event).clinicallyVerified" type="checkbox"> 临床签核</label>
                    <input v-model.trim="reviewDraft(event).animalId" maxlength="120" placeholder="真实耳标/管理编号" aria-label="真实耳标或管理编号" />
                    <input v-model.trim="reviewDraft(event).recordingSessionId" maxlength="120" placeholder="录音会话编号" aria-label="录音会话编号" />
                    <input v-model.trim="reviewDraft(event).veterinarian" maxlength="80" placeholder="兽医姓名或工号" aria-label="兽医姓名或工号" />
                    <input v-model.trim="reviewDraft(event).clinicalEvidenceReference" maxlength="1200" placeholder="病例、听诊或超声证据编号" aria-label="临床证据编号" />
                  </div>
                </details>
              </td>
              <td>
                <button class="icon-button" title="保存复核" :disabled="savingEventId === event.id" @click="saveReview(event)">
                  <Save :size="18" />
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="audio-empty-state">
        <Volume2 :size="23" />
        <span>{{ emptyMessage }}</span>
      </div>
    </section>

    <section class="audio-boundary">
      <BadgeInfo :size="19" />
      <p>声音结果用于健康风险筛查和人工复核。疾病模型训练只接受真实牛舍录音和完整兽医临床签核；普通人工标注只能用于声学事件整理。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue'
import { storeToRefs } from 'pinia'
import {
  BadgeInfo,
  BrainCircuit,
  Cpu,
  Mic,
  Radio,
  RefreshCcw,
  Save,
  ShieldAlert,
  ShieldCheck,
  Volume2
} from 'lucide-vue-next'
import { getAudioClip, getAudioResearch, reviewAudioEvent, sendCommand } from '../api/client'
import { useTelemetryStore } from '../stores/telemetry'
import { eventLabel, fixed, formatFullTime, percent } from '../utils/format'

const telemetry = useTelemetryStore()
const { latest, audioEvents } = storeToRefs(telemetry)
const drafts = reactive({})
const clipUrls = reactive({})
const researchResults = reactive({})
const researchRequests = new Set()
const researchAttempts = new Map()
const capturePending = ref(false)
const savingEventId = ref(null)
let refreshTimer
let mounted = true

const microphone = computed(() => latest.value?.microphone || null)
const signalClass = computed(() => microphone.value?.status === 'ok' ? 'valid' : 'invalid')
const signalLabel = computed(() => microphone.value?.status === 'ok' ? '信号有效' : (microphone.value?.status || '等待上报'))
const canCapture = computed(() => microphone.value?.status === 'ok')
const captureButtonLabel = computed(() => capturePending.value
  ? '请求中'
  : (microphone.value?.captureInProgress ? '采集中' : '采集 2 秒样本'))
const modelState = computed(() => microphone.value?.modelStatus || 'feature_only')
const modelStateLabel = computed(() => modelState.value === 'deployed' ? '已部署' : '待训练')
const modelLabel = computed(() => modelState.value === 'deployed' ? '分类模型已部署' : '特征采集模式')
const audioCandidate = computed(() => Boolean(
  microphone.value?.respiratoryCandidate || microphone.value?.abnormalVocalizationCandidate
))
const screeningHeadline = computed(() => {
  if (microphone.value?.status !== 'ok') return '等待有效声音输入'
  if (microphone.value?.respiratoryCandidate) return '发现待复核呼吸声候选'
  if (microphone.value?.abnormalVocalizationCandidate) return '发现待复核异常鸣叫候选'
  if (modelState.value !== 'deployed') return '正在积累标注样本'
  return '当前未见呼吸声候选'
})
const emptyMessage = computed(() => microphone.value?.status === 'ok'
  ? '尚无已保存的声音事件'
  : '麦克风信号有效后可采集和保存声音样本')
const levelPercent = computed(() => {
  const dbfs = Number(microphone.value?.dbfs)
  if (!Number.isFinite(dbfs)) return 0
  return Math.max(0, Math.min(100, Math.round(((dbfs + 80) / 80) * 100)))
})

function bandWidth(value) {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '0%'
  return `${Math.max(0, Math.min(100, Number(value) * 100))}%`
}

function reviewDraft(event) {
  const key = String(event.id)
  if (!drafts[key]) {
    drafts[key] = {
      status: event.reviewStatus || 'pending',
      label: event.reviewLabel || '',
      note: event.reviewNote || '',
      clinicallyVerified: Boolean(event.clinicallyVerifiedAt),
      animalId: event.clinicalAnimalId || event.cattleId || '',
      recordingSessionId: event.recordingSessionId || '',
      veterinarian: event.veterinarian || '',
      clinicalEvidenceReference: event.clinicalEvidenceReference || ''
    }
  }
  return drafts[key]
}

async function loadClip(event) {
  if (!event?.id || !event.clipAvailable || !event.audioClipPath || clipUrls[event.id]) return
  try {
    const clip = await getAudioClip(event.audioClipPath)
    clipUrls[event.id] = URL.createObjectURL(clip)
  } catch {
    // A missing or unauthorized clip must not prevent review of its metadata.
  }
}

async function loadAvailableClips() {
  await Promise.all(audioEvents.value.flatMap((event) => [loadClip(event), loadResearch(event)]))
}

async function loadResearch(event) {
  if (!event?.id || !event.clipAvailable || !event.audioClipPath || researchRequests.has(event.id)) return
  const state = researchResults[event.id]?.status
  if (['ready', 'disabled', 'inference_failed'].includes(state)) return
  const wait = state === 'model_unavailable' || state === 'unavailable' ? 30000 : 3000
  if (Date.now() - (researchAttempts.get(event.id) || 0) < wait) return
  researchRequests.add(event.id)
  researchAttempts.set(event.id, Date.now())
  try {
    const result = await getAudioResearch(event.audioClipPath)
    if (mounted) researchResults[event.id] = result
  } catch {
    if (mounted) researchResults[event.id] = { status: 'unavailable' }
  } finally {
    researchRequests.delete(event.id)
  }
}

function researchText(eventId) {
  const result = researchResults[eventId]
  if (!result || ['pending', 'busy'].includes(result.status)) return '声音研究分析中'
  if (result.status !== 'ready') return result.status === 'disabled' ? '声音研究分析未启用' : '声音研究模型暂不可用'
  const scored = (result.windows || []).filter((window) => window.status === 'scored')
  const cough = scored.filter((window) => window.label === 'cough').sort((a, b) => b.score - a.score)[0]
  const best = cough || scored.sort((a, b) => b.score - a.score)[0]
  if (!best) return '声音研究：信号不足，未判定'
  return best.label === 'cough' ? `声音研究：咳嗽候选 ${percent(best.score)}` : '声音研究：非咳嗽片段'
}

watch(
  () => audioEvents.value.map((event) => event.id).join(','),
  () => { void loadAvailableClips() },
  { immediate: true }
)

async function captureAudio() {
  if (!canCapture.value || capturePending.value) return
  capturePending.value = true
  try {
    await sendCommand({
      deviceId: latest.value?.deviceId || 'demo_esp32_01',
      action: 'audio_capture',
      enabled: true
    })
  } finally {
    window.setTimeout(() => { capturePending.value = false }, 1800)
  }
}

async function saveReview(event) {
  const draft = reviewDraft(event)
  savingEventId.value = event.id
  try {
    if (draft.clinicallyVerified && (!draft.animalId || !draft.recordingSessionId || !draft.veterinarian || !draft.clinicalEvidenceReference)) {
      window.alert('兽医临床签核需要真实耳标、录音会话、兽医和临床证据编号。')
      return
    }
    const updated = await reviewAudioEvent(event.id, {
      ...draft,
      reviewer: '现场复核'
    })
    telemetry.audioEvents = telemetry.audioEvents.map((item) => item.id === updated.id ? updated : item)
  } finally {
    savingEventId.value = null
  }
}

async function refreshEvents() {
  await telemetry.loadAudioEvents()
  await loadAvailableClips()
}

onMounted(() => {
  telemetry.loadSnapshot()
  telemetry.loadAudioEvents()
  telemetry.connect()
  refreshTimer = window.setInterval(refreshEvents, 5000)
})

onBeforeUnmount(() => {
  mounted = false
  window.clearInterval(refreshTimer)
  Object.values(clipUrls).forEach((url) => URL.revokeObjectURL(url))
})
</script>

<style scoped>
.audio-page { min-width: 0; }

.audio-livebar {
  display: grid;
  grid-template-columns: minmax(250px, 1.25fr) minmax(155px, .7fr) minmax(190px, .82fr) auto;
  align-items: center;
  min-height: 68px;
  border: 1px solid rgba(248, 242, 223, .16);
  border-left: 3px solid var(--red);
  background: rgba(12, 18, 14, .76);
}

.audio-livebar.signal-valid { border-left-color: var(--green); }
.audio-live-identity,
.audio-live-stat { display: flex; align-items: center; min-width: 0; gap: 10px; padding: 12px 16px; }
.audio-live-identity > div { display: grid; min-width: 0; }
.audio-live-identity span:not(.audio-live-dot) { overflow: hidden; color: var(--muted); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.audio-live-stat { min-height: 42px; color: var(--muted); border-left: 1px solid var(--line); font-size: 13px; }
.audio-live-stat span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.audio-live-dot { flex: 0 0 auto; width: 9px; height: 9px; border-radius: 50%; background: var(--red); box-shadow: 0 0 0 6px rgba(255, 110, 87, .12); }
.signal-valid .audio-live-dot { background: var(--green); box-shadow: 0 0 0 6px rgba(142, 240, 160, .12); }
.audio-capture-button { display: inline-flex; align-items: center; justify-content: center; min-width: 166px; min-height: 42px; gap: 8px; margin: 10px 12px; color: #071009; background: var(--green); border: 0; border-radius: 6px; font-weight: 900; cursor: pointer; }
.audio-capture-button:disabled { color: var(--muted); background: rgba(248, 242, 223, .09); cursor: not-allowed; }

.audio-metric-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 15px; }
.audio-meter-card, .audio-model-card, .audio-screen-card { min-height: 250px; }
.audio-channel, .model-state { padding: 4px 7px; color: var(--blue); border: 1px solid rgba(124, 183, 255, .28); background: rgba(124, 183, 255, .08); font-family: Consolas, monospace; font-size: 11px; }
.model-state.state-deployed { color: var(--green); border-color: rgba(142, 240, 160, .28); background: rgba(142, 240, 160, .08); }
.audio-db-readout { display: grid; gap: 4px; margin-top: 26px; }
.audio-db-readout strong { font-size: 34px; font-variant-numeric: tabular-nums; }
.audio-db-readout span { color: var(--muted); font-family: Consolas, monospace; font-size: 13px; }
.audio-level-track { overflow: hidden; height: 8px; margin: 18px 0; background: rgba(248, 242, 223, .10); }
.audio-level-track span { display: block; height: 100%; background: linear-gradient(90deg, var(--blue), var(--green), var(--gold)); transition: width .3s ease; }
.audio-mini-grid { display: grid; grid-template-columns: repeat(3, minmax(0, 1fr)); gap: 1px; border: 1px solid var(--line); background: var(--line); }
.audio-mini-grid > div { min-width: 0; padding: 9px; background: #111813; }
.audio-mini-grid span, .audio-mini-grid strong { display: block; overflow-wrap: anywhere; }
.audio-mini-grid span { color: var(--muted); font-size: 11px; }
.audio-mini-grid strong { margin-top: 4px; font-size: 14px; font-variant-numeric: tabular-nums; }

.audio-model-readout { display: grid; grid-template-columns: 52px minmax(0, 1fr) auto; align-items: center; gap: 12px; margin: 23px 0 20px; }
.model-icon { display: grid; width: 50px; height: 50px; place-items: center; color: #071009; background: var(--gold); }
.audio-model-readout > div:nth-child(2) { display: grid; min-width: 0; gap: 4px; }
.audio-model-readout strong { overflow-wrap: anywhere; font-family: "Noto Serif SC", serif; font-size: 20px; }
.audio-model-readout span { overflow: hidden; color: var(--muted); font-family: Consolas, monospace; font-size: 11px; text-overflow: ellipsis; white-space: nowrap; }
.audio-model-readout b { color: var(--gold); font-size: 21px; font-variant-numeric: tabular-nums; }
.audio-band-list { display: grid; gap: 10px; }
.audio-band-list > div { display: grid; grid-template-columns: 42px minmax(40px, 1fr) 42px; align-items: center; gap: 8px; color: var(--muted); font-size: 12px; }
.audio-band-list i { overflow: hidden; height: 6px; background: rgba(248, 242, 223, .10); }
.audio-band-list i b { display: block; height: 100%; background: var(--blue); }
.audio-band-list > div:nth-child(2) i b { background: var(--green); }
.audio-band-list > div:nth-child(3) i b { background: var(--gold); }
.audio-band-list strong { color: var(--text); font-variant-numeric: tabular-nums; }

.audio-screen-card { border-top: 3px solid var(--green); }
.audio-screen-card.is-candidate { border-top-color: var(--red); }
.audio-screen-card .section-title svg { color: var(--green); }
.audio-screen-card.is-candidate .section-title svg { color: var(--red); }
.audio-screen-card > strong { display: block; min-height: 58px; margin: 25px 0 18px; font-family: "Noto Serif SC", serif; font-size: 23px; line-height: 1.35; }
.screen-line { display: flex; justify-content: space-between; gap: 10px; padding: 9px 0; color: var(--muted); border-top: 1px solid var(--line); font-size: 13px; }
.screen-line b { color: var(--text); }

.audio-event-panel { min-width: 0; }
.audio-event-title { align-items: center; }
.audio-event-title > div { display: grid; gap: 3px; }
.audio-event-table { min-width: 1150px; }
.audio-event-table td { vertical-align: middle; }
.audio-event-table td:nth-child(2) { min-width: 125px; }
.audio-event-table td:nth-child(2) small,
.audio-event-table td:nth-child(4) small { display: block; margin-top: 4px; color: var(--muted); font-family: Consolas, monospace; font-size: 11px; }
.audio-event-table td .audio-research-result { max-width: 210px; color: var(--gold); font-family: inherit; white-space: normal; overflow-wrap: anywhere; }
.audio-event-table audio { display: block; width: 190px; height: 32px; }
.review-fields { display: grid; grid-template-columns: 112px 112px minmax(130px, 1fr); gap: 6px; min-width: 400px; }
.review-fields select, .review-fields input { min-width: 0; height: 32px; padding: 0 8px; color: var(--ink); border: 1px solid var(--line); border-radius: 4px; outline: none; background: #111813; font-size: 12px; }
.review-fields select { color-scheme: dark; }
.review-fields input::placeholder { color: #8b887b; }
.review-fields select:focus, .review-fields input:focus { border-color: var(--green); }
.clinical-signoff { min-width: 400px; margin-top: 7px; color: var(--muted); font-size: 12px; }
.clinical-signoff summary { cursor: pointer; color: var(--gold); }
.clinical-signoff-grid { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 6px; margin-top: 7px; }
.clinical-signoff-grid label { display: flex; align-items: center; gap: 6px; min-height: 32px; }
.clinical-signoff-grid input:not([type='checkbox']) { min-width: 0; height: 32px; padding: 0 8px; color: var(--ink); border: 1px solid var(--line); border-radius: 4px; outline: none; background: rgba(248, 242, 223, .06); font-size: 12px; }
.clinical-signoff-grid input:focus { border-color: var(--green); }
.audio-empty-state { display: flex; align-items: center; gap: 10px; min-height: 125px; padding: 16px; color: var(--muted); border: 1px dashed var(--line); }
.audio-empty-state svg { color: var(--gold); }
.audio-boundary { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; color: #d5ddd7; border-left: 3px solid var(--gold); background: rgba(229, 184, 92, .08); }
.audio-boundary svg { flex: 0 0 auto; margin-top: 2px; color: var(--gold); }
.audio-boundary p { margin: 0; line-height: 1.55; }

@media (max-width: 1180px) {
  .audio-livebar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .audio-live-stat { border-top: 1px solid var(--line); }
  .audio-capture-button { justify-self: stretch; }
  .audio-metric-grid { grid-template-columns: 1fr; }
}

@media (max-width: 680px) {
  .audio-livebar { grid-template-columns: 1fr; }
  .audio-live-stat { border-left: 0; }
  .audio-capture-button { margin: 8px 14px 14px; }
  .audio-model-readout { grid-template-columns: 48px minmax(0, 1fr); }
  .audio-model-readout b { grid-column: 1 / -1; }
}
</style>
