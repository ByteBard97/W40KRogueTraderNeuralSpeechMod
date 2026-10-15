<script setup lang="ts">
import { Handle, Position } from '@vue-flow/core'
import { computed, ref } from 'vue'
import type { CatalogBlock, GraphNode } from '../../pedalboard/types'
import ControlRow from './ControlRow.vue'

// `muted` and `solo` are audition state from the store (Bypass all, Solo); they are not part of the saved node.
export interface PedalData { node: GraphNode; block: CatalogBlock; muted?: boolean; solo?: boolean }

defineOptions({ inheritAttrs: false })
const props = defineProps<{ id: string; data: PedalData; selected?: boolean }>()
const emit = defineEmits<{ param: [label: string, value: number]; stomp: [on: boolean]; solo: [] }>()

const PORT_LABELS = ['A', 'B', 'C', 'D']
const PERCENT = 100

const collapsed = ref(false)
const on = computed(() => props.data.node.on !== false)
const stompable = computed(() => props.data.block.stomp !== null)
const rows = computed(() => props.data.block.controls.filter((c) => c.label !== props.data.block.stomp))
const valueOf = (label: string, init: number) => props.data.node.params?.[label] ?? init
const inputs = computed(() => Array.from({ length: props.data.block.inputs }, (_, i) => i))
// Spread several inputs down the left edge; a single input sits in the middle.
const handleTop = (i: number) => `${((i + 1) / (inputs.value.length + 1)) * PERCENT}%`
</script>

<template>
  <div class="pedal" :class="{ selected, bypassed: stompable && !on, muted: data.muted, soloed: data.solo }" :data-testid="`pedal-${id}`">
    <Handle
      v-for="i in inputs"
      :id="`in${i}`"
      :key="i"
      type="target"
      :position="Position.Left"
      :style="{ top: handleTop(i) }"
      :data-testid="`in-${id}-${i}`"
    />
    <span v-for="i in inputs.length > 1 ? inputs : []" :key="`l${i}`" class="port-label" :style="{ top: handleTop(i) }">{{ PORT_LABELS[i] }}</span>
    <header class="head">
      <span class="led" :class="{ lit: on }" aria-hidden="true" />
      <span class="title" :title="data.block.description">{{ data.block.name }}</span>
      <button
        v-if="stompable"
        type="button"
        class="stomp nodrag"
        role="switch"
        :aria-checked="on"
        :aria-label="`${data.block.name} ${on ? 'in chain' : 'bypassed'}`"
        :data-testid="`stomp-${id}`"
        @click="emit('stomp', !on)"
      >{{ on ? 'In chain' : 'Bypassed' }}</button>
      <button
        v-if="stompable"
        type="button"
        class="solo nodrag"
        :aria-pressed="!!data.solo"
        :title="data.solo ? 'Soloed: every other pedal is bypassed. Click to release.' : 'Solo: bypass every other pedal while you listen'"
        :data-testid="`solo-${id}`"
        @click="emit('solo')"
      >Solo</button>
      <button
        type="button"
        class="fold nodrag"
        :aria-expanded="!collapsed"
        :aria-label="collapsed ? 'Show controls' : 'Hide controls'"
        :data-testid="`collapse-${id}`"
        @click="collapsed = !collapsed"
      >{{ collapsed ? '+' : '-' }}</button>
    </header>
    <div v-if="!collapsed && rows.length" class="body">
      <ControlRow
        v-for="c in rows"
        :key="c.label"
        :node-id="id"
        :control="c"
        :value="valueOf(c.label, c.init)"
        @change="(v) => emit('param', c.label, v)"
      />
    </div>
    <Handle id="out0" type="source" :position="Position.Right" :data-testid="`out-${id}`" />
  </div>
</template>

<style scoped>
.pedal { position: relative; width: 220px; background: var(--raised); border: 1px solid var(--line); border-radius: var(--r-md); color: var(--text); font-size: var(--fs-md); }
.pedal.selected { border-color: var(--selected-line); }
.pedal.bypassed .body { opacity: 0.55; }
.pedal.muted { border-style: dashed; }
.pedal.muted .head, .pedal.muted .body { opacity: 0.5; }
.pedal.soloed { border-color: var(--accent); }
.solo { background: transparent; color: var(--text-3); border: 1px solid var(--line); border-radius: var(--r-pill); font-size: var(--fs-xs); padding: 2px var(--s-2); cursor: pointer; }
.solo:hover { color: var(--text); border-color: var(--line-strong); }
.solo[aria-pressed="true"] { color: var(--accent-ink); background: var(--accent); border-color: var(--accent); font-weight: 600; }
.head { display: flex; align-items: center; gap: var(--s-2); padding: var(--s-2); border-bottom: 1px solid var(--line); }
.led { width: 8px; height: 8px; border-radius: var(--r-pill); background: var(--n-5); flex: none; }
.led.lit { background: var(--accent); }
.title { flex: 1; min-width: 0; font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.stomp { background: var(--inset); color: var(--text-3); border: 1px solid var(--line-strong); border-radius: var(--r-pill); font-size: var(--fs-xs); padding: 2px var(--s-2); cursor: pointer; }
.stomp[aria-checked="true"] { color: var(--accent-hi); border-color: var(--selected-line); background: var(--accent-tint); }
.fold { background: transparent; border: 0; color: var(--text-3); cursor: pointer; width: 20px; font-family: var(--font-mono); }
.fold:hover { color: var(--text); }
.body { display: flex; flex-direction: column; gap: var(--s-2); padding: var(--s-2); }
.port-label { position: absolute; left: 8px; transform: translateY(-50%); font-size: var(--fs-xs); color: var(--text-3); pointer-events: none; }
:deep(.vue-flow__handle) { width: 9px; height: 9px; background: var(--n-6); border: 1px solid var(--line-strong); }
:deep(.vue-flow__handle:hover), :deep(.vue-flow__handle.connectingto) { background: var(--accent); }
</style>
