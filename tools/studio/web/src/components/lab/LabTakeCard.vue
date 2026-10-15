<script setup lang="ts">
import { ref } from 'vue'
import type { LabMetrics, LabRecipe, LabTake, LabTakePiece } from '../../api/labTypes'
import { modelExceeded, recipeSummary } from '../../utils/labRecipe'
import StarRating from '../shared/StarRating.vue'
import Btn from '../ui/Btn.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import CrestBadge from './CrestBadge.vue'

/** One row of the takes board: the current render (a bare take with no recipe) or a lab take. */
export interface BoardEntry {
  id: string
  title: string
  wav: string
  seed?: number
  recipe?: LabRecipe
  metrics: Pick<LabMetrics, 'seconds' | 'crest_db' | 'flag' | 'clip_runs'> & { model_peak?: number }
  pieces?: LabTakePiece[]
  take?: LabTake
}
const props = defineProps<{ entry: BoardEntry; abSlot: 'A' | 'B' | null }>()
const emit = defineEmits<{ rate: [n: number]; note: [text: string]; hide: []; load: []; mark: [] }>()
const note = ref(props.entry.take?.note ?? '')
</script>

<template>
  <article class="take" :class="{ cur: !entry.take }" data-take>
    <header class="top">
      <InlinePlay :id="entry.wav" :title="entry.title" subtitle="Render lab" />
      <b class="title">{{ entry.title }}</b>
      <span v-if="entry.seed !== undefined" class="num muted">seed {{ entry.seed }}</span>
      <Btn size="sm" :variant="abSlot ? 'primary' : 'default'" :pressed="!!abSlot" data-mark @click="emit('mark')">{{ abSlot ? `Slot ${abSlot}` : 'A/B' }}</Btn>
    </header>
    <p v-if="entry.recipe" class="muted recipe" data-recipe>{{ recipeSummary(entry.recipe) }}</p>
    <div class="metrics">
      <span class="num">{{ entry.metrics.seconds.toFixed(2) }}s</span>
      <CrestBadge :metrics="entry.metrics" />
      <span class="num muted">{{ entry.metrics.clip_runs }} clip runs</span>
      <span v-if="entry.metrics.model_peak !== undefined && modelExceeded(entry.metrics.model_peak)" class="over" data-exceeded>model exceeded full scale ({{ entry.metrics.model_peak.toFixed(2) }})</span>
    </div>
    <ul v-if="entry.pieces && entry.pieces.length > 1" class="pieces">
      <li v-for="(p, i) in entry.pieces" :key="i" data-piece-crest><CrestBadge :metrics="p" /> <span v-if="p.level_db != null" class="num muted" data-level>{{ p.level_db }} dB</span> <span class="ptxt">{{ p.text }}</span></li>
    </ul>
    <div v-if="entry.take" class="foot">
      <StarRating :model-value="entry.take.rating" @update:model-value="emit('rate', $event)" />
      <input v-model="note" class="note" placeholder="note" aria-label="Note" @change="emit('note', note)" />
      <Btn size="sm" data-load @click="emit('load')">load this recipe</Btn>
      <Btn size="sm" variant="ghost" data-hide @click="emit('hide')">hide</Btn>
    </div>
  </article>
</template>

<style scoped>
.take { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); padding: var(--s-3); display: flex; flex-direction: column; gap: var(--s-2); min-width: 0; }
.take.cur { border-color: var(--info-line); }
.top { display: flex; align-items: center; gap: var(--s-2); }
.title { flex: 1 1 auto; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.recipe { margin: 0; font-family: var(--font-mono); font-size: var(--fs-xs); }
.metrics { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; font-size: var(--fs-sm); }
.over { color: var(--bad); font-weight: 600; font-size: var(--fs-sm); }
.pieces { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 2px; font-size: var(--fs-sm); }
.ptxt { color: var(--text-2); }
.foot { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.note { flex: 1 1 120px; min-width: 0; }
</style>
