<script setup lang="ts">
import { ref } from 'vue'
import type { PoolSlot } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'
import SpotCheck from './SpotCheck.vue'

defineProps<{ slots: PoolSlot[] }>()
const emit = defineEmits<{ rename: [id: string, name: string] }>()
const editing = ref<string | null>(null)
const draft = ref('')
const checking = ref<string | null>(null)

function edit(s: PoolSlot) {
  editing.value = s.id
  draft.value = s.name
}
function save(id: string) {
  emit('rename', id, draft.value)
  editing.value = null
}
</script>

<template>
  <EmptyState v-if="!slots.length" message="No slots yet. Build the pools first." />
  <div v-for="s in slots" :key="s.id" class="slot">
    <template v-if="editing === s.id">
      <input v-model="draft" />
      <button data-save-name @click="save(s.id)">Save</button>
    </template>
    <template v-else>
      <RouterLink :to="`/speakers/${s.slug}`">{{ s.name }}</RouterLink>
      <button data-rename title="rename" @click="edit(s)">rename</button>
    </template>
    <span class="dim">{{ s.lines }} lines</span>
    <span class="dim">{{ s.spot.checked }} checked<template v-if="s.spot.wrong">, {{ s.spot.wrong }} wrong</template></span>
    <button data-spot @click="checking = checking === s.id ? null : s.id">{{ checking === s.id ? 'close check' : 'spot check' }}</button>
    <div v-if="checking === s.id" class="check"><SpotCheck :slot-id="s.id" /></div>
  </div>
</template>

<style scoped>
.slot { display: flex; flex-wrap: wrap; gap: 10px; align-items: center; padding: 4px 0; border-top: 1px solid var(--line); }
.check { flex-basis: 100%; padding: 6px 0 4px 12px; }
.dim { color: var(--dim); font-size: 12px; }
</style>
