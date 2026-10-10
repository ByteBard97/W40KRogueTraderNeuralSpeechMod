<script setup lang="ts">
/** Mono score chip. `none` is the dashed "unscored" look. */
export type ScoreTone = 'neutral' | 'ok' | 'hot' | 'none'
withDefaults(defineProps<{ tone?: ScoreTone }>(), { tone: 'neutral' })
</script>

<template><span class="score" :class="`s-${tone}`"><slot /></span></template>

<style scoped>
.score { display: inline-flex; align-items: center; height: 20px; padding: 0 6px; border-radius: var(--r-sm); font: 500 var(--fs-xs)/1 var(--font-mono); background: var(--inset); color: var(--text-2); white-space: nowrap; }
.s-ok { color: var(--good); background: var(--good-tint); }
.s-hot { color: var(--bad); background: var(--bad-tint); }
.s-none { color: var(--text-3); background: transparent; border: 1px dashed var(--line-strong); }
</style>
