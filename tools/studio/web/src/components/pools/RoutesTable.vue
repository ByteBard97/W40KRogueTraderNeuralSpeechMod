<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { api } from '../../api/client'
import type { PoolRoute, PoolSlot } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

const PAGE = 25
const props = defineProps<{ slots: Pick<PoolSlot, 'id' | 'name'>[] }>()
const route = ref({ rows: [] as PoolRoute[], total: 0 })
const offset = ref(0)
const slot = ref('')
const to = ref('')
const queued = ref(false)
const error = ref('')

const last = computed(() => offset.value + PAGE >= route.value.total)

async function load() {
  error.value = ''
  try {
    const r = await api.poolRoutes({ to: to.value || undefined, slot: slot.value || undefined, queued: queued.value || undefined, offset: offset.value, limit: PAGE })
    route.value = { rows: r.items, total: r.total }
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
function refilter() {
  offset.value = 0
  void load()
}
function step(delta: number) {
  offset.value = Math.max(0, offset.value + delta * PAGE)
  void load()
}
async function move(guid: string, slotId: string) {
  if (!slotId) return
  try {
    await api.poolOverride({ guids: [guid], to: 'slot', slot: slotId })
    await load()
  } catch (e) {
    error.value = e instanceof Error ? e.message : String(e)
  }
}
const where = (r: PoolRoute) => (r.to === 'slot' ? `slot ${r.slot}` : r.to === 'speaker' ? r.speaker : 'narrator')
onMounted(load)
</script>

<template>
  <div>
    <div class="filters">
      <select v-model="to" data-filter-to @change="refilter">
        <option value="">any destination</option>
        <option value="slot">slot</option>
        <option value="speaker">known speaker</option>
        <option value="narrator">narrator</option>
      </select>
      <select v-model="slot" data-filter-slot @change="refilter">
        <option value="">any slot</option>
        <option v-for="s in props.slots" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
      <label><input v-model="queued" type="checkbox" data-filter-queued @change="refilter" /> needs review only</label>
      <span class="dim">{{ route.total }} lines</span>
    </div>
    <p v-if="error" class="err">{{ error }}</p>
    <EmptyState v-if="!route.rows.length" message="No lines match these filters." />
    <div v-for="r in route.rows" :key="r.guid" class="row">
      <span class="text">{{ r.text }}</span>
      <span class="dim">{{ where(r) }} · {{ r.source }}<template v-if="r.confidence !== null"> · {{ r.confidence.toFixed(2) }}</template></span>
      <select data-move-line :value="''" @change="move(r.guid, ($event.target as HTMLSelectElement).value)">
        <option value="">move to…</option>
        <option v-for="s in props.slots" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>
    <div class="pager">
      <button data-prev :disabled="offset === 0" @click="step(-1)">Previous</button>
      <button data-next :disabled="last" @click="step(1)">Next</button>
    </div>
  </div>
</template>

<style scoped>
.filters { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 6px; }
.row { display: flex; gap: 10px; align-items: center; padding: 3px 0; border-top: 1px solid var(--line); }
.text { flex: 1; }
.pager { display: flex; gap: 8px; margin-top: 6px; }
.dim { color: var(--dim); font-size: 12px; }
.err { color: var(--bad); }
</style>
