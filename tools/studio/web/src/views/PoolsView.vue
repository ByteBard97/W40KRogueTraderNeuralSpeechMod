<script setup lang="ts">
import { onMounted } from 'vue'
import { api } from '../api/client'
import EmptyState from '../components/shared/EmptyState.vue'
import SectionCard from '../components/shared/SectionCard.vue'
import QueuePanel from '../components/pools/QueuePanel.vue'
import RoutingSummary from '../components/pools/RoutingSummary.vue'
import RoutesTable from '../components/pools/RoutesTable.vue'
import SlotList from '../components/pools/SlotList.vue'
import { usePoolsStore } from '../stores/pools'

const pools = usePoolsStore()
onMounted(pools.load)

async function rename(id: string, name: string) {
  try {
    await api.poolRename(id, name)
    await pools.load()
  } catch (e) {
    pools.error = e instanceof Error ? e.message : String(e)
  }
}
</script>

<template>
  <div>
    <h1>Pools</h1>
    <p v-if="pools.error" class="err">{{ pools.error }}</p>
    <template v-if="pools.notBuilt">
      <EmptyState message="The pools are not built yet. Building routes every unnamed line and registers the slots as designed speakers." />
      <button data-build class="primary" @click="pools.rebuild">Build pools</button>
    </template>
    <template v-else-if="pools.summary">
      <SectionCard title="1. Where the unnamed lines go">
        <RoutingSummary :summary="pools.summary" />
        <button data-rebuild @click="pools.rebuild">Rebuild (keeps your decisions)</button>
      </SectionCard>
      <SectionCard title="2. Slots"><SlotList :slots="pools.summary.slots" @rename="rename" /></SectionCard>
      <SectionCard title="3. Needs review (by roster entry)">
        <QueuePanel :entries="pools.queue" :slots="pools.summary.slots" @accept="pools.accept" @move="pools.move" />
      </SectionCard>
      <SectionCard title="4. All lines" collapsed-by-default><RoutesTable :slots="pools.summary.slots" /></SectionCard>
    </template>
    <EmptyState v-else-if="pools.loading" message="Loading…" />
  </div>
</template>

<style scoped>
h1 { font-size: 18px; margin: 0 0 8px; }
.primary { background: var(--acc); color: var(--on-acc); border-color: var(--acc); }
.err { color: var(--bad); }
</style>
