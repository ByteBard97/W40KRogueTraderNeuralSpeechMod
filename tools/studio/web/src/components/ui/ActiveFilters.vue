<script setup lang="ts">
import Btn from './Btn.vue'

export interface ActiveFilter { key: string; label: string }
/** "Showing N of M" plus a removable chip per active filter and Clear all. Renders nothing when no filter is active. */
defineProps<{ filters: ActiveFilter[]; shown?: number; total?: number }>()
const emit = defineEmits<{ remove: [key: string]; clear: [] }>()
const fmt = (n: number) => n.toLocaleString('en-US')
</script>

<template>
  <div v-if="filters.length" class="active-filters" aria-label="Active filters">
    <span v-if="shown !== undefined && total !== undefined">Showing <span class="num">{{ fmt(shown) }}</span> of <span class="num">{{ fmt(total) }}</span> ·</span>
    <button v-for="f in filters" :key="f.key" type="button" class="chip" :aria-label="`Remove filter ${f.label}`" @click="emit('remove', f.key)">{{ f.label }} <span aria-hidden="true">×</span></button>
    <Btn variant="ghost" size="sm" @click="emit('clear')">Clear all</Btn>
  </div>
</template>

<style scoped>
.active-filters { display: flex; flex-wrap: wrap; gap: 6px; align-items: center; font-size: var(--fs-sm); color: var(--text-3); }
.chip { display: inline-flex; align-items: center; gap: 6px; min-height: 24px; padding: 0 10px; border-radius: var(--r-pill); border: 1px solid var(--selected-line); background: var(--accent-tint); color: var(--accent-hi); font-size: var(--fs-sm); cursor: pointer; white-space: nowrap; }
.chip:hover { border-color: var(--accent); }
</style>
