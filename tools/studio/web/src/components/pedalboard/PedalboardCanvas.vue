<script setup lang="ts">
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Connection, GraphEdge as FlowEdge, GraphNode as FlowNode, Node } from '@vue-flow/core'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { INPUT_TYPE, OUTPUT_TYPE } from '../../pedalboard/graph'
import { usePedalboardStore } from '../../stores/pedalboard'
import { handleShortcut, isTextEntry } from '../../pedalboard/shortcuts'
import { PALETTE_MIME } from './paletteDrag'
import PedalNode, { type PedalData } from './PedalNode.vue'
import StructuralNode from './StructuralNode.vue'
import '@vue-flow/core/dist/style.css'
import '@vue-flow/controls/dist/style.css'

const FLOW_ID = 'pedalboard'
const REFUSAL_MS = 3500
const MIN_ZOOM = 0.3
const MAX_ZOOM = 1.5
const GRID_GAP = 24
const FIT_PADDING = 0.15
// Vue Flow measures a new node's size a moment after it is added; fitting before that frames empty boxes, so the fit waits for the measurements.
const FIT_DELAY_MS = 350
// New pedals land centred on the drop point, not hanging from its top-left corner.
const DROP_OFFSET_X = 110
const DROP_OFFSET_Y = 30
const PORT_PREFIX = /^(in|out)/
// Shift-click adds to the selection; Ctrl and Cmd work too. Shift-drag on empty canvas draws a selection box.
const MULTI_SELECT_KEYS = ['Shift', 'Control', 'Meta']

const store = usePedalboardStore()
const { screenToFlowCoordinate, fitView, setEdges, getSelectedNodes, getSelectedEdges } = useVueFlow(FLOW_ID)

const root = ref<HTMLElement | null>(null)
const refusal = ref('')
const pendingRefusal = ref('')
const selectedEdges = ref<string[]>([])
let refusalTimer: ReturnType<typeof setTimeout> | undefined
let fitTimer: ReturnType<typeof setTimeout> | undefined

const isEnd = (type: string) => type === INPUT_TYPE || type === OUTPUT_TYPE
const portOf = (handle: string | null | undefined) => Number((handle ?? '').replace(PORT_PREFIX, '')) || 0

// Bypass all or Solo is in force: pedals that are silenced by it (not by their own stomp) are drawn muted.
const audition = computed(() => store.bypassAll || store.soloId !== null)
const isEmpty = computed(() => store.graph.nodes.every((n) => isEnd(n.type)))

const flowNodes = computed<Node<PedalData>[]>(() =>
  store.graph.nodes.flatMap((node) => {
    const block = store.catalog.blocks.find((b) => b.id === node.type)
    if (!block) return []
    return [{
      id: node.id,
      type: isEnd(node.type) ? 'structural' : 'pedal',
      position: { x: node.x, y: node.y },
      data: { node, block, muted: audition.value && block.stomp !== null && !store.viewOn(node.id), solo: store.soloId === node.id },
      selected: store.selection.includes(node.id),
      deletable: !isEnd(node.type),
    }]
  }),
)
const flowEdges = computed(() =>
  store.graph.edges.map((e) => ({
    id: e.id,
    source: e.source,
    target: e.target,
    sourceHandle: `out${e.sourcePort ?? 0}`,
    targetHandle: `in${e.targetPort}`,
    selected: selectedEdges.value.includes(e.id),
  })),
)

function showRefusal(reason: string) {
  refusal.value = reason
  clearTimeout(refusalTimer)
  refusalTimer = setTimeout(() => (refusal.value = ''), REFUSAL_MS)
}

const asRequest = (c: Connection) => ({ source: c.source, target: c.target, sourcePort: portOf(c.sourceHandle), targetPort: portOf(c.targetHandle) })

const alreadyWired = (c: Connection) => {
  const r = asRequest(c)
  return store.graph.edges.some((e) => e.source === r.source && e.target === r.target && e.targetPort === r.targetPort && (e.sourcePort ?? 0) === r.sourcePort)
}

// Called while a cable is being dragged, so it must not change anything; the reason is kept for connect-end.
// Vue Flow also runs it on every edge it is given, and a wire that is already in the graph would be refused as "that input already has a wire",
// so wires the store already holds always pass (otherwise no existing wire is ever drawn).
function isValidConnection(c: Connection): boolean {
  if (alreadyWired(c)) return true
  const reason = store.wireRefusal(asRequest(c))
  pendingRefusal.value = reason ?? ''
  return reason === null
}
function onConnect(c: Connection) {
  const reason = store.connect(asRequest(c))
  pendingRefusal.value = ''
  if (reason) showRefusal(reason)
}
function onConnectEnd() {
  if (pendingRefusal.value) showRefusal(pendingRefusal.value)
  pendingRefusal.value = ''
}
// A group drag reports every moved node in `nodes`; saving only `node` would leave the others at their old spot in the store.
function onDragStop(e: { node: FlowNode; nodes?: FlowNode[] }) {
  const moved = e.nodes?.length ? e.nodes : [e.node]
  store.moveNodes(moved.map((n) => ({ id: n.id, x: Math.round(n.position.x), y: Math.round(n.position.y) })))
}
function onSelection(e: { nodes: FlowNode[]; edges: FlowEdge[] }) {
  store.select(e.nodes.map((n) => n.id))
  // Assigning a new array, even with the same ids, would recompute the wires, re-apply them to Vue Flow, reset its selection and fire this again
  // without end (the stack overflowed in the browser); so only a real change is stored.
  const ids = e.edges.map((x) => x.id)
  const same = ids.length === selectedEdges.value.length && ids.every((id) => selectedEdges.value.includes(id))
  if (!same) selectedEdges.value = ids
}
// Vue Flow 1.48 has no selection-change event (a template listener for it silently never fires); the selected nodes and edges are reactive lists, so
// the store follows those. Without this a click selected the node on screen but copy, duplicate and delete had nothing to act on.
watch([getSelectedNodes, getSelectedEdges], ([nodes, edges]) => onSelection({ nodes, edges }))

function addAt(type: string, x: number, y: number) {
  const id = store.addNode(type, Math.round(x), Math.round(y))
  if (id) store.select([id])
}
function addAtCenter(type: string) {
  const r = root.value?.getBoundingClientRect()
  const p = r ? screenToFlowCoordinate({ x: r.left + r.width / 2, y: r.top + r.height / 2 }) : { x: 0, y: 0 }
  addAt(type, p.x - DROP_OFFSET_X, p.y - DROP_OFFSET_Y)
}
function onDrop(e: DragEvent) {
  const type = e.dataTransfer?.getData(PALETTE_MIME)
  if (!type) return
  const p = screenToFlowCoordinate({ x: e.clientX, y: e.clientY })
  addAt(type, p.x - DROP_OFFSET_X, p.y - DROP_OFFSET_Y)
}
function onDragOver(e: DragEvent) {
  if (e.dataTransfer) e.dataTransfer.dropEffect = 'copy'
}

// Delete is handled here rather than by Vue Flow so Input and Output stay put and the store sees every removal.
function onKey(e: KeyboardEvent) {
  if (handleShortcut(e, store)) return
  if ((e.key !== 'Delete' && e.key !== 'Backspace') || isTextEntry(e.target)) return
  if (!store.removeMany(store.selection, selectedEdges.value)) return
  e.preventDefault()
  selectedEdges.value = []
  store.select([])
}

// Vue Flow silently drops an edge whose nodes are not in its state yet, and a loaded graph changes nodes and edges in the same tick, so the edges
// are not passed as the :edges prop: they are applied after the nodes, once the DOM has updated.
watch(flowEdges, (e) => setEdges(e), { flush: 'post' })
function fitSoon() {
  clearTimeout(fitTimer)
  fitTimer = setTimeout(() => void fitView({ padding: FIT_PADDING }), FIT_DELAY_MS)
}
watch(() => [store.loadRev, store.fitRev], fitSoon)

onMounted(() => {
  window.addEventListener('keydown', onKey)
  void nextTick(() => setEdges(flowEdges.value))
  fitSoon()
})
onBeforeUnmount(() => {
  window.removeEventListener('keydown', onKey)
  clearTimeout(refusalTimer)
  clearTimeout(fitTimer)
})

defineExpose({ addAtCenter })
</script>

<template>
  <div ref="root" class="canvas" data-testid="canvas" @dragover.prevent="onDragOver" @drop.prevent="onDrop">
    <VueFlow
      :id="FLOW_ID"
      :nodes="flowNodes"
      :min-zoom="MIN_ZOOM"
      :max-zoom="MAX_ZOOM"
      :delete-key-code="null"
      selection-key-code="Shift"
      :multi-selection-key-code="MULTI_SELECT_KEYS"
      :is-valid-connection="isValidConnection"
      :default-edge-options="{ style: { stroke: 'var(--accent)', strokeWidth: 2 } }"
      @connect="onConnect"
      @connect-end="onConnectEnd"
      @node-drag-stop="onDragStop"
    >
      <template #node-pedal="p">
        <PedalNode v-bind="p" @param="(label, v) => store.setParam(p.id, label, v)" @stomp="(on) => store.setOn(p.id, on)" @solo="store.toggleSolo(p.id)" />
      </template>
      <template #node-structural="p">
        <StructuralNode v-bind="p" @param="(label, v) => store.setParam(p.id, label, v)" />
      </template>
      <Background :gap="GRID_GAP" pattern-color="var(--line)" />
      <Controls :show-interactive="false" />
    </VueFlow>
    <div class="tools" role="toolbar" aria-label="Board tools">
      <button type="button" class="tool" data-testid="tidy-btn" title="Arrange the pedals by signal order" @click="store.tidy()">Tidy</button>
      <button type="button" class="tool" data-testid="bypass-all" :aria-pressed="store.bypassAll" title="Hear the dry signal without changing any pedal's saved state" @click="store.setBypassAll(!store.bypassAll)">Bypass all</button>
      <span v-if="audition" class="audition" data-testid="audition-note" role="status">{{ store.bypassAll ? 'Every pedal bypassed (not saved)' : 'Solo: other pedals bypassed (not saved)' }}</span>
    </div>
    <p v-if="isEmpty" class="empty" data-testid="empty-hint">Drag a pedal from the left, or load a starting point.</p>
    <p v-if="refusal" class="refusal" role="status" data-testid="refusal">{{ refusal }}</p>
  </div>
</template>

<style scoped>
.canvas { position: relative; min-height: 420px; height: 100%; background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-md); overflow: hidden; }
.tools { position: absolute; top: var(--s-2); left: var(--s-2); z-index: 5; display: flex; align-items: center; gap: var(--s-2); }
.tool { min-height: var(--hit); padding: 0 var(--s-3); background: var(--raised); color: var(--text); border: 1px solid var(--line-strong); border-radius: var(--r-md); font-size: var(--fs-md); cursor: pointer; }
.tool:hover { background: var(--inset); }
.tool[aria-pressed="true"] { background: var(--accent); border-color: var(--accent); color: var(--accent-ink); font-weight: 600; }
.audition { color: var(--warn); font-size: var(--fs-sm); }
.empty { position: absolute; left: 50%; top: 62%; transform: translateX(-50%); margin: 0; color: var(--text-3); font-size: var(--fs-md); pointer-events: none; }
.refusal { position: absolute; left: 50%; bottom: var(--s-4); transform: translateX(-50%); margin: 0; padding: var(--s-2) var(--s-3); background: var(--raised); border: 1px solid var(--warn-line); border-radius: var(--r-md); color: var(--text); font-size: var(--fs-sm); }
:deep(.vue-flow) { background: var(--bg); }
:deep(.vue-flow__edge-path) { stroke: var(--accent); stroke-width: 2; }
:deep(.vue-flow__edge.selected .vue-flow__edge-path) { stroke: var(--accent-hi); stroke-width: 3; }
:deep(.vue-flow__connection-path) { stroke: var(--accent-lo); stroke-width: 2; }
:deep(.vue-flow__node) { cursor: default; }
:deep(.vue-flow__controls) { box-shadow: none; border: 1px solid var(--line-strong); border-radius: var(--r-sm); overflow: hidden; }
:deep(.vue-flow__controls-button) { background: var(--raised); border-bottom: 1px solid var(--line); fill: var(--text-2); }
:deep(.vue-flow__controls-button:hover) { background: var(--inset); }
</style>
