<template>
  <div ref="chartEl" class="motion-chart" role="img" aria-label="颈部、背部和腿部活动强度趋势"></div>
</template>

<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { LineChart } from 'echarts/charts'
import { GridComponent, LegendComponent, TooltipComponent } from 'echarts/components'
import * as echarts from 'echarts/core'
import { CanvasRenderer } from 'echarts/renderers'

echarts.use([CanvasRenderer, GridComponent, LegendComponent, TooltipComponent, LineChart])

const props = defineProps({
  rows: { type: Array, default: () => [] }
})

const chartEl = ref(null)
let chart
let resizeObserver

function timeLabel(value) {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return '-'
  return date.toLocaleTimeString('zh-CN', { hour12: false, minute: '2-digit', second: '2-digit' })
}

function render() {
  if (!chart) return
  const rows = props.rows.slice(-60)
  chart.setOption({
    animationDuration: 260,
    grid: { left: 46, right: 18, top: 36, bottom: 34 },
    tooltip: {
      trigger: 'axis',
      backgroundColor: 'rgba(8, 12, 9, .94)',
      borderColor: 'rgba(248, 242, 223, .2)',
      textStyle: { color: '#f8f2df' }
    },
    legend: {
      top: 0,
      right: 0,
      itemWidth: 16,
      textStyle: { color: '#b8b19e' }
    },
    xAxis: {
      type: 'category',
      boundaryGap: false,
      data: rows.map((row) => timeLabel(row.receivedAt)),
      axisLine: { lineStyle: { color: 'rgba(248, 242, 223, .22)' } },
      axisLabel: { color: '#9f9989', hideOverlap: true }
    },
    yAxis: {
      type: 'value',
      min: 0,
      axisLabel: { color: '#9f9989' },
      splitLine: { lineStyle: { color: 'rgba(248, 242, 223, .09)' } }
    },
    series: [
      {
        name: '颈部',
        type: 'line',
        showSymbol: false,
        smooth: 0.25,
        data: rows.map((row) => row.behavior?.neckActivity ?? null),
        lineStyle: { width: 2 },
        color: '#8ef0a0'
      },
      {
        name: '背部',
        type: 'line',
        showSymbol: false,
        smooth: 0.25,
        data: rows.map((row) => row.behavior?.bodyActivity ?? null),
        lineStyle: { width: 2 },
        color: '#e5b85c'
      },
      {
        name: '腿部',
        type: 'line',
        showSymbol: false,
        smooth: 0.25,
        data: rows.map((row) => row.behavior?.legActivity ?? null),
        lineStyle: { width: 2 },
        color: '#7cb7ff'
      }
    ]
  }, true)
}

onMounted(() => {
  chart = echarts.init(chartEl.value)
  resizeObserver = new ResizeObserver(() => chart?.resize())
  resizeObserver.observe(chartEl.value)
  render()
})

onBeforeUnmount(() => {
  resizeObserver?.disconnect()
  chart?.dispose()
})

watch(() => props.rows, render, { deep: true })
</script>
