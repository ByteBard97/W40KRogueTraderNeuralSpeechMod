<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted } from 'vue'
import { useModelStore } from '../../stores/model'
import { formatClock } from '../../utils/time'
import Btn from './Btn.vue'

/** Top-bar model status: ready, busy (with elapsed) or down (with the reason and Retry). Each state has its own LED shape plus text. */
const model = useModelStore()
onMounted(model.start)
onBeforeUnmount(model.stop)
const text = computed(() => {
  if (model.state === 'ready') return 'Model ready'
  if (model.state === 'busy') return 'Model busy'
  return `Model down: ${model.reason}`
})
</script>

<template>
  <span class="wrap">
    <span class="pill" :class="model.state" role="status" :title="model.reason || 'The model backend is ready.'">
      <span class="led" />{{ text }}<span v-if="model.state === 'busy'" class="num">{{ formatClock(model.busyElapsed) }}</span>
    </span>
    <Btn v-if="model.state === 'down'" size="sm" @click="model.retry()">Retry</Btn>
  </span>
</template>

<style scoped>
.wrap { display: inline-flex; align-items: center; gap: var(--s-2); min-width: 0; }
.pill { display: inline-flex; align-items: center; gap: 8px; min-height: 28px; padding: 0 12px 0 10px; border-radius: var(--r-pill); border: 1px solid var(--line-strong); background: var(--raised); font-size: var(--fs-sm); color: var(--text-2); white-space: nowrap; max-width: 46ch; overflow: hidden; text-overflow: ellipsis; }
.led { width: 8px; height: 8px; border-radius: 50%; background: var(--text-3); flex: none; }
.ready .led { background: var(--good); box-shadow: 0 0 0 3px var(--good-tint); }
.busy { border-color: var(--selected-line); color: var(--text); }
.busy .led { background: var(--accent); animation: pulse 1.2s ease-in-out infinite; }
.down { border-color: var(--bad-line); color: var(--text); }
.down .led { background: var(--bad); border-radius: 1px; transform: rotate(45deg); }
@keyframes pulse { 50% { opacity: 0.35; } }
@media (max-width: 640px) { .pill { max-width: 22ch; } }
</style>
