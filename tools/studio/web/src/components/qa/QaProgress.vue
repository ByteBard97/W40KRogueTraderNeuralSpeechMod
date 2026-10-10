<script setup lang="ts">
import { computed } from 'vue'
import type { QaStats, QaView } from '../../api/types'

const props = defineProps<{ stats: QaStats; view: QaView | null; session: number }>()

const PERCENT = 100
const fmt = (n: number) => n.toLocaleString('en-US')
/** The bar shows the filtered set when the server sends it, otherwise the whole run. */
const scope = computed(() => props.view ?? { ...props.stats, total: props.stats.good + props.stats.bad + props.stats.unjudged })
const scopeLabel = computed(() => (props.view ? 'this view' : 'this run'))
const pct = (n: number) => (scope.value.total > 0 ? `${(n / scope.value.total) * PERCENT}%` : '0%')
const refs = computed(() => Object.entries(props.stats.by_ref ?? {}))
</script>

<template>
  <div class="qa-bar" aria-label="Progress">
    <span class="num counts" data-stats>
      <b class="g">{{ fmt(stats.good) }}</b> good · <b class="b">{{ fmt(stats.bad) }}</b> bad · <b>{{ fmt(stats.unjudged) }}</b> unjudged
    </span>
    <span class="muted small">{{ scopeLabel }}</span>
    <div class="bar" role="img" :aria-label="`${scopeLabel}: ${scope.good} good, ${scope.bad} bad, ${scope.unjudged} unjudged`">
      <i class="seg-g" :style="{ width: pct(scope.good) }" /><i class="seg-b" :style="{ width: pct(scope.bad) }" />
    </div>
    <span class="muted small" data-session>this session {{ session }} judged</span>
    <details v-if="refs.length" class="refs">
      <summary class="refs-btn">Per reference ▾</summary>
      <ul class="mono muted tally" data-ref-tally>
        <li v-for="[name, r] in refs" :key="name">{{ name }}: {{ r.good }}g/{{ r.bad }}b/{{ r.total }}</li>
      </ul>
    </details>
  </div>
</template>

<style scoped>
.qa-bar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-4); padding: var(--s-3) var(--s-4); background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); }
.counts { font-size: 13px; }
.g { color: var(--good); }
.b { color: var(--bad); }
.small { font-size: var(--fs-sm); }
.bar { display: flex; flex: 1 1 300px; height: var(--s-2); border-radius: var(--r-pill); background: var(--n-3); overflow: hidden; }
.seg-g { background: var(--good); }
.seg-b { background: var(--bad); }
.refs { position: relative; }
.refs-btn { list-style: none; cursor: pointer; padding: var(--s-1) var(--s-2); border-radius: var(--r-md); font-size: var(--fs-sm); font-weight: 500; color: var(--text-2); }
.refs-btn::-webkit-details-marker { display: none; }
.refs-btn:hover { background: var(--hover); color: var(--text); }
.tally { margin: 0; padding: var(--s-2) 0 0; list-style: none; font-size: var(--fs-xs); line-height: 1.8; }
.refs[open] { flex-basis: 100%; }
</style>
