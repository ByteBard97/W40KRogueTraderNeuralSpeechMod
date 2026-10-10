<script setup lang="ts">
import { computed, ref } from 'vue'
import { useSpeakerContext } from '../../composables/useSpeakerContext'
import { spreadPick } from '../../utils/spread'
import SectionCard from '../shared/SectionCard.vue'
import EmptyState from '../shared/EmptyState.vue'
import Btn from '../ui/Btn.vue'
import FilterBar from '../ui/FilterBar.vue'
import FilterChips from '../ui/FilterChips.vue'
import SearchField from '../ui/SearchField.vue'
import LineRow from './LineRow.vue'

const FIRST_PAGE = 8
const MORE = 20
const MAX_SHOW_ALL = 500
const TOP_EMOTIONS = 8
const TALLY_SHOWN = 4
const ALL = '__all'

const ctx = useSpeakerContext()
const query = ref('')
const emotion = ref<string | null>(null)
const shown = ref(FIRST_PAGE)
const allEmotions = ref(false)

const counts = computed(() => {
  const m = new Map<string, number>()
  for (const l of ctx.lines.value) if (l.emotion) m.set(l.emotion, (m.get(l.emotion) ?? 0) + 1)
  return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]))
})
const chips = computed(() => {
  const list = allEmotions.value ? counts.value : counts.value.slice(0, TOP_EMOTIONS)
  return [{ value: ALL, label: 'all', count: ctx.lines.value.length }, ...list.map(([value, count]) => ({ value, label: value, count }))]
})
const hidden = computed(() => Math.max(counts.value.length - TOP_EMOTIONS, 0))
const filtered = computed(() => {
  const q = query.value.trim().toLowerCase()
  return ctx.lines.value.filter((l) => (!emotion.value || l.emotion === emotion.value) && (!q || l.text.toLowerCase().includes(q)))
})
const visible = computed(() => filtered.value.slice(0, shown.value))
const ticked = computed(() => ctx.selectedLines.value.size)
const tally = computed(() => {
  const m = new Map<string, number>()
  for (const l of ctx.lines.value) if (ctx.selectedLines.value.has(l.guid)) m.set(l.emotion ?? 'none', (m.get(l.emotion ?? 'none') ?? 0) + 1)
  const parts = [...m.entries()].sort((a, b) => b[1] - a[1]).map(([e, n]) => `${e} ${n}`)
  return parts.length > TALLY_SHOWN ? `${parts.slice(0, TALLY_SHOWN).join(', ')} …` : parts.join(', ')
})
const summary = computed(() => `${ticked.value} of ${ctx.lines.value.length} ticked${tally.value ? ` · ${tally.value}` : ''}`)
const barPct = computed(() => (filtered.value.length ? Math.round((visible.value.length / filtered.value.length) * 100) : 100))
const chip = computed({
  get: () => emotion.value ?? ALL,
  set: (v) => { emotion.value = v === ALL ? null : (v as string); shown.value = FIRST_PAGE },
})

function toggle(guid: string, on: boolean) {
  const next = new Set(ctx.selectedLines.value)
  if (on) next.add(guid)
  else next.delete(guid)
  ctx.selectedLines.value = next
}
const spread = () => (ctx.selectedLines.value = new Set(spreadPick(ctx.lines.value)))
const clear = () => (ctx.selectedLines.value = new Set())
const speaker = computed(() => ctx.detail.value?.summary.name ?? '')
</script>

<template>
  <SectionCard title="Test lines" step="2" :summary="summary">
    <template #actions>
      <Btn size="sm" data-spread @click="spread">Pick 6 spread across emotions</Btn>
      <Btn size="sm" variant="ghost" data-clear @click="clear">Clear</Btn>
    </template>
    <EmptyState v-if="!ctx.lines.value.length" message="No lines for this speaker." />
    <div v-else class="body">
      <FilterBar>
        <SearchField v-model="query" class="grow" :placeholder="`Search ${ctx.lines.value.length} lines`" label="Search lines" />
        <FilterChips v-model="chip" :options="chips" aria-label="Filter by emotion" />
        <Btn v-if="hidden && !allEmotions" size="sm" variant="ghost" data-more-emotions @click="allEmotions = true">+{{ hidden }}</Btn>
      </FilterBar>
      <div>
        <LineRow v-for="l in visible" :key="l.guid" :line="l" :ticked="ctx.selectedLines.value.has(l.guid)" :speaker="speaker" @toggle="toggle(l.guid, $event)" />
        <p v-if="!filtered.length" class="muted none">No line matches.</p>
        <div v-if="filtered.length > FIRST_PAGE" class="foot">
          <span class="muted">Showing 1–{{ visible.length }} of {{ filtered.length }}</span>
          <div class="bar"><i :style="{ width: `${barPct}%` }" /></div>
          <Btn v-if="filtered.length > shown" size="sm" data-more @click="shown += MORE">Show {{ Math.min(MORE, filtered.length - shown) }} more</Btn>
          <Btn v-if="filtered.length > shown && filtered.length <= MAX_SHOW_ALL" size="sm" data-all @click="shown = filtered.length">Show all {{ filtered.length }}</Btn>
        </div>
      </div>
    </div>
  </SectionCard>
</template>

<style scoped>
.body { display: flex; flex-direction: column; gap: var(--s-3); }
.foot { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3); padding: 10px 6px; border-top: 1px solid var(--line); font-size: var(--fs-sm); }
.bar { flex: 1 1 120px; max-width: 240px; height: 6px; border-radius: 3px; background: var(--n-4); overflow: hidden; }
.bar i { display: block; height: 100%; background: var(--n-7); }
.none { padding: var(--s-3); margin: 0; }
</style>
