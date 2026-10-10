<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import type { Candidate, CloneTest, Verdict } from '../../api/types'
import { shortId } from '../../composables/useDesign'
import { moveItem } from '../../utils/order'
import EmptyState from '../shared/EmptyState.vue'
import CandidateRow from './CandidateRow.vue'

const props = withDefaults(
  defineProps<{
    candidates: Candidate[]
    /** Candidate ids ticked as clone sources. */
    sourceIds: Set<string>
    pickId: string | null
    clones?: CloneTest[]
    speaker: string
    canRenderTests?: boolean
  }>(),
  { clones: () => [], canRenderTests: false },
)
const emit = defineEmits<{
  reorder: [order: string[]]
  verdict: [cand: string, patch: Verdict]
  pick: [cand: string]
  reject: [cand: string]
  source: [cand: string, on: boolean]
}>()

const root = ref<HTMLElement | null>(null)
const ids = computed(() => props.candidates.map((c) => c.id))
const clonesFor = (id: string) => props.clones.filter((c) => c.candidate === id)
const dragFrom = ref<number | null>(null)

async function move(from: number, to: number) {
  if (to < 0 || to >= ids.value.length || from === to) return
  const id = ids.value[from]
  emit('reorder', moveItem(ids.value, from, to))
  await nextTick()
  root.value?.querySelector<HTMLElement>(`[data-cand="${shortId(id)}"]`)?.focus()      // keep keyboard focus on the row that moved
}
function drop(to: number) {
  if (dragFrom.value !== null) void move(dragFrom.value, to)
  dragFrom.value = null
}
</script>

<template>
  <EmptyState v-if="!candidates.length" message="No candidates yet. Open Live design below and generate one." />
  <div v-else ref="root" role="listbox" aria-label="Candidates in rank order" aria-multiselectable="false">
    <div v-for="(c, i) in candidates" :key="c.id" role="presentation" draggable="true" @dragstart="dragFrom = i" @dragover.prevent @drop.prevent="drop(i)">
      <CandidateRow
        :cand="c"
        :rank="i + 1"
        :picked="pickId === c.id"
        :is-source="sourceIds.has(c.id)"
        :clones="clonesFor(c.id)"
        :speaker="speaker"
        :first="i === 0"
        :last="i === candidates.length - 1"
        :can-render-tests="canRenderTests"
        @verdict="emit('verdict', c.id, $event)"
        @pick="emit('pick', c.id)"
        @reject="emit('reject', c.id)"
        @move="move(i, i + $event)"
        @source="emit('source', c.id, $event)"
      />
    </div>
  </div>
</template>
