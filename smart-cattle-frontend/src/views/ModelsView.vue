<template>
  <div class="grid page-stack">
    <section class="grid cols-3">
      <article v-for="model in models" :key="model.name" class="card pad model-card">
        <div class="model-head">
          <BrainCircuit :size="24" />
          <div>
            <strong>{{ model.name }}</strong>
            <span>{{ model.version }} / {{ model.device }}</span>
          </div>
        </div>
        <div class="model-meta-row">
          <span class="model-status" :class="`status-${model.status || 'unknown'}`">
            {{ model.statusLabel || model.status || '状态未知' }}
          </span>
          <span v-if="model.scope" class="model-scope">{{ model.scope }}</span>
        </div>
        <p>{{ model.task }}</p>
        <p v-if="model.metricsNote" class="model-metric-note">{{ model.metricsNote }}</p>
        <div v-if="model.releaseReasons?.length" class="model-gate">
          <span class="model-gate-label">发布门禁 · {{ model.releaseState === 'research_only' ? '仅研究' : model.releaseState === 'triage_only' ? '仅分诊' : '未就绪' }}</span>
          <ul>
            <li v-for="reason in model.releaseReasons" :key="reason">{{ reason }}</li>
          </ul>
        </div>
        <div v-if="model.metricsAvailable !== false" class="model-metrics">
          <div>
            <span>{{ model.primaryMetricLabel || 'Precision' }}</span>
            <strong>{{ percent(model.primaryMetric ?? model.precision) }}</strong>
          </div>
          <div>
            <span>{{ model.secondaryMetricLabel || 'Recall' }}</span>
            <strong>{{ percent(model.secondaryMetric ?? model.recall) }}</strong>
          </div>
        </div>
        <div v-else class="model-metrics">
          <div>
            <span>评估状态</span>
            <strong>{{ model.metricsStatus || '未标定' }}</strong>
          </div>
          <div>
            <span>性能指标</span>
            <strong>待独立验证</strong>
          </div>
        </div>
      </article>
    </section>

    <section class="card pad release-ledger">
      <div class="section-title release-title">
        <div>
          <h2>疾病筛查发布账本</h2>
          <span class="muted">{{ releasesError || `${releases.length} 个服务端发布记录` }}</span>
        </div>
        <button class="icon-button" title="刷新发布账本" :disabled="releasesLoading" @click="loadReleases">
          <RefreshCw :size="18" :class="{ spinning: releasesLoading }" />
        </button>
      </div>

      <div v-if="!releasesError && releases.length" class="table-scroll">
        <table class="table release-table">
          <thead>
            <tr>
              <th>模型</th>
              <th>状态</th>
              <th>源血缘指纹</th>
              <th>批准</th>
              <th>撤回</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="release in releases" :key="release.id">
              <td>
                <strong>{{ release.modelVersion }}</strong>
                <small>{{ familyLabel(release.modelFamily) }}</small>
              </td>
              <td>
                <span class="release-state" :class="`state-${release.approvalState}`">
                  {{ releaseStateLabel(release.approvalState) }}
                </span>
              </td>
              <td>
                <code :title="release.sourceLineageSha256 || '旧版记录未保留源血缘指纹'">
                  {{ shortHash(release.sourceLineageSha256) }}
                </code>
              </td>
              <td>
                <span>{{ formatTime(release.approvedAt) }}</span>
                <small>{{ release.approvedBy || '-' }} · {{ release.evidenceReference || '-' }}</small>
              </td>
              <td>
                <template v-if="release.revokedAt">
                  <span>{{ formatTime(release.revokedAt) }}</span>
                  <small>{{ release.revokedBy || '-' }} · {{ release.revocationEvidenceReference || '-' }}</small>
                </template>
                <span v-else class="muted">-</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-else-if="!releasesError" class="release-empty">暂无发布记录</div>
    </section>

    <section class="grid cols-2">
      <article class="card pad">
        <div class="section-title">
          <h2>AI 训练流程</h2>
          <span class="muted">开源模型 + 自采数据优化</span>
        </div>
        <div class="pipeline">
          <div v-for="step in trainingSteps" :key="step.title" class="pipeline-step">
            <span>{{ step.index }}</span>
            <div>
              <strong>{{ step.title }}</strong>
              <p>{{ step.text }}</p>
            </div>
          </div>
        </div>
      </article>

      <article class="card pad">
        <div class="section-title">
          <h2>边缘部署策略</h2>
          <span class="muted">MaixCam / ESP32-S3 / 后端融合</span>
        </div>
        <div class="deploy-grid">
          <div>
            <strong>视觉端</strong>
            <p>当前已部署可运行的 COCO YOLOv8n，仅检测 cow 目标；姿态、跛行和病灶模型需要另行采集标注与验证。</p>
          </div>
          <div>
            <strong>声音端</strong>
            <p>当前仅输出异常发声候选；需以人工或兽医标注音频训练后，才能报告咳嗽、喘鸣分类结果。</p>
          </div>
          <div>
            <strong>平台端</strong>
            <p>Spring Boot 汇聚环境、声音、视觉和历史趋势，形成健康风险等级与复核建议。</p>
          </div>
        </div>
      </article>
    </section>

    <section class="card pad">
      <div class="section-title">
        <h2>模型落地检查表</h2>
        <span class="muted">用于项目验收</span>
      </div>
      <table class="table">
        <thead>
          <tr>
            <th>模块</th>
            <th>开源基线</th>
            <th>自优化方向</th>
            <th>部署目标</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td>牛体与姿态检测</td>
            <td>MaixCAM cattle-yolov8-coco-v1（仅 cow）</td>
            <td>自采牛舍俯视/侧视图，标注站立、卧倒、跛行、采食</td>
            <td>牛只框选已启用；姿态和疾病类别待独立模型</td>
          </tr>
          <tr>
            <td>皮肤与眼鼻异常</td>
            <td>YOLO 分区检测 + MobileNet 分类</td>
            <td>局部裁剪增强，低光照、遮挡、污渍样本扩充</td>
            <td>视觉节点输出局部异常候选</td>
          </tr>
          <tr>
            <td>声音疾病筛查</td>
            <td>异常发声候选（当前）</td>
            <td>采集牛舍音频并经人工/兽医标注后，训练咳嗽、喘鸣、异常叫声分类器</td>
            <td>当前后端保留证据；训练验证后再部署轻量推理</td>
          </tr>
          <tr>
            <td>健康融合判断</td>
            <td>个体基线规则筛查（当前）</td>
            <td>按同一牛只历史趋势建立基线；使用疾病/兽医结局标注进行独立校准</td>
            <td>后端生成非诊断风险等级和证据链</td>
          </tr>
        </tbody>
      </table>
    </section>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { BrainCircuit, RefreshCw } from 'lucide-vue-next'
import { getModelReleases, getModels } from '../api/client'
import { percent } from '../utils/format'

const models = ref([])
const releases = ref([])
const releasesError = ref('')
const releasesLoading = ref(false)
const trainingSteps = [
  { index: '01', title: '采集与同步', text: '按时间戳同步环境、视觉截图、声音片段和人工复核结果，形成可追溯样本。' },
  { index: '02', title: '标注与清洗', text: '使用 CVAT/Label Studio 标注牛体框、姿态、眼鼻皮肤局部和声音事件类别。' },
  { index: '03', title: '开源基线训练', text: '以 YOLO Nano、MobileNet、轻量 CNN 作为基线，先跑通训练、验证、导出链路。' },
  { index: '04', title: '边缘量化部署', text: '进行 INT8/FP16 量化和输入尺寸裁剪，导出 MaixCam 可加载模型。' },
  { index: '05', title: '现场闭环优化', text: '把误报漏报样本回流训练集，按牛舍光照、遮挡和噪声条件迭代阈值。' }
]

async function loadModels() {
  models.value = await getModels()
}

async function loadReleases() {
  releasesLoading.value = true
  releasesError.value = ''
  try {
    releases.value = await getModelReleases()
  } catch (error) {
    releases.value = []
    const status = error?.response?.status
    releasesError.value = status === 401 || status === 403
      ? '需要管理员权限'
      : '发布账本暂不可用'
  } finally {
    releasesLoading.value = false
  }
}

function familyLabel(family) {
  return family === 'audio' ? '声音筛查' : family === 'lameness' ? '跛行筛查' : family || '-'
}

function releaseStateLabel(state) {
  return state === 'approved' ? '已批准' : state === 'revoked' ? '已撤回' : state || '-'
}

function shortHash(value) {
  const hash = String(value || '')
  return hash.length === 64 ? `${hash.slice(0, 12)}...${hash.slice(-8)}` : '-'
}

function formatTime(value) {
  if (!value) return '-'
  const time = new Date(value)
  return Number.isNaN(time.getTime()) ? '-' : time.toLocaleString('zh-CN', { hour12: false })
}

onMounted(async () => {
  await Promise.all([loadModels(), loadReleases()])
})
</script>

<style scoped>
.model-meta-row { display: flex; align-items: center; flex-wrap: wrap; gap: 7px; margin: 16px 0 2px; }
.model-status, .model-scope { display: inline-flex; width: max-content; padding: 4px 7px; border: 1px solid rgba(229, 184, 92, .28); background: rgba(229, 184, 92, .08); color: var(--gold); font-size: 11px; }
.model-status.status-deployed { border-color: rgba(142, 240, 160, .28); background: rgba(142, 240, 160, .08); color: var(--green); }
.model-status.status-feature_only,
.model-status.status-not_trained { border-color: rgba(248, 242, 223, .14); background: rgba(248, 242, 223, .05); color: var(--muted); }
.model-status.status-triage_only { border-color: rgba(229, 184, 92, .3); background: rgba(229, 184, 92, .08); color: var(--gold); }
.model-status.status-screening_only { border-color: rgba(124, 183, 255, .25); background: rgba(124, 183, 255, .08); color: var(--blue); }
.model-scope { color: var(--muted); border-color: var(--line); background: transparent; }
.model-gate { margin: 14px 0 0; padding: 10px; border-left: 2px solid var(--gold); background: rgba(229, 184, 92, .06); color: var(--muted); font-size: 12px; line-height: 1.45; }
.model-gate-label { color: var(--gold); font-weight: 800; }
.model-gate ul { margin: 6px 0 0; padding-left: 16px; }
.model-gate li + li { margin-top: 3px; }
.release-ledger { min-width: 0; }
.release-title { align-items: center; }
.release-title > div { display: grid; gap: 3px; }
.release-table { min-width: 920px; }
.release-table td { vertical-align: middle; }
.release-table td:first-child { min-width: 190px; }
.release-table strong, .release-table span, .release-table small { display: block; }
.release-table small { margin-top: 4px; color: var(--muted); font-size: 11px; overflow-wrap: anywhere; }
.release-table code { color: var(--blue); font-family: Consolas, monospace; font-size: 12px; }
.release-state { display: inline-flex !important; width: max-content; padding: 4px 7px; border: 1px solid rgba(229, 184, 92, .28); background: rgba(229, 184, 92, .08); color: var(--gold); font-size: 12px; }
.release-state.state-approved { border-color: rgba(142, 240, 160, .3); background: rgba(142, 240, 160, .08); color: var(--green); }
.release-state.state-revoked { border-color: rgba(255, 110, 87, .32); background: rgba(255, 110, 87, .08); color: var(--red); }
.release-empty { padding: 24px 0 6px; color: var(--muted); font-size: 13px; }
.spinning { animation: spin .8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }
</style>
