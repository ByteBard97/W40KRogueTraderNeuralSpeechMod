<script setup lang="ts">
import { computed, ref } from 'vue'
import type { FxLabels, FxPresetInfo, FxUsage } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'
import Btn from '../ui/Btn.vue'
import StatusDot from '../ui/StatusDot.vue'

const FALLBACK_FAMILY = 'Other'
const props = defineProps<{ draft: FxLabels; labels: string[]; dirty: string[]; presets: FxPresetInfo[]; usage: FxUsage | null }>()
const emit = defineEmits<{ add: [label: string, name: string]; remove: [label: string, i: number]; move: [label: string, from: number, to: number] }>()

const grouped = computed(() => {
  const g = new Map<string, FxPresetInfo[]>()
  for (const p of props.presets) g.set(p.family || FALLBACK_FAMILY, [...(g.get(p.family || FALLBACK_FAMILY) ?? []), p])
  return [...g]
})
const uses = (label: string) => (props.usage ? String(props.usage.labels[label]?.speakers ?? 0) : '–')
const lineUses = (label: string) => props.usage?.labels[label]?.lines

function onAdd(label: string, e: Event) {
  const el = e.target as HTMLSelectElement
  if (el.value) emit('add', label, el.value)
  el.value = ''
}

const drag = ref<{ label: string; from: number } | null>(null)
function onDrop(label: string, to: number) {
  if (drag.value && drag.value.label === label) emit('move', label, drag.value.from, to)
  drag.value = null
}
function onChipKey(label: string, i: number, e: KeyboardEvent) {
  if (!e.altKey || (e.key !== 'ArrowLeft' && e.key !== 'ArrowRight')) return
  e.preventDefault()
  const to = i + (e.key === 'ArrowLeft' ? -1 : 1)
  emit('move', label, i, to)
  requestAnimationFrame(() => (e.target as HTMLElement | null)?.closest('.chain')?.querySelectorAll<HTMLElement>('.chip-name')[to]?.focus())
}
</script>

<template>
  <SectionCard title="Label → preset map" summary="presets run left to right · drag or Alt+←/→ to reorder">
    <EmptyState v-if="!labels.length" message="No labels found." />
    <div v-else class="grid" role="table" aria-label="Label to preset map">
      <div class="map-row head" role="row">
        <span role="columnheader">Label</span><span role="columnheader">Chain</span><span role="columnheader" class="uses">Speakers</span><span role="columnheader" class="vh">State</span>
      </div>
      <div v-for="label in labels" :key="label" class="map-row" :class="{ dirty: dirty.includes(label) }" role="row" :data-label="label">
        <span class="lb mono" role="cell">{{ label }}</span>
        <div class="chain" role="cell" @dragover.prevent @drop.prevent="onDrop(label, (draft[label]?.length ?? 1) - 1)">
          <span
            v-for="(p, i) in draft[label] ?? []"
            :key="p"
            class="chip"
            draggable="true"
            @dragstart="drag = { label, from: i }"
            @dragover.prevent
            @drop.prevent.stop="onDrop(label, i)"
          >
            <button type="button" class="chip-name" :aria-label="`${p}, step ${i + 1}. Alt+arrow keys reorder`" @keydown="onChipKey(label, i, $event)">{{ p }}</button>
            <button type="button" class="x" :aria-label="`Remove ${p} from ${label}`" data-remove @click="emit('remove', label, i)">×</button>
          </span>
          <span v-if="!(draft[label] ?? []).length" class="muted none">no effect</span>
          <label class="add">
            <span class="vh">Add preset to {{ label }}</span>
            <select data-add :aria-label="`Add preset to ${label}`" @change="onAdd(label, $event)">
              <option value="">+ Add</option>
              <optgroup v-for="[fam, items] in grouped" :key="fam" :label="fam">
                <option v-for="p in items" :key="p.name" :value="p.name" :disabled="(draft[label] ?? []).includes(p.name)">{{ p.name }}</option>
              </optgroup>
            </select>
          </label>
        </div>
        <span class="uses num muted" role="cell" :title="lineUses(label) === undefined ? undefined : `${lineUses(label)} lines`">{{ uses(label) }}</span>
        <span role="cell"><StatusDot :status="dirty.includes(label) ? 'flag' : 'good'" :label="dirty.includes(label) ? 'edited, not written' : 'matches file'" /></span>
      </div>
    </div>
    <p v-if="usage && !usage.pools_built" class="note muted">Speaker counts use roster entries until the Pools routes are built.</p>
  </SectionCard>
</template>

<style scoped>
.grid { margin: 0 calc(var(--s-4) * -1); }
.map-row { display: grid; grid-template-columns: 150px minmax(0, 1fr) 90px 28px; gap: 10px; align-items: center; padding: 10px var(--s-4); border-top: 1px solid var(--line); }
.map-row.head { border-top: 0; padding-top: 0; font-size: var(--fs-xs); text-transform: uppercase; letter-spacing: 0.08em; color: var(--text-3); font-weight: 600; }
.map-row.dirty { background: var(--warn-tint); }
.lb { font-size: 13px; color: var(--text); overflow-wrap: anywhere; }
.chain { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; }
.chip { display: inline-flex; align-items: center; min-height: 26px; border-radius: var(--r-pill); border: 1px solid var(--accent-lo); background: var(--accent-tint); color: var(--accent-hi); font-size: var(--fs-sm); cursor: grab; }
.chip-name, .x { background: transparent; border: 0; color: inherit; font: inherit; min-height: 24px; padding: 0 6px; cursor: inherit; border-radius: var(--r-pill); }
.chip-name { padding-left: 10px; }
.x { padding-right: 9px; cursor: pointer; }
.x:hover { color: var(--bad); }
.none { font-size: 13px; }
.add select { min-height: 26px; padding: 0 6px; font-size: var(--fs-sm); background: transparent; border: 1px solid transparent; color: var(--text-2); border-radius: var(--r-md); cursor: pointer; max-width: 120px; }
.add select:hover, .add select:focus-visible { border-color: var(--line-strong); background: var(--hover); }
.uses { font-size: var(--fs-sm); }
.note { margin: var(--s-2) 0 0; font-size: var(--fs-sm); }
@media (max-width: 640px) {
  .map-row { grid-template-columns: minmax(0, 1fr) 28px; }
  .map-row.head .uses, .map-row.head span:nth-child(2) { display: none; }
  .map-row .chain { grid-column: 1 / -1; order: 3; }
  .map-row .uses { display: none; }
}
</style>
