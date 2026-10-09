<script setup lang="ts">
defineProps<{ message: string }>()
</script>

<template><p class="empty">{{ message }}</p></template>

<style scoped>
.empty { color: var(--dim); font-size: 13px; padding: 8px 0; }
</style>
