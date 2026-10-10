<script setup lang="ts">
import { ref, useId } from 'vue'
import Icon from '../ui/Icon.vue'

/** Collapsible card. When closed, `summary` stays visible so the state of the section is readable without opening it. */
const props = defineProps<{ title: string; collapsedByDefault?: boolean; summary?: string; step?: string | number }>()
const open = ref(!props.collapsedByDefault)
const bodyId = useId()
const toggle = () => (open.value = !open.value)
defineExpose({ open, toggle })
</script>

<template>
  <section class="section" :data-open="open">
    <div class="head" @click="toggle">
      <button type="button" class="toggle" :aria-expanded="open" :aria-controls="bodyId">
        <Icon name="chev" :size="14" class="chev" />
        <span class="title"><span v-if="step !== undefined" class="step">{{ step }}</span>{{ title }}</span>
      </button>
      <span v-if="summary" class="summary">{{ summary }}</span>
      <span class="actions" @click.stop><slot name="actions" /></span>
    </div>
    <div v-if="open" :id="bodyId" class="body"><slot /></div>
  </section>
</template>

<style scoped>
.section { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-lg); overflow: hidden; margin-bottom: var(--s-3); }
.head { display: flex; flex-wrap: wrap; align-items: center; gap: var(--s-2) var(--s-3); padding: var(--s-2) var(--s-4); cursor: pointer; min-height: 48px; }
.toggle { display: inline-flex; align-items: center; gap: var(--s-2); background: transparent; border: 0; padding: 0; min-height: var(--hit); color: var(--text); cursor: pointer; }
.chev { transition: transform 0.15s; color: var(--text-3); }
[data-open="true"] .chev { transform: rotate(90deg); }
.title { font-weight: 600; font-size: 15px; display: inline-flex; align-items: center; gap: var(--s-2); }
.step { font-family: var(--font-mono); font-size: var(--fs-xs); color: var(--text-3); }
.summary { color: var(--text-3); font-size: var(--fs-sm); }
.actions { margin-left: auto; display: flex; flex-wrap: wrap; gap: var(--s-2); align-items: center; }
.body { padding: 0 var(--s-4) var(--s-4); }
</style>
