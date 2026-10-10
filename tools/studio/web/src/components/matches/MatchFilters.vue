<script setup lang="ts">
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import type { MatchCounts, MatchFilter } from '../../api/types'
import FilterBar from '../ui/FilterBar.vue'
import SearchField from '../ui/SearchField.vue'
import SelectField from '../ui/SelectField.vue'
import Seg from '../ui/Seg.vue'

const TYPE_DEBOUNCE_MS = 250
const props = defineProps<{ modelValue: MatchFilter; counts: MatchCounts | null }>()
const emit = defineEmits<{ 'update:modelValue': [filter: MatchFilter] }>()

const STATES = [
  { value: 'unreviewed', label: 'Not reviewed' },
  { value: 'reviewed', label: 'Reviewed' },
  { value: 'accept', label: 'Accepted' },
  { value: 'reject', label: 'Rejected' },
  { value: '', label: 'Any' },
]
const n = (v: number | undefined) => (v === undefined ? '' : ` ${v}`)
const groups = computed(() => {
  const c = props.counts
  const all = c ? (c.total ?? c.flagged + c.bank + c.nobank) : undefined
  return [
    { value: 'flagged', label: `Flagged${n(c?.flagged)}` },
    { value: 'bank', label: `Has bank${n(c?.bank)}` },
    { value: 'nobank', label: `No bank${n(c?.nobank)}` },
    { value: '', label: `All${n(all)}` },
  ]
})

/** Text fields wait for a pause in typing before they ask the server. */
const speaker = ref(props.modelValue.speaker ?? '')
const q = ref(props.modelValue.q ?? '')
const set = (patch: Partial<MatchFilter>) => emit('update:modelValue', { ...props.modelValue, speaker: speaker.value, q: q.value, ...patch })
let timer: ReturnType<typeof setTimeout> | undefined
const later = (patch: () => Partial<MatchFilter>) => {
  clearTimeout(timer)
  timer = setTimeout(() => set(patch()), TYPE_DEBOUNCE_MS)
}
watch(speaker, () => later(() => ({ speaker: speaker.value })))
watch(q, () => later(() => ({ q: q.value })))
watch(() => props.modelValue, (f) => { speaker.value = f.speaker ?? ''; q.value = f.q ?? '' })
onBeforeUnmount(() => clearTimeout(timer))
</script>

<template>
  <FilterBar>
    <Seg :model-value="modelValue.group ?? ''" :options="groups" aria-label="Group" @update:model-value="set({ group: String($event) })" />
    <SelectField label="Decision" :options="STATES" :model-value="modelValue.state ?? ''" @update:model-value="set({ state: $event })" />
    <label class="field speaker"><span class="lbl">Speaker</span><input v-model="speaker" placeholder="any" aria-label="Proposed speaker" /></label>
    <SearchField v-model="q" class="grow" placeholder="Search names and lines" label="Search names and lines" />
  </FilterBar>
</template>

<style scoped>
.speaker { width: 180px; }
@media (max-width: 480px) { .speaker { width: 100%; } }
</style>
