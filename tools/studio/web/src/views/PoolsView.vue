<script setup lang="ts">
import { computed, nextTick, onMounted, ref, watch } from 'vue'
import AttentionTiles from '../components/pools/AttentionTiles.vue'
import QueuePanel from '../components/pools/QueuePanel.vue'
import RoutesTable from '../components/pools/RoutesTable.vue'
import RoutingSummary from '../components/pools/RoutingSummary.vue'
import SlotList from '../components/pools/SlotList.vue'
import SpotCheck from '../components/pools/SpotCheck.vue'
import EmptyState from '../components/shared/EmptyState.vue'
import Btn from '../components/ui/Btn.vue'
import Icon from '../components/ui/Icon.vue'
import InlineError from '../components/ui/InlineError.vue'
import Skeleton from '../components/ui/Skeleton.vue'
import { type PoolZone, usePoolKeys } from '../composables/usePoolKeys'
import { useShortcuts } from '../composables/useShortcuts'
import { type DestFilter, usePoolRoutesStore } from '../stores/poolRoutes'
import { usePoolsStore } from '../stores/pools'

const pools = usePoolsStore()
const routes = usePoolRoutesStore()
const zone = ref<PoolZone>('review')
const spotSlotId = ref<string | null>(null)
const spot = ref<InstanceType<typeof SpotCheck> | null>(null)

const spotSlot = computed(() => pools.slots.find((s) => s.id === spotSlotId.value) ?? null)
const fmt = (n: number) => n.toLocaleString('en-US')

function scrollTo(selector: string) {
  void nextTick(() => document.querySelector(selector)?.scrollIntoView({ block: 'start', behavior: 'smooth' }))
}
function startReview() {
  zone.value = 'review'
  pools.select(pools.ordered[0]?.key ?? '')
  scrollTo('#review')
}
function openSpot(id: string) {
  spotSlotId.value = spotSlotId.value === id ? null : id
  zone.value = 'spot'
  if (spotSlotId.value) scrollTo('#spot')
}
function nextSlot() {
  if (pools.nextUnchecked) openSpot(pools.nextUnchecked.id)
}
function filterRoutes(d: Exclude<DestFilter, ''>) {
  void routes.setDest(d)
  scrollTo('#routes')
}
function focusMove() {
  document.querySelector<HTMLSelectElement>('[data-current] select')?.focus()
}

usePoolKeys(zone, () => (spotSlot.value ? spot.value : null), focusMove)
useShortcuts({
  title: 'Pools',
  groups: [
    { title: 'Review queue', items: [
      { label: 'Start review', keys: ['R'] },
      { label: 'Accept the guess', keys: ['A'] },
      { label: 'Move to the chosen voice', keys: ['M'] },
      { label: 'Skip for now', keys: ['S'] },
      { label: 'Next / previous entry', keys: ['J', 'K'] },
      { label: 'Undo the last change', keys: ['Z'] },
    ] },
    { title: 'Spot check (after clicking in it)', items: [
      { label: 'Mark right / wrong', keys: ['Y', 'W'] },
      { label: 'Next / previous line', keys: ['J', 'K'] },
    ] },
    { title: 'Routes', items: [{ label: 'Search lines', keys: ['/'] }] },
  ],
})

onMounted(() => {
  void pools.load()
  document.addEventListener('keydown', onR)
})
function onR(e: KeyboardEvent) {
  const t = e.target as HTMLElement | null
  if (e.key.toLowerCase() !== 'r' || e.ctrlKey || e.metaKey || e.altKey || ['INPUT', 'SELECT', 'TEXTAREA'].includes(t?.tagName ?? '')) return
  if (pools.summary && pools.ordered.length) startReview()
}
watch(() => pools.cursor, () => void nextTick(() => document.querySelector('[data-current]')?.scrollIntoView({ block: 'nearest' })))
</script>

<template>
  <div class="page">
    <div class="page-head">
      <div class="titles">
        <h1 class="page-title">Pools</h1>
        <span v-if="pools.summary" class="page-sub">{{ fmt(pools.summary.total) }} unnamed lines routed · built {{ pools.summary.built }} · confidence threshold {{ pools.summary.threshold }}</span>
      </div>
      <div v-if="pools.summary" class="head-end">
        <span class="saved" role="status"><Icon name="check" :size="14" />Decisions saved</span>
        <Btn data-rebuild @click="pools.rebuild">Rebuild routing <span class="muted small">keeps your decisions</span></Btn>
      </div>
    </div>

    <InlineError v-if="pools.error" title="Could not load the pools">{{ pools.error }} <Btn size="sm" @click="pools.load">Retry</Btn></InlineError>
    <EmptyState v-if="pools.notBuilt" title="The pools are not built yet" message="Building routes every unnamed line and registers the slots as designed speakers.">
      <Btn variant="primary" data-build @click="pools.rebuild">Build pools</Btn>
    </EmptyState>

    <template v-else-if="pools.summary">
      <AttentionTiles
        :queue-entries="pools.summary.queue_entries" :queue-lines="pools.summary.queue_lines" :threshold="pools.summary.threshold"
        :checked="pools.checkedSlots" :slot-total="pools.slots.length" :overrides="pools.summary.overrides ?? 0" :has-next-slot="!!pools.nextUnchecked"
        @review="startReview" @next-slot="nextSlot"
      />
      <RoutingSummary :summary="pools.summary" @filter="filterRoutes" />
      <div class="split">
        <div class="main" @pointerdown.capture="zone = 'review'" @focusin="zone = 'review'"><QueuePanel /></div>
        <aside class="side">
          <SlotList :slots="pools.slots" :selected-id="spotSlotId" @rename="pools.rename" @merge="pools.merge" @spot="openSpot" @create="pools.createSlot" />
          <div v-if="spotSlot" @pointerdown.capture="zone = 'spot'" @focusin="zone = 'spot'"><SpotCheck ref="spot" :key="spotSlot.id" :slot-id="spotSlot.id" :slot-name="spotSlot.name" /></div>
          <p v-else class="hint">Pick “Spot check” on a slot to listen to a sample of its lines.</p>
        </aside>
      </div>
      <RoutesTable />
    </template>
    <Skeleton v-else-if="pools.loading" :rows="6" />
  </div>
</template>

<style scoped>
.titles { display: flex; flex-direction: column; gap: var(--s-1); }
.head-end { margin-left: auto; display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.small { font-size: var(--fs-sm); }
.muted { color: var(--text-3); }
.hint { margin: 0; font-size: 13px; color: var(--text-3); }
.split > .side { flex: 1 1 420px; }
</style>
