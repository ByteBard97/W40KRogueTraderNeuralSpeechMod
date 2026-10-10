<script setup lang="ts">
import { nextTick, ref, watch } from 'vue'
import type { QaClip } from '../../api/types'
import { QA_PAGE } from '../../stores/qa'
import Btn from '../ui/Btn.vue'
import Kbd from '../ui/Kbd.vue'
import StatusDot, { type DotStatus } from '../ui/StatusDot.vue'

const props = defineProps<{ items: QaClip[]; index: number; total: number; hasNext: boolean; loading: boolean; sortLabel: string }>()
const emit = defineEmits<{ select: [index: number]; more: [] }>()

const SORT_NAMES: Record<string, string> = { suspicious: 'suspicious first', slowest: 'slowest', fastest: 'fastest', longest: 'longest', shortest: 'shortest', random: 'random' }
const fmt = (n: number) => n.toLocaleString('en-US')
const dot = (c: QaClip): { status: DotStatus; label: string } => {
  const v = c.verdict?.verdict
  return v === 'good' ? { status: 'good', label: 'Good' } : v === 'bad' ? { status: 'bad', label: 'Bad' } : { status: 'idle', label: 'Unjudged' }
}
const rows = ref<HTMLElement | null>(null)
watch(() => props.index, async () => {
  await nextTick()
  rows.value?.querySelector<HTMLElement>('[aria-current="true"]')?.scrollIntoView?.({ block: 'nearest' })
})
</script>

<template>
  <div class="vs-card queue">
    <div class="list-head head">
      <span>Queue · {{ SORT_NAMES[sortLabel] ?? sortLabel }}</span>
      <span class="n">{{ items.length ? `1–${fmt(items.length)}` : 0 }} of {{ fmt(total) }}</span>
    </div>
    <div ref="rows" class="rows" role="list">
      <button
        v-for="(c, i) in items"
        :key="c.guid"
        type="button"
        class="qrow"
        :aria-current="i === index"
        data-qrow
        @click="emit('select', i)"
      >
        <StatusDot :status="dot(c).status" :label="dot(c).label" />
        <span class="t"><b>{{ c.speaker }}</b> · {{ c.text }}</span>
        <span class="num muted dur">{{ c.dur.toFixed(1) }} s</span>
        <span class="m"><span>{{ c.engine }}</span><span v-if="c.flags.length" class="w">{{ c.flags.join(' ') }}</span></span>
      </button>
    </div>
    <div class="foot muted">
      <span><Kbd>J</Kbd> <Kbd>K</Kbd> move · <Kbd>N</Kbd> next unjudged</span>
      <Btn size="sm" :disabled="!hasNext || loading" data-more @click="emit('more')">{{ loading ? 'Loading…' : hasNext ? `Load ${QA_PAGE} more` : 'End of queue' }}</Btn>
    </div>
  </div>
</template>

<style scoped>
.queue { padding: var(--s-1); display: flex; flex-direction: column; min-height: 0; }
.head { justify-content: space-between; }
.rows { overflow-y: auto; max-height: 60vh; }
.qrow { display: grid; grid-template-columns: 12px minmax(0, 1fr) auto; gap: 2px var(--s-3); align-items: center; width: 100%; padding: var(--s-2) 10px; border: 0; border-top: 1px solid var(--line); border-radius: 0; background: transparent; color: inherit; text-align: left; cursor: pointer; font: inherit; }
.qrow:hover { background: var(--hover); }
.qrow[aria-current="true"] { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); border-top-color: transparent; }
.t { font-size: 13px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; color: var(--text); }
.t b { color: var(--text-2); font-weight: 600; }
.dur { font-size: var(--fs-sm); }
.m { grid-column: 2 / 4; display: flex; gap: var(--s-2); font-size: var(--fs-xs); color: var(--text-3); font-family: var(--font-mono); white-space: nowrap; overflow: hidden; }
.w { color: var(--warn); }
.foot { display: flex; flex-wrap: wrap; align-items: center; justify-content: space-between; gap: var(--s-2); padding: var(--s-2) 10px; font-size: var(--fs-sm); border-top: 1px solid var(--line); }
@media (max-width: 960px) { .rows { max-height: 50vh; } }
</style>
