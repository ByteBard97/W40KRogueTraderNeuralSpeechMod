<script setup lang="ts">
/** One list/table-like row: `lead` (play button, dot), default slot (text/name), `meta` (tags, numbers), `end` (actions). */
defineProps<{ selected?: boolean; as?: 'div' | 'a' | 'li'; href?: string }>()
</script>

<template>
  <component :is="as ?? 'div'" class="row" :class="{ sel: selected }" :href="as === 'a' ? href : undefined" :aria-current="selected ? 'true' : undefined">
    <slot name="lead" />
    <span class="main"><slot /></span>
    <slot name="meta" />
    <span v-if="$slots.end" class="end"><slot name="end" /></span>
  </component>
</template>

<style scoped>
.row { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); min-height: 44px; padding: 6px var(--s-3); border-top: 1px solid var(--line); text-decoration: none; color: inherit; }
.row:first-child { border-top: 0; }
.row:hover { background: var(--hover); }
.sel { background: var(--selected); box-shadow: inset 0 0 0 1px var(--selected-line); border-top-color: transparent; border-radius: var(--r-md); }
.main { flex: 1 1 200px; min-width: 0; }
.end { margin-left: auto; display: flex; align-items: center; gap: var(--s-3); }
</style>
