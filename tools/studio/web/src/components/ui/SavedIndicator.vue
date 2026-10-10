<script setup lang="ts">
import Icon from './Icon.vue'
/** Quiet "Saved" line. `ago` is a short phrase such as "2 s ago". */
defineProps<{ ago?: string }>()
</script>

<template><span class="saved" role="status"><Icon name="check" :size="14" />Saved<template v-if="ago"> · {{ ago }}</template></span></template>
