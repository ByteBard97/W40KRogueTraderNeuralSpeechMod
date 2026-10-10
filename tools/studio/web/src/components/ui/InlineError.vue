<script setup lang="ts">
import Icon from './Icon.vue'
/** Error shown at the control that failed. Slot is the detail (path, hint); `title` is the bold first line. */
defineProps<{ title: string }>()
</script>

<template>
  <div class="inline-error" role="alert">
    <Icon class="ico" name="warn" />
    <div><b>{{ title }}</b><slot /></div>
  </div>
</template>

<style scoped>
.inline-error { display: flex; align-items: flex-start; gap: var(--s-2); padding: 10px 12px; border-radius: var(--r-md); background: var(--bad-tint); border: 1px solid var(--bad-line); color: var(--text); font-size: 13px; }
.ico { color: var(--bad); flex: none; margin-top: 2px; }
</style>
