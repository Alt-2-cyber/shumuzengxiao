<template>
  <div class="vision-page grid page-stack">
    <section class="vision-livebar">
      <div class="vision-live-identity">
        <span class="vision-live-dot"></span>
        <div>
          <strong>视觉证据归档</strong>
          <span>MaixCam · barn_01 · 原图和复核记录可追溯</span>
        </div>
      </div>
      <div class="vision-live-stat">
        <Camera :size="17" />
        <span>{{ events.length }} 条事件</span>
      </div>
      <div class="vision-live-stat">
        <ShieldCheck :size="17" />
        <span>{{ clinicallyVerifiedCount }} 条已签核</span>
      </div>
      <button class="icon-button" title="刷新视觉事件" @click="loadEvents">
        <RefreshCcw :size="18" />
      </button>
    </section>

    <div v-if="error" class="error-banner">{{ error }}</div>

    <section class="vision-summary-grid">
      <article class="card pad vision-summary-card">
        <div class="summary-icon summary-camera"><Camera :size="21" /></div>
        <span>视觉事件</span>
        <strong>{{ events.length }}</strong>
        <small>最近 20 条服务端归档</small>
      </article>
      <article class="card pad vision-summary-card">
        <div class="summary-icon summary-review"><ClipboardCheck :size="21" /></div>
        <span>临床复核</span>
        <strong>{{ reviewedCount }} / {{ events.length }}</strong>
        <small>confirmed、normal 或已排除</small>
      </article>
      <article class="card pad vision-summary-card">
        <div class="summary-icon summary-integrity"><ShieldCheck :size="21" /></div>
        <span>原图完整性</span>
        <strong>{{ archivedCount }}</strong>
        <small>已归档并可重新计算 SHA-256</small>
      </article>
      <article class="card pad vision-summary-card">
        <div class="summary-icon summary-risk"><TriangleAlert :size="21" /></div>
        <span>病灶/步态候选</span>
        <strong>{{ candidateCount }}</strong>
        <small>仍需兽医检查，不是疾病确诊</small>
      </article>
    </section>

    <section class="card pad vision-event-panel">
      <div class="section-title vision-panel-title">
        <div>
          <h2>截图、模型与临床复核</h2>
          <span class="muted">只有完整复核的真实视觉档案才能进入训练血缘</span>
        </div>
        <span v-if="loading" class="muted">加载中...</span>
      </div>

      <div v-if="events.length" class="table-scroll">
        <table class="table vision-event-table">
          <thead>
            <tr>
              <th>截图</th>
              <th>事件与对象</th>
              <th>模型状态</th>
              <th>归档完整性</th>
              <th>临床复核</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="event in events" :key="event.id">
              <td>
                <div class="vision-thumb">
                  <img v-if="snapshotUrls[event.id]" :src="snapshotUrls[event.id]" alt="视觉事件截图">
                  <div v-else class="snapshot-placeholder">
                    <Camera :size="20" />
                    <span>{{ event.snapshotAvailable ? '加载中' : '摄像头原图未上传' }}</span>
                  </div>
                </div>
                <small class="vision-time">{{ formatFullTime(event.recordedAt) }}</small>
              </td>
              <td class="vision-event-cell">
                <strong>{{ eventLabel(event.reviewLabel || event.eventType) }}</strong>
                <small>{{ event.eventType }} · {{ event.targetId || '未绑定真实牛只' }}</small>
                <span v-if="event.evidence" class="vision-evidence">{{ evidenceText(event.evidence) }}</span>
                <span class="score-line">置信度 {{ percent(event.score) }}</span>
              </td>
              <td>
                <span class="state-pill" :class="modelStateClass(event)">{{ modelStateLabel(event) }}</span>
                <small class="vision-mono">{{ event.modelVersion || '未上报版本' }}</small>
                <small>{{ event.modelApprovedByServer ? '服务端批准' : '仅归档/待批准' }}</small>
              </td>
              <td>
                <span class="state-pill" :class="event.snapshotAvailable ? 'state-good' : 'state-muted'">
                  {{ event.snapshotAvailable ? '已归档' : '待上传原图' }}
                </span>
                <small class="vision-mono hash-text">{{ shortHash(event.snapshotSha256) }}</small>
                <small>{{ event.snapshotBytes ? `${event.snapshotBytes} bytes` : '不可用于训练' }}</small>
              </td>
              <td class="vision-review-cell">
                <div class="review-fields vision-review-fields">
                  <select v-model="reviewDraft(event).status" aria-label="视觉复核状态">
                    <option value="pending">待复核</option>
                    <option value="confirmed">确认候选</option>
                    <option value="rejected">排除</option>
                    <option value="normal">正常</option>
                  </select>
                  <select v-model="reviewDraft(event).label" aria-label="视觉标签">
                    <option value="normal">正常</option>
                    <option value="gait_abnormal_suspect">步态异常候选</option>
                    <option value="hoof_lesion_suspect">蹄部病灶候选</option>
                    <option value="oral_lesion_suspect">口鼻病灶候选</option>
                    <option value="nasal_discharge_suspect">鼻部分泌物候选</option>
                    <option value="fall_suspect">倒地/久卧候选</option>
                    <option value="person_enter">人员进入</option>
                    <option value="snapshot_event">普通抓拍</option>
                  </select>
                  <input v-model.trim="reviewDraft(event).note" maxlength="1200" placeholder="复核备注" aria-label="视觉复核备注">
                </div>
                <details class="clinical-signoff">
                  <summary>{{ event.clinicallyVerifiedAt ? `兽医签核 ${formatFullTime(event.clinicallyVerifiedAt)}` : '兽医临床签核（训练必填）' }}</summary>
                  <div class="clinical-signoff-grid">
                    <label><input v-model="reviewDraft(event).clinicallyVerified" type="checkbox"> 临床签核</label>
                    <input v-model.trim="reviewDraft(event).animalId" maxlength="120" placeholder="真实耳标/管理编号" aria-label="真实耳标或管理编号">
                    <input v-model.trim="reviewDraft(event).veterinarian" maxlength="80" placeholder="兽医姓名或工号" aria-label="兽医姓名或工号">
                    <input v-model.trim="reviewDraft(event).clinicalEvidenceReference" maxlength="1200" placeholder="病例、蹄检或实验室证据编号" aria-label="临床证据编号">
                  </div>
                </details>
                <div class="vision-row-actions">
                  <span class="review-status">{{ reviewStatusLabel(event.reviewStatus) }}</span>
                  <button class="icon-button" title="重新验证视觉训练血缘" :disabled="lineageLoading === event.id" @click="loadLineage(event)">
                    <GitBranch :size="17" />
                  </button>
                  <button class="icon-button" title="保存视觉复核" :disabled="savingEventId === event.id" @click="saveReview(event)">
                    <Save :size="18" />
                  </button>
                </div>
                <div v-if="lineages[event.id]" class="lineage-result">
                  <span>血缘：{{ lineages[event.id].snapshotIntegrityVerified ? '完整' : '失败' }}</span>
                  <span>{{ lineages[event.id].reviewStatus || 'pending' }} · {{ lineages[event.id].reviewLabel || '未标注' }}</span>
                </div>
              </td>
              <td></td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else class="vision-empty-state">
        <Camera :size="23" />
        <span>尚无视觉事件。MaixCam 上报截图或病灶/步态候选后，会在这里归档和复核。</span>
      </div>
    </section>

    <section class="vision-boundary">
      <BadgeInfo :size="19" />
      <p>当前 MaixCam 模型只具备牛只检测能力。口蹄疫不能由摄像头单独确诊；平台只有在经批准的口鼻/蹄部视觉候选、三位置跛行候选和 24 小时内人工核心体温异常同时满足时，才建立 <code>fmd_suspect_triage</code> 分诊，最终必须由兽医、主管部门和法定实验室确认。</p>
    </section>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from 'vue'
import {
  BadgeInfo,
  Camera,
  ClipboardCheck,
  GitBranch,
  RefreshCcw,
  Save,
  ShieldCheck,
  TriangleAlert
} from 'lucide-vue-next'
import {
  getVisionEvents,
  getVisionSnapshot,
  getVisionTrainingLineage,
  reviewVisionEvent
} from '../api/client'
import { eventLabel, formatFullTime, percent } from '../utils/format'

const events = ref([])
const loading = ref(false)
const error = ref('')
const savingEventId = ref(null)
const lineageLoading = ref(null)
const drafts = reactive({})
const snapshotUrls = reactive({})
const lineages = reactive({})
let refreshTimer

const reviewedCount = computed(() => events.value.filter((event) => ['confirmed', 'normal', 'rejected'].includes(event.reviewStatus)).length)
const clinicallyVerifiedCount = computed(() => events.value.filter((event) => Boolean(event.clinicallyVerifiedAt)).length)
const archivedCount = computed(() => events.value.filter((event) => event.snapshotAvailable).length)
const candidateCount = computed(() => events.value.filter((event) => [
  'gait_abnormal_suspect',
  'hoof_lesion_suspect',
  'oral_lesion_suspect',
  'nasal_discharge_suspect'
].includes(event.eventType)).length)

function reviewDraft(event) {
  const key = String(event.id)
  if (!drafts[key]) {
    drafts[key] = {
      status: event.reviewStatus || 'pending',
      label: event.reviewLabel || event.eventType || 'normal',
      note: event.reviewNote || '',
      clinicallyVerified: Boolean(event.clinicallyVerifiedAt),
      animalId: event.clinicalAnimalId || '',
      veterinarian: event.veterinarian || '',
      clinicalEvidenceReference: event.clinicalEvidenceReference || ''
    }
  }
  return drafts[key]
}

async function loadSnapshot(event) {
  if (!event?.id || !event.snapshotAvailable || !event.snapshotPath || snapshotUrls[event.id]) return
  try {
    snapshotUrls[event.id] = URL.createObjectURL(await getVisionSnapshot(event.snapshotPath))
  } catch {
    // Metadata remains useful when the viewer is not authorized to read the original.
  }
}

async function loadEvents() {
  loading.value = true
  error.value = ''
  try {
    events.value = await getVisionEvents()
    await Promise.all(events.value.map(loadSnapshot))
  } catch (loadError) {
    error.value = loadError?.response?.data?.message || loadError?.message || '无法读取视觉事件'
  } finally {
    loading.value = false
  }
}

async function saveReview(event) {
  const draft = reviewDraft(event)
  if (draft.clinicallyVerified && (!draft.animalId || !draft.veterinarian || !draft.clinicalEvidenceReference)) {
    window.alert('视觉临床签核需要真实耳标、兽医和临床证据编号。')
    return
  }
  savingEventId.value = event.id
  try {
    await reviewVisionEvent(event.id, { ...draft, reviewer: '现场复核' })
    await loadEvents()
  } catch (saveError) {
    window.alert(saveError?.response?.data?.message || saveError?.message || '保存视觉复核失败')
  } finally {
    savingEventId.value = null
  }
}

async function loadLineage(event) {
  lineageLoading.value = event.id
  try {
    lineages[event.id] = await getVisionTrainingLineage(event.id)
  } catch (lineageError) {
    lineages[event.id] = { snapshotIntegrityVerified: false, reviewStatus: lineageError?.response?.data?.message || '验证失败' }
  } finally {
    lineageLoading.value = null
  }
}

function modelStateClass(event) {
  if (event.modelApprovedByServer && event.modelStatus === 'deployed') return 'state-good'
  if (event.modelStatus === 'feature_only' || !event.modelStatus) return 'state-muted'
  return 'state-warn'
}

function modelStateLabel(event) {
  if (event.modelApprovedByServer && event.modelStatus === 'deployed') return '已批准'
  if (event.modelStatus === 'deployed') return '未批准'
  return '特征/归档'
}

function reviewStatusLabel(value) {
  return ({ pending: '待复核', confirmed: '已确认候选', rejected: '已排除', normal: '正常' }[value] || '待复核')
}

function shortHash(value) {
  if (!value) return '无 SHA-256'
  return `${value.slice(0, 12)}...${value.slice(-8)}`
}

function evidenceText(value) {
  if (!value) return ''
  try {
    const parsed = JSON.parse(value)
    return parsed.message || parsed.approvalReason || ''
  } catch {
    return value
  }
}

onMounted(() => {
  loadEvents()
  refreshTimer = window.setInterval(loadEvents, 10000)
})

onBeforeUnmount(() => {
  window.clearInterval(refreshTimer)
  Object.values(snapshotUrls).forEach((url) => URL.revokeObjectURL(url))
})
</script>

<style scoped>
.vision-page { min-width: 0; }
.vision-livebar { display: grid; grid-template-columns: minmax(280px, 1fr) repeat(2, minmax(150px, .35fr)) auto; align-items: center; min-height: 68px; border: 1px solid rgba(248, 242, 223, .16); border-left: 3px solid var(--blue); background: rgba(12, 18, 14, .76); }
.vision-live-identity, .vision-live-stat { display: flex; align-items: center; min-width: 0; gap: 10px; padding: 12px 16px; }
.vision-live-identity > div { display: grid; min-width: 0; gap: 3px; }
.vision-live-identity span:not(.vision-live-dot) { overflow: hidden; color: var(--muted); font-size: 13px; text-overflow: ellipsis; white-space: nowrap; }
.vision-live-stat { min-height: 42px; color: var(--muted); border-left: 1px solid var(--line); font-size: 13px; }
.vision-live-dot { flex: 0 0 auto; width: 9px; height: 9px; border-radius: 50%; background: var(--blue); box-shadow: 0 0 0 6px rgba(124, 183, 255, .12); }
.vision-summary-grid { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 14px; }
.vision-summary-card { min-width: 0; min-height: 145px; }
.vision-summary-card > span, .vision-summary-card > strong, .vision-summary-card > small { display: block; }
.vision-summary-card > span { margin-top: 14px; color: var(--muted); font-size: 13px; }
.vision-summary-card > strong { margin-top: 6px; font-size: 26px; font-variant-numeric: tabular-nums; }
.vision-summary-card > small { margin-top: 5px; color: var(--muted); font-size: 11px; }
.summary-icon { display: grid; width: 38px; height: 38px; place-items: center; color: var(--blue); border: 1px solid rgba(124, 183, 255, .28); background: rgba(124, 183, 255, .08); }
.summary-review { color: var(--green); border-color: rgba(142, 240, 160, .28); background: rgba(142, 240, 160, .08); }
.summary-integrity { color: var(--gold); border-color: rgba(229, 184, 92, .28); background: rgba(229, 184, 92, .08); }
.summary-risk { color: var(--red); border-color: rgba(255, 110, 87, .28); background: rgba(255, 110, 87, .08); }
.vision-event-panel { min-width: 0; }
.vision-panel-title { align-items: center; }
.vision-panel-title > div { display: grid; gap: 3px; min-width: 0; }
.vision-event-table { min-width: 1420px; }
.vision-event-table td { vertical-align: top; }
.vision-thumb { display: grid; width: 144px; height: 96px; overflow: hidden; place-items: center; border: 1px solid var(--line); background: #0d130f; }
.vision-thumb img { width: 100%; height: 100%; object-fit: cover; }
.snapshot-placeholder { display: grid; place-items: center; gap: 5px; color: var(--muted); font-size: 11px; }
.snapshot-placeholder svg { color: var(--blue); }
.vision-time { display: block; margin-top: 6px; color: var(--muted); font-size: 11px; }
.vision-event-cell { min-width: 210px; }
.vision-event-cell strong, .vision-event-cell small, .vision-event-cell span { display: block; }
.vision-event-cell strong { font-family: "Noto Serif SC", serif; font-size: 16px; }
.vision-event-cell small { margin-top: 5px; color: var(--muted); font-size: 11px; }
.vision-evidence { max-width: 230px; margin-top: 8px; color: #d5ddd7; font-size: 12px; line-height: 1.4; }
.score-line { margin-top: 9px; color: var(--gold); font-size: 12px; font-variant-numeric: tabular-nums; }
.state-pill { display: inline-flex; width: max-content; padding: 4px 7px; border: 1px solid rgba(248, 242, 223, .14); background: rgba(248, 242, 223, .05); color: var(--muted); font-size: 12px; white-space: nowrap; }
.state-pill.state-good { color: var(--green); border-color: rgba(142, 240, 160, .28); background: rgba(142, 240, 160, .08); }
.state-pill.state-warn { color: var(--gold); border-color: rgba(229, 184, 92, .30); background: rgba(229, 184, 92, .08); }
.state-pill.state-muted { color: var(--muted); }
.vision-event-table td small { display: block; margin-top: 6px; color: var(--muted); font-size: 11px; }
.vision-mono { font-family: Consolas, monospace; }
.hash-text { max-width: 150px; overflow-wrap: anywhere; }
.vision-review-cell { min-width: 570px; }
.vision-review-fields { display: grid; grid-template-columns: 112px 170px minmax(180px, 1fr); gap: 6px; min-width: 520px; }
.vision-review-fields select, .vision-review-fields input, .clinical-signoff-grid input:not([type='checkbox']) { min-width: 0; height: 32px; padding: 0 8px; color: var(--ink); border: 1px solid var(--line); border-radius: 4px; outline: none; background: #111813; font-size: 12px; }
.vision-review-fields select { color-scheme: dark; }
.vision-review-fields select:focus, .vision-review-fields input:focus, .clinical-signoff-grid input:focus { border-color: var(--green); }
.vision-row-actions { display: flex; align-items: center; gap: 8px; margin-top: 8px; }
.review-status { margin-right: auto; color: var(--muted); font-size: 12px; }
.lineage-result { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 7px; padding: 7px 9px; color: var(--muted); border-left: 2px solid var(--gold); background: rgba(229, 184, 92, .07); font-size: 11px; }
.vision-empty-state { display: flex; align-items: center; gap: 10px; min-height: 125px; padding: 16px; color: var(--muted); border: 1px dashed var(--line); }
.vision-empty-state svg { color: var(--blue); }
.vision-boundary { display: flex; align-items: flex-start; gap: 10px; padding: 12px 14px; color: #d5ddd7; border-left: 3px solid var(--gold); background: rgba(229, 184, 92, .08); }
.vision-boundary svg { flex: 0 0 auto; margin-top: 2px; color: var(--gold); }
.vision-boundary p { margin: 0; line-height: 1.55; }
.vision-boundary code { color: var(--gold); font-family: Consolas, monospace; }
@media (max-width: 1180px) {
  .vision-livebar { grid-template-columns: repeat(2, minmax(0, 1fr)); }
  .vision-live-stat { border-top: 1px solid var(--line); }
  .vision-summary-grid { grid-template-columns: repeat(2, minmax(0, 1fr)); }
}
@media (max-width: 680px) {
  .vision-livebar { grid-template-columns: 1fr; }
  .vision-live-stat { border-left: 0; }
  .vision-summary-grid { grid-template-columns: 1fr; }
  .vision-thumb { width: 118px; height: 80px; }
}
</style>
