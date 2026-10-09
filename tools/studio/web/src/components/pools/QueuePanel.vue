<script setup lang="ts">
import { computed, reactive, ref } from 'vue'
import type { OverrideBody, PoolSlot, QueueEntry } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

const NARRATOR = 'narrator'
const SLOT = 'slot:'
const SPEAKER = 'speaker:'
const PAGE = 15
const props = defineProps<{ entries: QueueEntry[]; slots: Pick<PoolSlot, 'id' | 'name'>[] }>()
const emit = defineEmits<{ accept: [entry: string]; move: [entry: string, target: Pick<OverrideBody, 'to' | 'slot' | 'speaker'>] }>()
const choice = reactive<Record<string, string>>({})
const shown = ref(PAGE)
const visible = computed(() => props.entries.slice(0, shown.value))

function routed(e: QueueEntry): string {
  if (e.slot) return `${SLOT}${e.slot}`
  if (e.to === 'speaker' && e.speaker) return `${SPEAKER}${e.speaker}`
  return NARRATOR
}
const current = (e: QueueEntry) => choice[e.key] ?? routed(e)
function move(e: QueueEntry) {
  if (!e.entry) return
  const v = current(e)
  if (v.startsWith(SLOT)) emit('move', e.entry, { to: 'slot', slot: v.slice(SLOT.length) })
  else if (v.startsWith(SPEAKER)) emit('move', e.entry, { to: 'speaker', speaker: v.slice(SPEAKER.length) })
  else emit('move', e.entry, { to: 'narrator' })
}
</script>

<template>
  <EmptyState v-if="!props.entries.length" message="Nothing needs review." />
  <div v-for="e in visible" :key="e.key" class="entry">
    <div class="head">
      <b>{{ e.name ?? e.label }}</b>
      <span class="dim">{{ e.lines }} lines</span>
      <span v-for="r in e.reasons" :key="r" class="chip">{{ r }}</span>
      <span v-if="e.attr" class="dim">{{ e.attr.gender }} {{ e.attr.species }} {{ e.attr.age }}</span>
    </div>
    <p v-for="s in e.samples" :key="s" class="sample">“{{ s }}”</p>
    <p v-if="e.evidence.length" class="dim">evidence: {{ e.evidence.join(' · ') }}</p>
    <div class="acts">
      <button data-accept :disabled="!e.entry" @click="e.entry && emit('accept', e.entry)">Accept {{ e.slot ?? e.speaker ?? e.to }}</button>
      <select :value="current(e)" @change="choice[e.key] = ($event.target as HTMLSelectElement).value">
        <option v-for="s in props.slots" :key="s.id" :value="`${SLOT}${s.id}`">{{ s.name }}</option>
        <option v-if="e.speaker" :value="`${SPEAKER}${e.speaker}`">{{ e.speaker }} (game voice)</option>
        <option :value="NARRATOR">narrator</option>
      </select>
      <button data-move :disabled="!e.entry" @click="move(e)">Move</button>
    </div>
  </div>
  <button v-if="props.entries.length > shown" data-more @click="shown += PAGE">Show {{ Math.min(PAGE, props.entries.length - shown) }} more of {{ props.entries.length - shown }}</button>
</template>

<style scoped>
.entry { border-top: 1px solid var(--line); padding: 8px 0; }
.head { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; }
.chip { border: 1px solid var(--warn); color: var(--warn); border-radius: 10px; padding: 0 7px; font-size: 11px; }
.sample { margin: 3px 0; }
.acts { display: flex; gap: 8px; margin-top: 4px; }
.dim { color: var(--dim); font-size: 12px; }
</style>
