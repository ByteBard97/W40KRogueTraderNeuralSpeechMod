<script setup lang="ts">
/** Status marker. Each state has its own shape or fill, so it reads without colour. `label` is the accessible name. */
export type DotStatus = 'idle' | 'progress' | 'picked' | 'done' | 'good' | 'bad' | 'flag'
withDefaults(defineProps<{ status?: DotStatus; label?: string }>(), { status: 'idle' })
</script>

<template><span class="dot" :class="`d-${status}`" role="img" :aria-label="label ?? status" :title="label" /></template>

<style scoped>
.dot { width: 12px; height: 12px; flex: none; border-radius: 50%; border: 2px solid var(--text-3); background: transparent; display: inline-block; }
.d-progress { border-color: var(--accent); background: linear-gradient(90deg, var(--accent) 50%, transparent 50%); }
.d-picked { border-color: var(--accent); background: var(--accent); }
.d-done { border-color: var(--good); background: var(--good); box-shadow: inset 0 0 0 2px var(--bg); }
.d-good { border-color: var(--good); background: var(--good); }
.d-bad { border-color: var(--bad); background: var(--bad); border-radius: 2px; }
.d-flag { border-color: var(--warn); border-radius: 2px; transform: rotate(45deg); width: 10px; height: 10px; }
</style>
