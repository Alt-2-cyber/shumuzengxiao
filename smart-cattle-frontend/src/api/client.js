import axios from 'axios'

export const api = axios.create({
  baseURL: '/api',
  timeout: 10000
})

// Only used when the deployment enables the optional backend API-key gate.
// Local commissioning remains keyless by default; production should prefer a
// TLS identity proxy over exposing a browser-held shared secret.
const browserApiKey = import.meta.env.VITE_API_KEY
if (browserApiKey) {
  api.defaults.headers.common.Authorization = `Bearer ${browserApiKey}`
}

export async function getDashboard() {
  const { data } = await api.get('/dashboard')
  return data
}

export async function getEnvironmentTrend() {
  const { data } = await api.get('/environment/trend')
  return data
}

export async function getDevices() {
  const { data } = await api.get('/devices')
  return data
}

export async function sendCommand(payload) {
  const { data } = await api.post('/devices/command', payload)
  return data
}

export async function getCommandHistory() {
  const { data } = await api.get('/devices/commands')
  return data
}

export async function getVisionEvents() {
  const { data } = await api.get('/events/vision')
  return data
}

export async function getVisionSnapshot(snapshotPath) {
  const endpoint = String(snapshotPath || '').replace(/^\/api(?=\/)/, '')
  const { data } = await api.get(endpoint, { responseType: 'blob' })
  return data
}

export async function reviewVisionEvent(eventId, payload) {
  const { data } = await api.put(`/events/vision/${eventId}/review`, payload)
  return data
}

export async function getVisionTrainingLineage(eventId) {
  const { data } = await api.get(`/events/vision/${eventId}/training-lineage`)
  return data
}

export async function getAudioEvents() {
  const { data } = await api.get('/events/audio')
  return data
}

export async function getAudioClip(audioClipPath) {
  const endpoint = String(audioClipPath || '').replace(/^\/api(?=\/)/, '')
  const { data } = await api.get(endpoint, { responseType: 'blob' })
  return data
}

export async function getAudioResearch(audioClipPath) {
  const endpoint = String(audioClipPath || '').replace(/^\/api(?=\/)/, '')
  const { data } = await api.get(`${endpoint}/research`)
  return data
}

export async function reviewAudioEvent(eventId, payload) {
  const { data } = await api.put(`/events/audio/${eventId}/review`, payload)
  return data
}

export async function getHealthRisks() {
  const { data } = await api.get('/events/health-risks')
  return data
}

export async function getModels() {
  const { data } = await api.get('/models')
  return data
}

export async function getTelemetrySnapshot(limit = 60) {
  const { data } = await api.get('/telemetry/snapshot', { params: { limit } })
  return data
}

export async function getClinicalChecks(cattleId) {
  const { data } = await api.get('/clinical-checks', { params: cattleId ? { cattleId } : {} })
  return data
}

export async function createClinicalCheck(payload) {
  const { data } = await api.post('/clinical-checks', payload)
  return data
}

export async function getMotionCaptures(cattleId) {
  const { data } = await api.get('/motion-captures', { params: cattleId ? { cattleId } : {} })
  return data
}

export async function getMotionCaptureRaw(sessionId) {
  const { data } = await api.get(`/motion-captures/${encodeURIComponent(sessionId)}/raw`, {
    responseType: 'blob'
  })
  return data
}

export async function getMotionCaptureTrainingLineage(sessionId) {
  const { data } = await api.get(`/motion-captures/${encodeURIComponent(sessionId)}/training-lineage`)
  return data
}

export async function reviewMotionCaptureClinical(sessionId, payload) {
  const { data } = await api.put(`/motion-captures/${encodeURIComponent(sessionId)}/clinical-review`, payload)
  return data
}

export async function startMotionCapture(payload) {
  const { data } = await api.post('/motion-captures', payload)
  return data
}

export async function getFmdTriageCases(cattleId) {
  const { data } = await api.get('/fmd-triage-cases', { params: cattleId ? { cattleId } : {} })
  return data
}

export async function openFmdTriageCase(payload) {
  const { data } = await api.post('/fmd-triage-cases', payload)
  return data
}

export async function addFmdTriageAction(caseId, payload) {
  const { data } = await api.post(`/fmd-triage-cases/${caseId}/actions`, payload)
  return data
}

export async function getAuditRecords(targetType, targetId) {
  const { data } = await api.get('/audit-records', { params: targetType && targetId ? { targetType, targetId } : {} })
  return data
}

export async function getModelReleases() {
  const { data } = await api.get('/model-releases')
  return data
}
