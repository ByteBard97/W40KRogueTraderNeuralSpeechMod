<script setup lang="ts">
/** Global empty / loading / error block. `message` alone keeps the old one-line look working. */
withDefaults(defineProps<{ message?: string; title?: string; state?: 'empty' | 'loading' | 'error' }>(), { state: 'empty' })
</script>

<template>
  <div class="empty" :class="`is-${state}`" :role="state === 'error' ? 'alert' : 'status'" :aria-busy="state === 'loading' ? 'true' : undefined">
    <span v-if="state === 'loading'" class="spinner" />
    <span v-if="title" class="t">{{ title }}</span>
    <span v-if="message">{{ message }}</span>
    <slot />
  </div>
</template>

<style scoped>
.empty { display: flex; flex-direction: column; align-items: center; justify-content: center; text-align: center; gap: var(--s-2); padding: var(--s-5) var(--s-4); color: var(--text-3); border: 1px dashed var(--line-strong); border-radius: var(--r-lg); font-size: 13px; }
.t { color: var(--text); font-weight: 600; font-size: 15px; }
.is-error { border-style: solid; border-color: var(--bad-line); background: var(--bad-tint); color: var(--text-2); }
</style>
