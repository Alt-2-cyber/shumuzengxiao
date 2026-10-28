<template>
  <div ref="chartEl" class="chart-box"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([CanvasRenderer, GridComponent, LegendComponent, TooltipComponent, LineChart])

const props = defineProps({
  rows: { type: Array, default: () => [] },
  thirdKey: { type: String, default: 'ammonia' },
  thirdLabel: { type: String, default: '氨气' }
})

const chartEl = ref(null)
let chart
let handleResize

function render() {
  if (!chart) return
  const timestamps = props.rows
    .map((row) => new Date(row.recordedAt).getTime())
    .filter(Number.isFinite)
  const useSeconds = timestamps.length > 1 && Math.max(...timestamps) - Math.min(...timestamps) < 6 * 60 * 60 * 1000
  const labels = props.rows.map((row) => {
    const date = new Date(row.recordedAt)
    if (!Number.isFinite(date.getTime())) return '-'
    const hour = String(date.getHours()).padStart(2, '0')
    const minute = String(date.getMinutes()).padStart(2, '0')
    const second = String(date.getSeconds()).padStart(2, '0')
    return useSeconds ? `${hour}:${minute}:${second}` : `${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')} ${hour}:00`
  })
  chart.setOption({
    grid: { left: 42, right: 20, top: 28, bottom: 32 },
    tooltip: { trigger: 'axis' },
    legend: { top: 0, right: 0 },
    xAxis: { type: 'category', data: labels, axisLine: { lineStyle: { color: '#cbd5ca' } } },
    yAxis: { type: 'value', splitLine: { lineStyle: { color: '#edf1ec' } } },
    series: [
      { name: '温度', type: 'line', smooth: true, data: props.rows.map((r) => r.temperature), color: '#b37a22' },
      { name: '湿度', type: 'line', smooth: true, data: props.rows.map((r) => r.humidity), color: '#2d6f91' },
      { name: props.thirdLabel, type: 'line', smooth: true, data: props.rows.map((r) => r[props.thirdKey]), color: '#b64235' }
    ]
  })
}

onMounted(() => {
  chart = echarts.init(chartEl.value)
  handleResize = () => chart?.resize()
  render()
  window.addEventListener('resize', handleResize)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', handleResize)
  chart?.dispose()
})

watch(() => props.rows, render, { deep: true })
</script>
