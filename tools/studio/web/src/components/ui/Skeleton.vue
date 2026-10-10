<script setup lang="ts">
/** Loading rows. Widths cycle so the block does not look like a barcode. */
const WIDTHS = [90, 70, 80, 60]
withDefaults(defineProps<{ rows?: number }>(), { rows: 3 })
</script>

<template>
  <div class="skeletons" aria-busy="true" aria-label="Loading">
    <div v-for="n in rows" :key="n" class="skeleton" :style="{ width: `${WIDTHS[(n - 1) % WIDTHS.length]}%` }" />
  </div>
</template>

<style scoped>
.skeletons { display: flex; flex-direction: column; gap: var(--s-3); }
.skeleton { background: linear-gradient(90deg, var(--n-2), var(--n-3), var(--n-2)); background-size: 200% 100%; animation: shimmer 1.4s linear infinite; border-radius: var(--r-sm); height: 12px; }
@keyframes shimmer { to { background-position: -200% 0; } }
</style>
