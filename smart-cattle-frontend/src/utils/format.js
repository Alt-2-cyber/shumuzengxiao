export const severityOrder = {
  NORMAL: 0,
  OBSERVE: 1,
  WARNING: 2,
  URGENT: 3
}

export function formatTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit'
  }).format(new Date(value))
}

export function formatFullTime(value) {
  if (!value) return '-'
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  }).format(new Date(value))
}

export function percent(value) {
  if (value === null || value === undefined) return '-'
  return `${Math.round(Number(value) * 100)}%`
}

export function fixed(value, digits = 1, unit = '') {
  if (value === null || value === undefined || Number.isNaN(Number(value))) return '-'
  return `${Number(value).toFixed(digits)}${unit}`
}

export function eventLabel(value) {
  return {
    fall_suspect: '疑似倒地/久卧',
    nasal_discharge_suspect: '鼻部分泌物疑似',
    skin_lesion_suspect: '皮肤异常疑似',
    cough_suspect: '咳嗽疑似',
    wheeze_suspect: '喘鸣疑似',
    abnormal_vocalization_suspect: '异常鸣叫疑似',
    normal_moo: '正常叫声',
    none: '暂无候选',
    untrained: '未训练',
    acoustic_candidate: '声学异常候选',
    manual_capture: '人工采样',
    barn_noise: '牛舍背景声',
    respiratory_sound_attention: '呼吸异常声音关注',
    abnormal_vocalization_attention: '异常鸣叫/发声关注',
    brd_suspect: '牛呼吸道疾病疑似（BRD）',
    lameness_suspect: '跛行/蹄病疑似',
    fmd_suspect_triage: '口蹄疫疑似事件分诊',
    gait_abnormal_suspect: '步态异常疑似',
    hoof_lesion_suspect: '蹄部病灶疑似',
    oral_lesion_suspect: '口鼻病灶疑似',
    respiratory_risk: '呼吸道风险',
    low_activity_risk: '活动量偏低',
    feeding_rumination_attention: '采食/反刍下降关注',
    mobility_activity_attention: '活动/运动异常关注',
    temperature_inflammation_attention: '体温/炎症关注',
    vocalization_attention: '异常发声关注'
  }[value] || value || '-'
}

export function healthRiskLabel(value) {
  return eventLabel(value)
}

export function deviceTypeLabel(value) {
  return {
    environment: '环境采集',
    vision: '视觉 AI',
    audio: '声音采集',
    actuator: '执行器'
  }[value] || value || '-'
}

export function statusLabel(value) {
  return {
    ONLINE: '在线',
    OFFLINE: '离线',
    MAINTENANCE: '维护'
  }[value] || value || '-'
}

export function behaviorLabel(value) {
  return {
    grazing: '采食',
    lying_ruminating: '卧姿反刍',
    lying_resting: '卧姿休息',
    standing_resting: '站立休息',
    walking: '行走',
    standing_ruminating: '站立反刍',
    sensors_missing: '运动传感器离线',
    waiting: '等待模型数据'
  }[value] || value || '-'
}
