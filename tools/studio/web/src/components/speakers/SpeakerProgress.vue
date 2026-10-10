<script setup lang="ts">
import { computed } from 'vue'
import type { Counts } from '../../utils/speakerRows'
import StatusDot from '../ui/StatusDot.vue'

const props = defineProps<{ counts: Counts }>()
const PERCENT = 100
const pct = (n: number) => (props.counts.total ? (n / props.counts.total) * PERCENT : 0)
const segments = computed(() => [
  { key: 'registered', cls: 'g', w: pct(props.counts.registered) },
  { key: 'picked', cls: 'a', w: pct(props.counts.picked) },
  { key: 'progress', cls: 'w', w: pct(props.counts.progress) },
])
</script>

<template>
  <div class="progress">
    <div class="label"><span>Voices done</span><span class="num">{{ counts.done }} / {{ counts.total }}</span></div>
    <div class="bar" role="img" :aria-label="`${counts.registered} registered, ${counts.picked} picked, ${counts.progress} in progress, of ${counts.total} speakers`">
      <i v-for="s in segments" :key="s.key" :class="s.cls" :style="{ width: `${s.w}%` }" />
    </div>
    <div class="legend">
      <span><StatusDot status="done" label="registered" /> registered {{ counts.registered }}</span>
      <span><StatusDot status="picked" label="picked" /> picked {{ counts.picked }}</span>
      <span><StatusDot status="progress" label="in progress" /> in progress {{ counts.progress }}</span>
      <span><StatusDot status="idle" label="not started" /> not started {{ counts.idle }}</span>
    </div>
  </div>
</template>

<style scoped>
.progress { display: flex; flex-direction: column; gap: 6px; min-width: 200px; }
.label { display: flex; justify-content: space-between; gap: var(--s-3); font-size: var(--fs-sm); color: var(--text-2); }
.bar { height: 6px; border-radius: 3px; background: var(--n-4); overflow: hidden; display: flex; }
.bar i { display: block; height: 100%; }
.g { background: var(--good); }
.a { background: var(--accent); }
.w { background: var(--warn); }
.legend { display: flex; flex-wrap: wrap; gap: var(--s-1) var(--s-3); font-size: var(--fs-sm); color: var(--text-3); }
.legend span { display: inline-flex; align-items: center; gap: 6px; }
.legend :deep(.dot) { width: 9px; height: 9px; border-width: 2px; }
</style>
