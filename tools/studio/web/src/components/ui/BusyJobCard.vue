<script setup lang="ts">
import { computed } from 'vue'
import { formatClock } from '../../utils/time'
import Btn from './Btn.vue'

/** A running job. `progress` (0-1) makes the meter determinate; without it the bar shimmers and only elapsed time shows. */
const props = defineProps<{ title: string; elapsedS: number; progress?: number; etaS?: number; detail?: string; cancelable?: boolean }>()
const emit = defineEmits<{ cancel: [] }>()
const pct = computed(() => (props.progress === undefined ? null : Math.round(Math.min(Math.max(props.progress, 0), 1) * 100)))
</script>

<template>
  <div class="card" role="status">
    <div class="top">
      <span class="ttl"><span class="spinner" /><b>{{ title }}</b></span>
      <span class="num muted">{{ formatClock(elapsedS) }} elapsed<template v-if="etaS !== undefined"> · ~{{ formatClock(etaS) }} left</template></span>
    </div>
    <div class="bar" :class="{ indeterminate: pct === null }" role="progressbar" :aria-valuenow="pct ?? undefined" aria-valuemin="0" aria-valuemax="100"><i :style="{ width: pct === null ? '40%' : `${pct}%` }" /></div>
    <div class="top">
      <span class="muted detail">{{ detail }}</span>
      <Btn v-if="cancelable" size="sm" variant="ghost" @click="emit('cancel')">Cancel</Btn>
    </div>
  </div>
</template>

<style scoped>
.card { padding: 14px; display: flex; flex-direction: column; gap: 10px; background: var(--raised); border: 1px solid var(--line); border-radius: var(--r-lg); }
.top { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--s-2); }
.ttl { display: inline-flex; align-items: center; gap: var(--s-2); }
.detail { font-size: var(--fs-sm); }
.bar { height: 6px; border-radius: 3px; background: var(--n-4); overflow: hidden; display: flex; }
.bar i { display: block; height: 100%; background: var(--accent); }
.indeterminate i { animation: slide 1.4s ease-in-out infinite alternate; }
@keyframes slide { from { transform: translateX(0); } to { transform: translateX(150%); } }
</style>
