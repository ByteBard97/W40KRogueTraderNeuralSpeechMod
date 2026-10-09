<script setup lang="ts">
import { computed } from 'vue'
import type { PoolSummary } from '../../api/types'

const props = defineProps<{ summary: PoolSummary }>()
const rows = computed(() => [
  { key: 'speaker_bank', label: 'Known speaker with a real voice bank', note: 'companion lines exported without a speaker tag', n: props.summary.destinations.speaker_bank },
  { key: 'speaker_nobank', label: 'Known named NPC without a bank', note: 'needs its own designed voice (Speakers section)', n: props.summary.destinations.speaker_nobank },
  { key: 'narrator', label: 'Narrator', note: 'narration and unattributed text', n: props.summary.destinations.narrator },
  { key: 'slot', label: 'Shared slot voice', note: 'genuinely anonymous characters', n: props.summary.destinations.slot },
])
</script>

<template>
  <div>
    <p class="dim">{{ summary.total }} unnamed lines routed · built {{ summary.built }} · threshold {{ summary.threshold }}</p>
    <div v-for="r in rows" :key="r.key" class="row">
      <b class="n">{{ r.n }}</b>
      <span>{{ r.label }}</span>
      <span class="dim">{{ r.note }}</span>
    </div>
    <p class="dim">{{ summary.queue_entries }} roster entries ({{ summary.queue_lines }} lines) need a look.</p>
  </div>
</template>

<style scoped>
.row { display: flex; gap: 10px; align-items: baseline; padding: 3px 0; }
.n { min-width: 56px; text-align: right; color: var(--acc); }
.dim { color: var(--dim); font-size: 12px; }
</style>
