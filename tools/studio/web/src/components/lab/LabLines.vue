<script setup lang="ts">
import { computed } from 'vue'
import { useLabStore } from '../../stores/lab'
import type { LineFilter, LineSort } from '../../utils/labRecipe'
import Btn from '../ui/Btn.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import SearchField from '../ui/SearchField.vue'
import Seg from '../ui/Seg.vue'
import SelectField from '../ui/SelectField.vue'
import CrestBadge from './CrestBadge.vue'

const lab = useLabStore()
const SORTS: { value: LineSort; label: string }[] = [{ value: 'order', label: 'line order' }, { value: 'worst', label: 'worst first' }]
const FILTERS: { value: LineFilter; label: string }[] = [{ value: 'all', label: 'all' }, { value: 'flagged', label: 'flagged' }]
const speakerOptions = computed(() => lab.speakers.map((s) => ({ value: s.speaker, label: `${s.speaker} (${s.lines})` })))
const secs = (s: number | undefined) => (s === undefined ? '–' : `${s.toFixed(1)}s`)
</script>

<template>
  <section class="lines vs-card" aria-label="Lines">
    <div class="head">
      <h2 class="list-head">Lines <span class="n">{{ lab.visible.length }} / {{ lab.lines.length }}</span></h2>
      <SelectField label="Speaker" :options="speakerOptions" :model-value="lab.speaker" @update:model-value="lab.pickSpeaker" />
      <SearchField v-model="lab.query" placeholder="Search text" label="Search lines" :focus-key="false" />
      <div class="row">
        <Seg v-model="lab.sort" :options="SORTS" aria-label="Sort lines" />
        <Seg v-model="lab.filter" :options="FILTERS" aria-label="Filter lines" />
      </div>
      <div class="row">
        <Btn size="sm" data-check-flagged :disabled="!lab.flaggedGuids.length" @click="lab.checkFlagged()">Select all flagged ({{ lab.flaggedGuids.length }})</Btn>
        <Btn size="sm" variant="ghost" :disabled="!lab.checked.length" @click="lab.clearChecked()">Clear ({{ lab.checked.length }})</Btn>
      </div>
    </div>
    <ul class="list">
      <li v-for="l in lab.visible" :key="l.guid" class="item" :class="{ sel: l.guid === lab.selectedGuid }" data-line>
        <input type="checkbox" class="chk" :checked="lab.checked.includes(l.guid)" :aria-label="`Select line ${l.guid} for batch`" @change="lab.toggleCheck(l.guid)" />
        <button type="button" class="pick" :aria-current="l.guid === lab.selectedGuid ? 'true' : undefined" @click="lab.select(l.guid)">
          <span class="txt">{{ l.text }}</span>
          <span class="meta num">{{ l.chars }} ch · {{ secs(l.current?.seconds) }}</span>
        </button>
        <CrestBadge :metrics="l.current" />
        <InlinePlay :id="l.current?.wav ?? null" :title="`Current render`" :subtitle="l.guid" unavailable-reason="No current render" />
      </li>
      <li v-if="!lab.visible.length" class="empty muted">No lines match.</li>
    </ul>
  </section>
</template>

<style scoped>
.lines { display: flex; flex-direction: column; min-width: 0; }
.head { display: flex; flex-direction: column; gap: var(--s-2); padding: 0 var(--s-3) var(--s-3); }
.row { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.list { list-style: none; margin: 0; padding: 0; max-height: 70vh; overflow-y: auto; border-top: 1px solid var(--line); }
.item { display: grid; grid-template-columns: auto minmax(0, 1fr) auto auto; gap: var(--s-2); align-items: center; padding: var(--s-1) var(--s-2); border-bottom: 1px solid var(--line); }
.item.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); }
.chk { margin: 0; }
.pick { display: flex; flex-direction: column; gap: 2px; text-align: left; border: 0; background: transparent; padding: var(--s-1); min-width: 0; cursor: pointer; }
.txt { display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; font-size: 13px; }
.meta { font-size: var(--fs-xs); color: var(--text-3); }
.empty { padding: var(--s-4); text-align: center; }
</style>
