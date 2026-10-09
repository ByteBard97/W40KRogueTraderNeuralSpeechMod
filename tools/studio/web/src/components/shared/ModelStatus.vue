<script setup lang="ts">
import { onMounted, onUnmounted } from 'vue'
import { useModelStore } from '../../stores/model'

const model = useModelStore()
onMounted(model.start)
onUnmounted(model.stop)
</script>

<template>
  <span class="status" :title="model.reason || 'model ready'">
    <i class="dot" :class="model.state" /> model {{ model.state }}
  </span>
</template>

<style scoped>
.status { font-size: 12px; color: var(--dim); display: inline-flex; align-items: center; gap: 6px; }
.dot { width: 9px; height: 9px; border-radius: 50%; background: var(--bad); display: inline-block; }
.dot.ready { background: var(--ok); }
.dot.busy { background: #f0b400; }
</style>
