<script setup lang="ts">
export type TagVariant = 'plain' | 'real' | 'designed' | 'slot' | 'bank' | 'nobank'
withDefaults(defineProps<{ variant?: TagVariant }>(), { variant: 'plain' })
</script>

<template><span class="tag" :class="`t-${variant}`"><slot /></span></template>

<style scoped>
.tag { display: inline-flex; align-items: center; gap: 4px; height: 20px; padding: 0 7px; border-radius: var(--r-sm); background: var(--inset); color: var(--text-2); font-size: var(--fs-xs); font-weight: 500; letter-spacing: 0.02em; white-space: nowrap; }
.t-real { color: var(--info); background: var(--info-tint); }
.t-designed { color: var(--accent-hi); background: var(--accent-tint); }
.t-bank { color: var(--good); background: var(--good-tint); }
.t-nobank { color: var(--text-3); }
</style>
