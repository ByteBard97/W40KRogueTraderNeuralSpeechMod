<script setup lang="ts">
import { computed } from 'vue'
import type { NewSlotBody, PoolSampleItem, PoolSlot, QueueEntry } from '../../api/types'
import { usePoolsStore } from '../../stores/pools'
import { NEW_VOICE_VALUE, routeValue, targetLabel, targetOptions } from '../../utils/poolTargets'
import Btn from '../ui/Btn.vue'
import Flag from '../ui/Flag.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import SelectField from '../ui/SelectField.vue'
import NewVoiceForm from './NewVoiceForm.vue'

const props = defineProps<{ entry: QueueEntry; slots: Pick<PoolSlot, 'id' | 'name'>[]; current: boolean }>()
const emit = defineEmits<{ select: [] }>()
const pools = usePoolsStore()

const name = computed(() => props.entry.name ?? props.entry.label)
const guess = computed(() => {
  const a = props.entry.attr
  return a ? [a.gender, a.species, props.entry.role ?? 'unknown role'].filter(Boolean).join(' · ') : (props.entry.role ?? 'no guess')
})
const samples = computed<PoolSampleItem[]>(() => props.entry.sample_items ?? props.entry.samples.map((text) => ({ guid: text, text, wav: null })))
const options = computed(() => [...targetOptions(props.slots, props.entry.speaker), { value: NEW_VOICE_VALUE, label: 'New designed voice…' }])
const dest = computed(() => targetLabel(routeValue(props.entry), props.slots))
const creating = computed(() => pools.creating === props.entry.key)
const playTitle = (s: PoolSampleItem) => (s.text.length > 60 ? `${s.text.slice(0, 60)}…` : s.text)
const create = (body: NewSlotBody) => pools.moveToNewVoice(props.entry, body)
</script>

<template>
  <article class="rq" :class="{ cur: current }" :data-current="current ? '' : undefined" :aria-current="current ? 'true' : undefined" @pointerdown="emit('select')" @focusin="emit('select')">
    <div class="head">
      <b class="name">{{ name }}</b>
      <span class="num muted small">{{ entry.lines }} {{ entry.lines === 1 ? 'line' : 'lines' }}</span>
      <Flag v-for="r in entry.reasons" :key="r">{{ r }}</Flag>
      <span class="muted small guess">guess: {{ guess }}</span>
    </div>
    <div class="samples">
      <div v-for="s in samples" :key="s.guid" class="sample">
        <InlinePlay class="pl" :id="s.wav" :title="playTitle(s)" :subtitle="name" unavailable-reason="This line is not rendered yet" />
        <q>{{ s.text }}</q>
      </div>
    </div>
    <details v-if="entry.evidence.length">
      <summary class="muted small">Evidence ({{ entry.evidence.length }})</summary>
      <ul class="ev" data-evidence><li v-for="(e, i) in entry.evidence" :key="i">{{ e }}</li></ul>
    </details>
    <div class="acts">
      <Btn variant="good" data-accept :disabled="!entry.entry" :kbd="current ? 'A' : undefined" @click="pools.accept(entry)">Accept {{ dest }}</Btn>
      <SelectField class="mv" label="Move to" :options="options" :model-value="pools.chosen(entry)" @update:model-value="pools.setChoice(entry, $event)" />
      <Btn data-move :disabled="!entry.entry" :kbd="current ? 'M' : undefined" @click="pools.moveChosen(entry)">Move</Btn>
      <Btn variant="ghost" data-skip :kbd="current ? 'S' : undefined" @click="pools.skip(entry)">Skip</Btn>
    </div>
    <p v-if="!entry.entry" class="muted small">This group has no roster entry, so it cannot be accepted or moved as a whole. Use the routes table to move single lines.</p>
    <NewVoiceForm v-if="creating" :name="name" :gender="entry.attr?.gender" :species="entry.attr?.species" confirm-label="Create and move" @create="create" @cancel="pools.cancelCreate(entry)" />
  </article>
</template>

<style scoped>
.rq { display: flex; flex-direction: column; gap: var(--s-3); padding: var(--s-4); border-top: 1px solid var(--line); }
.rq.cur { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-radius: var(--r-md); border-top-color: transparent; }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); }
.name { font-size: var(--fs-lg); }
.pl { flex: none; }
.small { font-size: var(--fs-sm); }
.muted { color: var(--text-3); }
.guess { margin-left: auto; }
.samples { display: flex; flex-direction: column; gap: 6px; }
.sample { display: flex; gap: 10px; align-items: flex-start; }
q { display: block; font-size: var(--fs-md); line-height: 1.45; color: var(--text); quotes: "\201C" "\201D"; padding-top: 4px; }
summary { cursor: pointer; }
.ev { margin: 4px 0 0; padding-left: 18px; color: var(--text-2); font-size: var(--fs-md); line-height: var(--lh-body); }
.ev li + li { margin-top: 4px; }
.acts { display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.mv { min-width: 200px; }
p { margin: 0; }
</style>
