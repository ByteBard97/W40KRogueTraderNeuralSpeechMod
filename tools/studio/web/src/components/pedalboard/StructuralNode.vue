<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed } from 'vue'
import { INPUT_TYPE } from '../../pedalboard/graph'
import ControlRow from './ControlRow.vue'
import type { PedalData } from './PedalNode.vue'

defineOptions({ inheritAttrs: false })
const props = defineProps<{ id: string; data: PedalData; selected?: boolean }>()
const emit = defineEmits<{ param: [label: string, value: number] }>()

const isInput = computed(() => props.data.node.type === INPUT_TYPE)
const rows = computed(() => props.data.block.controls)
const valueOf = (label: string, init: number) => props.data.node.params?.[label] ?? init
</script>

<template>
  <div class="end" :class="{ selected }" :data-testid="`pedal-${id}`">
    <Handle v-if="!isInput" id="in0" type="target" :position="Position.Left" :data-testid="`in-${id}-0`" />
    <header class="head">
      <span class="title">{{ data.block.name }}</span>
      <span v-if="isInput" class="hint">voice clip, both channels</span>
    </header>
    <div v-if="rows.length" class="body">
      <ControlRow v-for="c in rows" :key="c.label" :node-id="id" :control="c" :value="valueOf(c.label, c.init)" @change="(v) => emit('param', c.label, v)" />
    </div>
    <Handle v-if="isInput" id="out0" type="source" :position="Position.Right" :data-testid="`out-${id}`" />
  </div>
</template>

<style scoped>
.end { position: relative; width: 200px; background: var(--surface); border: 1px solid var(--line-strong); border-radius: var(--r-md); color: var(--text); }
.end.selected { border-color: var(--selected-line); }
.head { display: flex; flex-direction: column; gap: 2px; padding: var(--s-2); }
.title { font-family: var(--font-display); letter-spacing: 0.06em; font-weight: 600; }
.hint { font-size: var(--fs-xs); color: var(--text-3); }
.body { display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-2); border-top: 1px solid var(--line); }
:deep(.vue-flow__handle) { width: 9px; height: 9px; background: var(--n-6); border: 1px solid var(--line-strong); }
:deep(.vue-flow__handle:hover), :deep(.vue-flow__handle.connectingto) { background: var(--accent); }
</style>
