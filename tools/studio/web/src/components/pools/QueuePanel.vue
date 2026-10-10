<script setup lang="ts">
import { computed, ref } from 'vue'
import { usePoolsStore } from '../../stores/pools'
import EmptyState from '../shared/EmptyState.vue'
import SectionCard from '../shared/SectionCard.vue'
import Btn from '../ui/Btn.vue'
import QueueCard from './QueueCard.vue'

const PAGE = 5
const PERCENT = 100
const pools = usePoolsStore()
const shown = ref(PAGE)
const visible = computed(() => pools.ordered.slice(0, Math.max(shown.value, pools.cursor + 1)))
const hidden = computed(() => pools.ordered.length - visible.value.length)
const position = computed(() => (pools.ordered.length ? `${pools.cursor + 1} of ${pools.ordered.length}` : 'nothing left'))
const pct = computed(() => Math.round(pools.reviewFraction * PERCENT))
</script>

<template>
  <SectionCard id="review" title="Review queue" :summary="`${position} · low-confidence routes, biggest first`">
    <template #actions><span class="keys">A accept · M move · S skip · J K move</span></template>
    <div class="bar" role="progressbar" aria-label="Review progress" :aria-valuenow="pct" aria-valuemin="0" aria-valuemax="100"><i :style="{ width: `${pct}%` }" /></div>
    <EmptyState v-if="!pools.ordered.length" title="Nothing needs review" message="Every unnamed line is routed with enough confidence. New matches and rebuilds can add entries here." />
    <div class="list">
      <QueueCard v-for="e in visible" :key="e.key" :entry="e" :slots="pools.slots" :current="pools.current?.key === e.key" @select="pools.select(e.key)" />
    </div>
    <Btn v-if="hidden > 0" size="sm" class="more" data-more @click="shown += PAGE">Show {{ Math.min(PAGE, hidden) }} more ({{ hidden }} left)</Btn>
  </SectionCard>
</template>

<style scoped>
.keys { font-size: var(--fs-sm); color: var(--text-3); }
.bar { height: 4px; border-radius: 2px; background: var(--n-4); overflow: hidden; margin-bottom: var(--s-3); }
.bar i { display: block; height: 100%; background: var(--good); }
.list { display: flex; flex-direction: column; }
.more { margin-top: var(--s-3); }
</style>
