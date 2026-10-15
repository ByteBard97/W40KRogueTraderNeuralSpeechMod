<script setup lang="ts">
import { computed, ref } from 'vue'
import type { LabTake } from '../../api/labTypes'
import { useGlobalAudio } from '../../composables/globalAudio'
import { useLabStore } from '../../stores/lab'
import Btn from '../ui/Btn.vue'
import LabTakeCard, { type BoardEntry } from './LabTakeCard.vue'

const lab = useLabStore()
const audio = useGlobalAudio()
const marked = ref<string[]>([])
const MAX_MARKED = 2

const entries = computed<BoardEntry[]>(() => {
  const cur = lab.selected?.current
  const out: BoardEntry[] = cur ? [{ id: 'current', title: 'current', wav: cur.wav, metrics: cur }] : []
  return out.concat(lab.takes.map((t) => ({ id: t.id, title: t.label || t.id, wav: t.wav, seed: t.seed, recipe: t.recipe, metrics: t.metrics, pieces: t.pieces, take: t })))
})
const slotOf = (id: string) => (marked.value[0] === id ? 'A' : marked.value[1] === id ? 'B' : null)
function mark(id: string) {
  marked.value = marked.value.includes(id) ? marked.value.filter((x) => x !== id) : [...marked.value, id].slice(-MAX_MARKED)
}
const wavOf = (id: string | undefined) => entries.value.find((e) => e.id === id)?.wav
const play = (id: string | undefined) => {
  const w = wavOf(id)
  if (w) audio.play(w, undefined, { title: id === marked.value[0] ? 'A' : 'B', subtitle: 'Render lab' })
}
const take = (e: BoardEntry): LabTake | undefined => e.take
</script>

<template>
  <section class="takes" aria-label="Takes">
    <header class="head">
      <h2 class="list-head">Takes <span class="n">{{ lab.takes.length }}</span></h2>
      <div class="ab" data-ab>
        <Btn size="sm" :disabled="!wavOf(marked[0])" data-play-a @click="play(marked[0])">Play A</Btn>
        <Btn size="sm" :disabled="!wavOf(marked[1])" data-play-b @click="play(marked[1])">Play B</Btn>
        <span class="muted hint">Tick A/B on two takes to compare them.</span>
      </div>
    </header>
    <div class="board">
      <LabTakeCard
        v-for="e in entries"
        :key="e.id"
        :entry="e"
        :ab-slot="slotOf(e.id)"
        @mark="mark(e.id)"
        @rate="lab.updateTake(e.id, { rating: $event })"
        @note="lab.updateTake(e.id, { note: $event })"
        @hide="lab.updateTake(e.id, { hidden: true })"
        @load="take(e) && lab.loadRecipe(take(e)!.recipe)"
      />
      <p v-if="!entries.length" class="muted empty">No takes for this line yet. Render it to start.</p>
    </div>
  </section>
</template>

<style scoped>
.takes { display: flex; flex-direction: column; gap: var(--s-2); }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3); }
.ab { display: flex; gap: var(--s-2); align-items: center; }
.hint { font-size: var(--fs-sm); }
.board { display: grid; grid-template-columns: repeat(auto-fill, minmax(320px, 1fr)); gap: var(--s-3); }
.empty { grid-column: 1 / -1; }
</style>
