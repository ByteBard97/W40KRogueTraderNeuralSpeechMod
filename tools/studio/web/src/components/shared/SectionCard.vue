<script setup lang="ts">
import { ref } from 'vue'

const props = defineProps<{ title: string; collapsedByDefault?: boolean }>()
const open = ref(!props.collapsedByDefault)
</script>

<template>
  <section class="card">
    <div class="head" @click="open = !open">
      <h2>{{ open ? '▾' : '▸' }} {{ title }}</h2>
      <span class="actions" @click.stop><slot name="actions" /></span>
    </div>
    <div v-if="open" class="content"><slot /></div>
  </section>
</template>

<style scoped>
.card { background: var(--card); border: 1px solid var(--line); border-radius: 10px; padding: 10px 12px; margin-bottom: 12px; }
.head { display: flex; justify-content: space-between; align-items: center; cursor: pointer; }
h2 { font-size: 14px; margin: 0; }
.content { margin-top: 8px; }
</style>
