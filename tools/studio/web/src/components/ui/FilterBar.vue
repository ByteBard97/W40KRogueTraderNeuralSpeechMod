<script setup lang="ts">
/** Container for a page's filter controls: slot SearchField (add class "grow"), SelectField, Seg. */
</script>

<template><div class="filterbar" role="search"><slot /></div></template>

<style scoped>
.filterbar { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2); padding: var(--s-2); border-radius: var(--r-lg); background: var(--surface); border: 1px solid var(--line); }
.filterbar :slotted(.grow) { flex: 1 1 220px; }
</style>
