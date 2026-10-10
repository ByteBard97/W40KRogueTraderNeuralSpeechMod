<script setup lang="ts">
import Icon from './Icon.vue'
/** Auto flag from the pipeline: mono, outlined, with an icon so colour is never the only signal. */
export type FlagTone = 'warn' | 'bad' | 'info'
withDefaults(defineProps<{ tone?: FlagTone; icon?: boolean }>(), { tone: 'warn', icon: true })
</script>

<template>
  <span class="flag" :class="`f-${tone}`"><Icon v-if="icon" :name="tone === 'bad' ? 'x' : 'warn'" :size="11" /><slot /></span>
</template>

<style scoped>
.flag { display: inline-flex; align-items: center; gap: 5px; height: 22px; padding: 0 8px; border-radius: var(--r-sm); border: 1px solid var(--warn-line); color: var(--warn); font-size: var(--fs-xs); font-family: var(--font-mono); white-space: nowrap; }
.f-bad { border-color: var(--bad-line); color: var(--bad); }
.f-info { border-color: var(--info-line); color: var(--info); }
.flag :deep(svg) { flex: none; }
</style>
