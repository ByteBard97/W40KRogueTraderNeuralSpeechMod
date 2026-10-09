<script setup lang="ts">
import type { FxPresetInfo } from '../../api/types'
import EmptyState from '../shared/EmptyState.vue'

defineProps<{ presets: FxPresetInfo[] }>()
</script>

<template>
  <EmptyState v-if="!presets.length" message="No presets found." />
  <div v-for="p in presets" :key="p.name" class="row">
    <b>{{ p.name }}</b>
    <span class="chip">{{ p.source }}</span>
    <span class="dim">{{ p.notes }}</span>
  </div>
</template>

<style scoped>
.row { display: flex; gap: 10px; align-items: center; padding: 3px 0; border-top: 1px solid var(--line); }
.chip { border: 1px solid var(--line); border-radius: 10px; padding: 0 7px; font-size: 11px; color: var(--dim); }
.dim { color: var(--dim); font-size: 12px; }
</style>
