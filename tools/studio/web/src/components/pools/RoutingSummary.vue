<script setup lang="ts">
import { computed } from 'vue'
import type { PoolSummary } from '../../api/types'
import type { DestFilter } from '../../stores/poolRoutes'

const PERCENT = 100
const props = defineProps<{ summary: PoolSummary }>()
const emit = defineEmits<{ filter: [dest: Exclude<DestFilter, ''>] }>()

interface Seg { key: Exclude<DestFilter, ''>; label: string; note: string; n: number; tone: string }
const segs = computed<Seg[]>(() => {
  const d = props.summary.destinations
  return [
    { key: 'bank', label: 'Known speaker with a voice bank', note: 'companion lines exported untagged', n: d.speaker_bank, tone: 'info' },
    { key: 'nobank', label: 'Named NPC without a bank', note: 'needs a designed voice', n: d.speaker_nobank, tone: 'accent' },
    { key: 'narrator', label: 'Narrator', note: 'narration, unattributed text', n: d.narrator, tone: 'narr' },
    { key: 'slot', label: 'Shared slot voice', note: `anonymous characters, ${props.summary.slots.length} slots`, n: d.slot, tone: 'slot' },
  ]
})
const total = computed(() => segs.value.reduce((a, s) => a + s.n, 0) || 1)
const width = (n: number) => `${(n / total.value) * PERCENT}%`
const fmt = (n: number) => n.toLocaleString('en-US')
const aria = computed(() => segs.value.map((s) => `${fmt(s.n)} ${s.label}`).join(', '))
</script>

<template>
  <section class="card" aria-labelledby="sum-h">
    <div class="head"><h2 id="sum-h">Where the unnamed lines go</h2><span class="hint">click a segment to filter the routes table</span></div>
    <div class="bar" role="group" :aria-label="aria">
      <button v-for="s in segs" v-show="s.n > 0" :key="s.key" type="button" class="seg" :class="`t-${s.tone}`" :style="{ width: width(s.n) }" :title="`${s.label}: ${fmt(s.n)}`" :aria-label="`Show ${s.label} in the routes table`" @click="emit('filter', s.key)" />
    </div>
    <div class="legend">
      <button v-for="s in segs" :key="s.key" type="button" class="item" @click="emit('filter', s.key)">
        <i :class="`t-${s.tone}`" />
        <b class="num">{{ fmt(s.n) }}</b>
        <span>{{ s.label }} <span class="muted">· {{ s.note }}</span></span>
      </button>
    </div>
  </section>
</template>

<style scoped>
.card { padding: var(--s-4); display: flex; flex-direction: column; gap: var(--s-3); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); }
.head { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: baseline; }
h2 { margin: 0; font-size: 15px; font-weight: 600; }
.hint { font-size: var(--fs-sm); color: var(--text-3); }
.bar { display: flex; height: 14px; border-radius: var(--r-sm); overflow: hidden; gap: 2px; }
.seg { height: 100%; min-width: 3px; padding: 0; border: 0; border-radius: 0; cursor: pointer; }
.seg:hover { filter: brightness(1.2); }
.t-info { background: var(--info); }
.t-accent { background: var(--accent); }
.t-narr { background: var(--n-7); }
.t-slot { background: var(--good); }
.legend { display: grid; grid-template-columns: repeat(auto-fit, minmax(min(240px, 100%), 1fr)); gap: var(--s-2) var(--s-5); }
.item { display: grid; grid-template-columns: 12px 64px minmax(0, 1fr); gap: var(--s-3); align-items: baseline; font-size: 13px; text-align: left; background: transparent; border: 0; padding: 2px 0; color: var(--text); cursor: pointer; min-height: 0; }
.item:hover span { color: var(--text); }
.item i { width: 12px; height: 12px; border-radius: 3px; display: block; align-self: center; }
.item b { font-family: var(--font-mono); font-weight: 500; text-align: right; }
.muted { color: var(--text-3); }
</style>
