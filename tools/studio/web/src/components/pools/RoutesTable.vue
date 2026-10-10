<script setup lang="ts">
import { onMounted, watch } from 'vue'
import type { PoolRoute } from '../../api/types'
import { usePoolRoutesStore, type DestFilter } from '../../stores/poolRoutes'
import { usePoolsStore } from '../../stores/pools'
import { NARRATOR_VALUE, parseTarget, slotValue } from '../../utils/poolTargets'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'
import ActiveFilters from '../ui/ActiveFilters.vue'
import Btn from '../ui/Btn.vue'
import FilterBar from '../ui/FilterBar.vue'
import InlineError from '../ui/InlineError.vue'
import InlinePlay from '../ui/InlinePlay.vue'
import SearchField from '../ui/SearchField.vue'
import SelectField from '../ui/SelectField.vue'
import Tag from '../ui/Tag.vue'

const PERCENT = 100
const pools = usePoolsStore()
const routes = usePoolRoutesStore()

const DESTS: { value: DestFilter; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'slot', label: 'Shared slot' },
  { value: 'bank', label: 'Speaker with bank' },
  { value: 'nobank', label: 'Named, no bank' },
  { value: 'narrator', label: 'Narrator' },
]
const slotName = (id?: string) => pools.slots.find((s) => s.id === id)?.name ?? id ?? ''
const slotOptions = () => [{ value: '', label: 'All' }, ...pools.slots.map((s) => ({ value: s.id, label: s.name }))]
const entry = (r: PoolRoute) => r.entry_name ?? r.entry_label ?? '—'
function dest(r: PoolRoute) {
  if (r.to === 'slot') return `Slot · ${slotName(r.slot)}`
  if (r.to === 'speaker') return r.has_bank ? `Speaker · ${r.speaker} (bank)` : `Named · ${r.speaker}`
  return 'Narrator'
}
const isLow = (r: PoolRoute) => r.confidence !== null && r.confidence < pools.summary!.threshold
const title = (t: string) => (t.length > 60 ? `${t.slice(0, 60)}…` : t)
const progress = () => (routes.total ? Math.round((routes.range.to / routes.total) * PERCENT) : 0)
const fmt = (n: number) => n.toLocaleString('en-US')

function override(r: PoolRoute, ev: Event) {
  const el = ev.target as HTMLSelectElement
  const v = el.value
  el.value = ''
  const t = parseTarget(v)
  if (t) void pools.moveLine(r.guid, t, v)
}

onMounted(routes.load)
watch(() => pools.revision, routes.load)
</script>

<template>
  <SectionCard id="routes" title="Routes" summary="every unnamed line and where it goes">
    <div class="body">
      <FilterBar>
        <SearchField class="grow" :model-value="routes.q" placeholder="Search line text or roster name" label="Search lines" @update:model-value="routes.search" />
        <SelectField label="Destination" :options="DESTS" :model-value="routes.dest" @update:model-value="routes.setDest($event as DestFilter)" />
        <SelectField label="Slot" :options="slotOptions()" :model-value="routes.slot" @update:model-value="routes.setSlot" />
        <SelectField label="Confidence" :options="[{ value: '', label: 'Any' }, { value: 'low', label: `Below ${pools.summary?.threshold ?? 0.8}` }]" :model-value="routes.lowConf ? 'low' : ''" @update:model-value="routes.setLowConf($event === 'low')" />
        <SelectField label="Review" :options="[{ value: '', label: 'All' }, { value: 'q', label: 'Needs review' }]" :model-value="routes.reviewOnly ? 'q' : ''" @update:model-value="routes.setReviewOnly($event === 'q')" />
      </FilterBar>
      <ActiveFilters :filters="routes.filters" :shown="routes.items.length" :total="routes.total" @remove="routes.remove" @clear="routes.clear" />
      <InlineError v-if="routes.error" title="Could not load the routes">{{ routes.error }}</InlineError>
      <EmptyState v-else-if="!routes.items.length && !routes.loading" message="No lines match these filters." />
      <div v-else class="tbl-wrap">
        <table class="tbl" aria-label="Routes">
          <thead>
            <tr><th class="play"><span class="vh">Play</span></th><th>Line</th><th class="hide-sm">Roster entry</th><th>Destination</th><th class="r hide-sm">Conf.</th><th>Override</th></tr>
          </thead>
          <tbody>
            <tr v-for="r in routes.items" :key="r.guid" data-route>
              <td><InlinePlay :id="r.wav ?? null" :title="title(r.text)" :subtitle="entry(r)" unavailable-reason="This line is not rendered yet" /></td>
              <td class="line">{{ r.text }}</td>
              <td class="nw hide-sm">{{ entry(r) }}</td>
              <td class="nw">{{ dest(r) }} <Tag v-if="r.source === 'override'" variant="plain">override</Tag></td>
              <td class="r num hide-sm" :class="{ muted: !isLow(r) }">{{ r.confidence === null ? '—' : r.confidence.toFixed(2) }}</td>
              <td>
                <select class="field ov" data-move-line aria-label="Move this line to" @change="override(r, $event)">
                  <option value="">—</option>
                  <option v-for="s in pools.slots" :key="s.id" :value="slotValue(s.id)">{{ s.name }}</option>
                  <option :value="NARRATOR_VALUE">Narrator</option>
                </select>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div class="pager">
        <span class="muted small num">{{ fmt(routes.range.from) }}–{{ fmt(routes.range.to) }} of {{ fmt(routes.total) }}</span>
        <div class="bar" aria-hidden="true"><i :style="{ width: `${progress()}%` }" /></div>
        <Btn size="sm" data-prev :disabled="routes.offset === 0" @click="routes.step(-1)">Previous</Btn>
        <Btn size="sm" data-next :disabled="routes.last" @click="routes.step(1)">Next 50</Btn>
      </div>
    </div>
  </SectionCard>
</template>

<style scoped>
.body { display: flex; flex-direction: column; gap: var(--s-3); }
.play { width: 40px; }
.line { min-width: 280px; }
.nw { white-space: nowrap; }
.muted { color: var(--text-3); }
.small { font-size: var(--fs-sm); }
.ov { min-height: 28px; font-size: var(--fs-sm); width: auto; min-width: 120px; }
.pager { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-3); }
.bar { flex: 0 1 240px; height: 4px; border-radius: 2px; background: var(--n-4); overflow: hidden; min-width: 80px; }
.bar i { display: block; height: 100%; background: var(--n-7); }
</style>
