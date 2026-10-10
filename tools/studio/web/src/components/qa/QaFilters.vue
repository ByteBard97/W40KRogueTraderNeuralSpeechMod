<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { QaFacets, QaFilter, QaFx, QaRun, QaSort } from '../../api/types'
import ActiveFilters, { type ActiveFilter } from '../ui/ActiveFilters.vue'
import FilterBar from '../ui/FilterBar.vue'
import Kbd from '../ui/Kbd.vue'
import SearchField from '../ui/SearchField.vue'
import SelectField, { type SelectOption } from '../ui/SelectField.vue'
import Seg from '../ui/Seg.vue'

const SEARCH_DEBOUNCE_MS = 300
type FxChoice = QaFx | ''
type PopKey = 'speaker' | 'ref' | 'engine' | 'flag' | 'verdict'

const props = defineProps<{
  runs: QaRun[]
  run: string
  facets: QaFacets
  filter: QaFilter
  fx: FxChoice
  /** Clips matching the filter, and clips in the whole run, for "Showing N of M". */
  matching: number
  inRun: number
}>()
const emit = defineEmits<{ change: [filter: QaFilter]; 'update:run': [id: string]; 'update:fx': [fx: FxChoice] }>()

const SORTS: { value: QaSort; label: string }[] = [
  { value: 'suspicious', label: 'Suspicious first' },
  { value: 'slowest', label: 'Slowest' },
  { value: 'fastest', label: 'Fastest' },
  { value: 'longest', label: 'Longest' },
  { value: 'shortest', label: 'Shortest' },
  { value: 'random', label: 'Random' },
]
const FX_OPTIONS: { value: FxChoice; label: string }[] = [
  { value: '', label: 'Off' },
  { value: 'mild', label: 'Mild' },
  { value: 'strong', label: 'Strong' },
]
const POP_LABELS: Record<PopKey, string> = { speaker: 'Speaker', ref: 'Reference', engine: 'Engine', flag: 'Flag', verdict: 'Verdict' }

const named = (all: string, items: string[]): SelectOption[] => [{ value: '', label: all }, ...items.map((v) => ({ value: v, label: v }))]
const runOptions = computed(() => props.runs.map((r) => ({ value: r.id, label: `${r.label} (${r.clips.toLocaleString('en-US')})` })))
const sortOptions = SORTS
const speakerOptions = computed(() => named('All', props.facets.speakers))
const refOptions = computed(() => named('All', props.facets.refs))
const engineOptions = computed(() => named('All', props.facets.engines))
const flagOptions = computed<SelectOption[]>(() => [
  { value: '', label: 'Any' }, { value: 'any flag', label: 'Has a flag' }, { value: 'no flag', label: 'No flag' },
  ...props.facets.flags.map((v) => ({ value: v, label: v })),
])
const verdictOptions: SelectOption[] = [
  { value: '', label: 'Any' }, { value: 'unjudged', label: 'Unjudged' }, { value: 'good', label: 'Good' }, { value: 'bad', label: 'Bad' },
]

const patch = (p: QaFilter) => emit('change', { ...props.filter, ...p })
const value = (k: PopKey | 'q') => props.filter[k] ?? ''

const q = ref(props.filter.q ?? '')
watch(() => props.filter.q, (v) => { q.value = v ?? '' })
let timer: ReturnType<typeof setTimeout> | undefined
watch(q, (v) => {
  clearTimeout(timer)
  if (v === value('q')) return
  timer = setTimeout(() => patch({ q: v }), SEARCH_DEBOUNCE_MS)
})
onBeforeUnmount(() => clearTimeout(timer))
function searchNow() {
  clearTimeout(timer)
  if (q.value !== value('q')) patch({ q: q.value })
}

const popKeys = Object.keys(POP_LABELS) as PopKey[]
const activeCount = computed(() => popKeys.filter((k) => value(k)).length)
const chips = computed<ActiveFilter[]>(() => [
  ...popKeys.filter((k) => value(k)).map((k) => ({ key: k, label: `${POP_LABELS[k]}: ${value(k)}` })),
  ...(value('q') ? [{ key: 'q', label: `Text: “${value('q')}”` }] : []),
])
const removeFilter = (key: string) => patch({ [key]: '' })
const clearAll = () => emit('change', { ...props.filter, speaker: '', ref: '', engine: '', flag: '', verdict: '', q: '' })
</script>

<template>
  <div class="qa-filters">
    <FilterBar>
      <SelectField label="Run" :options="runOptions" :model-value="run" data-run @update:model-value="emit('update:run', $event)" />
      <SearchField v-model="q" class="grow" placeholder="Search line text" label="Search line text" @keydown.enter="searchNow" />
      <SelectField label="Sort" :options="sortOptions" :model-value="filter.sort ?? 'suspicious'" data-sort @update:model-value="patch({ sort: $event as QaSort })" />
      <details class="pop">
        <summary class="pop-btn">Filters <span class="num muted count">{{ activeCount }} active</span></summary>
        <div class="pop-body">
          <SelectField label="Speaker" :options="speakerOptions" :model-value="value('speaker')" data-speaker @update:model-value="patch({ speaker: $event })" />
          <SelectField label="Reference" :options="refOptions" :model-value="value('ref')" data-ref @update:model-value="patch({ ref: $event })" />
          <SelectField label="Engine" :options="engineOptions" :model-value="value('engine')" data-engine @update:model-value="patch({ engine: $event })" />
          <SelectField label="Flag" :options="flagOptions" :model-value="value('flag')" data-flag @update:model-value="patch({ flag: $event })" />
          <SelectField label="Verdict" :options="verdictOptions" :model-value="value('verdict')" data-verdict @update:model-value="patch({ verdict: $event })" />
        </div>
      </details>
      <div class="comp">
        <span class="muted label">Compressor <Kbd>X</Kbd></span>
        <Seg :model-value="fx" :options="FX_OPTIONS" aria-label="Compressor" @update:model-value="emit('update:fx', $event as FxChoice)" />
      </div>
    </FilterBar>
    <ActiveFilters :filters="chips" :shown="matching" :total="inRun" @remove="removeFilter" @clear="clearAll" />
  </div>
</template>

<style scoped>
.qa-filters { position: relative; display: flex; flex-direction: column; gap: var(--s-2); }
/* The popover anchors under the whole filter area, not the button: the button sits mid-bar and a 560px body would run off the right edge. */
.pop { position: static; }
.pop-btn { list-style: none; display: inline-flex; align-items: center; gap: var(--s-2); min-height: var(--hit); padding: 0 var(--s-3); border-radius: var(--r-md); border: 1px solid var(--line-strong); background: var(--raised); color: var(--text); font-weight: 500; cursor: pointer; }
.pop-btn::-webkit-details-marker { display: none; }
.pop-btn:hover { border-color: var(--n-6); }
.count { font-size: var(--fs-sm); }
.pop-body { position: absolute; z-index: calc(var(--z-topbar) - 1); top: calc(100% + var(--s-1)); left: 0; width: min(560px, calc(100vw - 2 * var(--s-4))); display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: var(--s-2); padding: var(--s-3); border-radius: var(--r-lg); background: var(--surface); border: 1px solid var(--line-strong); box-shadow: var(--e-2); }
.comp { display: flex; align-items: center; gap: var(--s-2); margin-left: auto; }
.label { font-size: var(--fs-sm); }
@media (max-width: 640px) { .comp { margin-left: 0; width: 100%; justify-content: flex-end; } }
</style>
