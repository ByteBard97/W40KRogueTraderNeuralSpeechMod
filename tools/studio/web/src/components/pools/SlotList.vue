<script setup lang="ts">
import { computed, ref } from 'vue'
import type { NewSlotBody, PoolSlot } from '../../api/types'
import { slotCheck } from '../../stores/pools'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'
import Btn from '../ui/Btn.vue'
import InlineConfirm from '../ui/InlineConfirm.vue'
import SelectField from '../ui/SelectField.vue'
import StatusDot, { type DotStatus } from '../ui/StatusDot.vue'
import NewVoiceForm from './NewVoiceForm.vue'

const props = defineProps<{ slots: PoolSlot[]; selectedId: string | null }>()
const emit = defineEmits<{ rename: [id: string, name: string]; merge: [id: string, into: string]; spot: [id: string]; create: [body: NewSlotBody] }>()

const editing = ref<string | null>(null)
const draft = ref('')
const merging = ref<string | null>(null)
const target = ref('')
const adding = ref(false)

const totalLines = computed(() => props.slots.reduce((a, s) => a + s.lines, 0))
const summary = computed(() => `${props.slots.length} · ${totalLines.value.toLocaleString('en-US')} lines`)
const fmt = (n: number) => n.toLocaleString('en-US')

const DOT: Record<ReturnType<typeof slotCheck>, DotStatus> = { unchecked: 'idle', clean: 'done', wrong: 'flag' }
function dotLabel(s: PoolSlot) {
  const c = slotCheck(s)
  return c === 'clean' ? 'spot-checked' : c === 'wrong' ? `${s.spot.wrong} wrong in spot check` : 'not checked'
}
const checkLabel = (s: PoolSlot) => (slotCheck(s) === 'unchecked' ? 'Spot check' : 'Re-check')

function startMerge(s: PoolSlot) {
  merging.value = merging.value === s.id ? null : s.id
  target.value = ''
}
const targets = (s: PoolSlot) => [{ value: '', label: 'Choose a slot…' }, ...props.slots.filter((x) => x.id !== s.id).map((x) => ({ value: x.id, label: x.name }))]
const targetSlot = computed(() => props.slots.find((x) => x.id === target.value))
function confirmMerge(s: PoolSlot) {
  if (!target.value) return
  emit('merge', s.id, target.value)
  merging.value = null
}
function edit(s: PoolSlot) {
  editing.value = s.id
  draft.value = s.name
}
function save(id: string) {
  if (draft.value.trim()) emit('rename', id, draft.value.trim())
  editing.value = null
}
function create(body: NewSlotBody) {
  adding.value = false
  emit('create', body)
}
</script>

<template>
  <SectionCard id="slots" title="Slots" :summary="summary">
    <template #actions><Btn size="sm" variant="ghost" data-new-voice :pressed="adding" @click="adding = !adding">New voice</Btn></template>
    <NewVoiceForm v-if="adding" class="nv" @create="create" @cancel="adding = false" />
    <EmptyState v-if="!slots.length" message="No slots yet. Rebuild the routing to make them." />
    <div class="rows">
      <template v-for="s in slots" :key="s.id">
        <div class="srow" :class="{ sel: selectedId === s.id }" :aria-current="selectedId === s.id ? 'true' : undefined">
          <StatusDot :status="DOT[slotCheck(s)]" :label="dotLabel(s)" />
          <span v-if="editing === s.id" class="main edit">
            <label class="field"><span class="vh">Slot name</span><input v-model="draft" data-rename-input @keydown.enter.prevent="save(s.id)" @keydown.esc.stop="editing = null" /></label>
            <Btn size="sm" variant="primary" data-save-name @click="save(s.id)">Save</Btn>
          </span>
          <span v-else class="main nm">
            <RouterLink :to="`/speakers/${s.slug}`">{{ s.name }}</RouterLink>
            <button type="button" class="rn" data-rename :aria-label="`Rename ${s.name}`" @click="edit(s)">rename</button>
          </span>
          <span class="num muted lines">{{ fmt(s.lines) }}</span>
          <span class="end">
            <Btn size="sm" variant="ghost" data-spot :pressed="selectedId === s.id" @click="emit('spot', s.id)">{{ checkLabel(s) }}</Btn>
            <Btn v-if="slots.length > 1" size="sm" variant="ghost" data-merge :pressed="merging === s.id" @click="startMerge(s)">Merge</Btn>
          </span>
        </div>
        <div v-if="merging === s.id" class="merge">
          <SelectField v-model="target" label="Merge into" :options="targets(s)" data-merge-target-field />
          <InlineConfirm v-if="targetSlot" confirm-label="Merge" data-merge-confirm @confirm="confirmMerge(s)" @cancel="merging = null">
            <span data-merge-note><b>{{ fmt(s.lines) }} {{ s.lines === 1 ? 'line' : 'lines' }}</b> move to {{ targetSlot.name }}; the slot and its name are removed.</span>
          </InlineConfirm>
        </div>
      </template>
    </div>
  </SectionCard>
</template>

<style scoped>
.rows { margin: 0 calc(var(--s-2) * -1); }
.srow { display: flex; align-items: center; gap: var(--s-2); min-height: 44px; padding: 6px var(--s-3); border-top: 1px solid var(--line); }
.srow:first-child { border-top: 0; }
.srow:hover { background: var(--hover); }
.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-top-color: transparent; border-radius: var(--r-md); }
.main { flex: 1 1 100px; min-width: 0; }
.end { display: flex; align-items: center; gap: var(--s-1); flex: none; }
.nv { margin-bottom: var(--s-3); }
.nm { display: inline-flex; align-items: baseline; gap: var(--s-2); }
.rn { white-space: nowrap; }
.nm a { color: var(--text); font-weight: 600; text-decoration: none; }
.nm a:hover { color: var(--accent-hi); text-decoration: underline; }
.rn { background: transparent; border: 0; padding: 0; min-height: 0; color: var(--text-3); font-size: var(--fs-xs); cursor: pointer; }
.rn:hover { color: var(--text); text-decoration: underline; }
.edit { display: flex; gap: var(--s-2); align-items: center; }
.lines { font-size: var(--fs-sm); min-width: 48px; text-align: right; }
.merge { display: flex; flex-direction: column; gap: var(--s-2); margin: var(--s-1) var(--s-3) var(--s-3); }
</style>
