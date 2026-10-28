<template>
  <span class="status-pill" :class="klass">{{ label }}</span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  value: { type: String, default: 'NORMAL' }
})

const label = computed(() => ({
  NORMAL: '正常',
  OBSERVE: '观察',
  WARNING: '告警',
  URGENT: '紧急'
}[props.value] || props.value))

const klass = computed(() => ({
  NORMAL: 'normal',
  OBSERVE: 'observe',
  WARNING: 'warning',
  URGENT: 'urgent'
}[props.value] || 'normal'))
</script>
