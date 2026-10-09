<script setup lang="ts">
import { computed, inject, ref } from 'vue'
import type { Candidate, Verdict } from '../../api/types'
import { useAudioPlayer } from '../../composables/useAudioPlayer'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'
import { moveItem } from '../../utils/order'
import EmptyState from '../shared/EmptyState.vue'
import StarRating from '../shared/StarRating.vue'

const ACCENTS = ['british', 'american', 'other'] as const
const props = defineProps<{ candidates: Candidate[]; order: string[] }>()
const emit = defineEmits<{ reorder: [order: string[]]; verdict: [v: { cand: string } & Verdict] }>()
const { play } = useAudioPlayer()
const ctx = inject(SPEAKER_CTX_KEY, null)   // absent when the ranker is mounted on its own (tests)

const isSource = (id: string) => ctx?.selectedSources.value.has(`cand:${id}`) ?? false
function toggleSource(id: string, on: boolean) {
  if (!ctx) return
  const next = new Set(ctx.selectedSources.value)
  on ? next.add(`cand:${id}`) : next.delete(`cand:${id}`)
  ctx.selectedSources.value = next
}

const rows = computed(() => {
  const ranked = props.order.filter((id) => props.candidates.some((c) => c.id === id))
  const byId = new Map(props.candidates.map((c) => [c.id, c]))
  return [...ranked.map((id) => byId.get(id)!), ...props.candidates.filter((c) => !ranked.includes(c.id))]
})
const ids = computed(() => rows.value.map((c) => c.id))
const dragFrom = ref<number | null>(null)

function move(from: number, to: number) {
  if (to < 0 || to >= ids.value.length || from === to) return
  emit('reorder', moveItem(ids.value, from, to))
}
function drop(to: number) {
  if (dragFrom.value !== null) move(dragFrom.value, to)
  dragFrom.value = null
}
</script>

<template>
  <EmptyState v-if="!rows.length" message="No candidates yet. Generate one above." />
  <div
    v-for="(c, i) in rows"
    :key="c.id"
    class="cand"
    :class="{ picked: i === 0 && order.length }"
    draggable="true"
    @dragstart="dragFrom = i"
    @dragover.prevent
    @drop.prevent="drop(i)"
  >
    <span class="grip" title="drag to rank">⠇</span>
    <input v-if="ctx" type="checkbox" data-source title="use as a clone source" :checked="isSource(c.id)" @change="toggleSource(c.id, ($event.target as HTMLInputElement).checked)" />
    <b class="rank">{{ i + 1 }}.</b>
    <button class="play" @click="play(c.file)">▶</button>
    <span>{{ c.id.replace('.wav', '') }}</span>
    <span v-if="c.scores" class="chip" :class="c.scores.p_us > 0.5 ? 'us' : 'good'">p_us {{ c.scores.p_us.toFixed(2) }}</span>
    <span v-if="c.gen?.seed !== undefined" class="chip">seed {{ c.gen.seed }}</span>
    <span v-else class="chip warn" data-no-seed title="made before seeds were recorded; the WAV is the only copy">no recorded seed</span>
    <span class="grow" />
    <button v-for="a in ACCENTS" :key="a" :data-accent="a" :class="{ on: c.verdict.accent === a }" @click="emit('verdict', { cand: c.id, accent: a })">{{ a }}</button>
    <StarRating :model-value="c.verdict.fit ?? 0" @update:model-value="emit('verdict', { cand: c.id, fit: $event })" />
    <button data-reject :class="{ on: c.verdict.reject }" @click="emit('verdict', { cand: c.id, reject: !c.verdict.reject })">reject</button>
    <button data-move="up" :disabled="i === 0" aria-label="move up" @click="move(i, i - 1)">↑</button>
    <button data-move="down" :disabled="i === rows.length - 1" aria-label="move down" @click="move(i, i + 1)">↓</button>
  </div>
</template>

<style scoped>
.cand { display: flex; gap: 6px; align-items: center; flex-wrap: wrap; padding: 6px 0; border-top: 1px solid var(--line); }
.cand.picked:first-of-type { outline: 2px solid var(--ok); outline-offset: -2px; }
.grip { cursor: grab; color: var(--dim); }
.rank { color: var(--acc); }
.grow { flex: 1; }
.play { width: 28px; height: 28px; padding: 0; border-radius: 50%; }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); }
.chip.us { border-color: var(--bad); color: var(--bad); }
.chip.good { border-color: var(--ok); color: var(--ok); }
.chip.warn { border-color: var(--warn); color: var(--warn); }
button.on { background: var(--acc); color: var(--on-acc); border-color: var(--acc); }
</style>
