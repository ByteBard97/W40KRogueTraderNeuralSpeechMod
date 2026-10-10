<script setup lang="ts">
import { computed } from 'vue'
import type { JobView } from '../../api/jobs'
import { formatClock } from '../../utils/time'
import Btn from '../ui/Btn.vue'

const MAX_FILL = 0.95
/** One live-design job as a row at the end of the ranking: which id it will take, the seed it was given, how long it has run. */
const props = defineProps<{ job: JobView; nextId: string }>()
const emit = defineEmits<{ cancel: [] }>()

const item = computed(() => props.job.items.find((i) => i.state === 'running') ?? props.job.items.find((i) => i.state === 'queued') ?? props.job.items[0])
const running = computed(() => props.job.state === 'running')
const elapsed = computed(() => (running.value ? (props.job.current?.elapsed_s ?? props.job.elapsed_s) : 0))
const fill = computed(() => {
  const exp = props.job.expected_s
  return running.value && exp ? Math.min(elapsed.value / exp, MAX_FILL) : null
})
</script>

<template>
  <div class="job" role="status">
    <div class="l1">
      <span class="dot" aria-hidden="true">·</span>
      <span class="spinner" :class="{ idle: !running }" aria-hidden="true" />
      <span class="cid">{{ nextId }}</span>
      <span class="muted txt">
        {{ running ? 'Designing from the description' : 'Queued' }} · seed {{ item.seed }} · cfg {{ item.cfg }} · {{ item.timesteps }} steps<template v-if="running"> · {{ formatClock(elapsed) }} elapsed</template>
      </span>
      <span class="end"><Btn size="sm" variant="ghost" @click="emit('cancel')">Cancel</Btn></span>
    </div>
    <div class="l2"><div class="bar" :class="{ indeterminate: fill === null }"><i :style="{ width: fill === null ? '40%' : `${Math.round(fill * 100)}%` }" /></div></div>
  </div>
</template>

<style scoped>
.job { display: flex; flex-direction: column; gap: 6px; padding: 8px 10px; border-top: 1px solid var(--line); }
.l1 { display: flex; flex-wrap: wrap; align-items: center; gap: 6px 10px; }
.dot { width: 16px; text-align: right; color: var(--text-3); }
.cid { font: 500 14px var(--font-mono); min-width: 28px; }
.txt { font-size: 13px; }
.end { margin-left: auto; }
.idle { animation: none; border-top-color: var(--n-5); }
.l2 { padding-left: 78px; }
.bar { height: 6px; max-width: 40%; border-radius: 3px; background: var(--n-4); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--accent); }
.indeterminate i { animation: slide 1.4s ease-in-out infinite alternate; }
@keyframes slide { from { transform: translateX(0); } to { transform: translateX(150%); } }
@media (max-width: 640px) { .l2 { padding-left: 0; } .bar { max-width: 100%; } }
</style>
