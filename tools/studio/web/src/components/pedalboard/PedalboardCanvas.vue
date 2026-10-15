<script setup lang="ts">
import { Background } from '@vue-flow/background'
import { Controls } from '@vue-flow/controls'
import { VueFlow, useVueFlow } from '@vue-flow/core'
import type { Connection, GraphEdge as FlowEdge, GraphNode as FlowNode, Node } from '@vue-flow/core'
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { INPUT_TYPE, OUTPUT_TYPE } from '../../pedalboard/graph'
import { usePedalboardStore } from '../../stores/pedalboard'
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

const store = usePedalboardStore()
const { screenToFlowCoordinate, fitView, setEdges } = useVueFlow(FLOW_ID)

const root = ref<HTMLElement | null>(null)
const refusal = ref('')
const pendingRefusal = ref('')
const selectedEdges = ref<string[]>([])
let refusalTimer: ReturnType<typeof setTimeout> | undefined
let fitTimer: ReturnType<typeof setTimeout> | undefined

const isEnd = (type: string) => type === INPUT_TYPE || type === OUTPUT_TYPE
const portOf = (handle: string | null | undefined) => Number((handle ?? '').replace(PORT_PREFIX, '')) || 0

const flowNodes = computed<Node<PedalData>[]>(() =>
  store.graph.nodes.flatMap((node) => {
    const block = store.catalog.blocks.find((b) => b.id === node.type)
    if (!block) return []
    return [{
      id: node.id,
      type: isEnd(node.type) ? 'structural' : 'pedal',
      position: { x: node.x, y: node.y },
      data: { node, block },
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
function onDragStop(e: { node: FlowNode }) {
  store.moveNode(e.node.id, Math.round(e.node.position.x), Math.round(e.node.position.y))
}
function onSelection(e: { nodes: FlowNode[]; edges: FlowEdge[] }) {
  store.select(e.nodes.map((n) => n.id))
  selectedEdges.value = e.edges.map((x) => x.id)
}

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

const typing = (t: EventTarget | null) => t instanceof HTMLElement && (t.isContentEditable || /^(INPUT|TEXTAREA|SELECT)$/.test(t.tagName))

// Delete is handled here rather than by Vue Flow so Input and Output stay put and the store sees every removal.
function onKey(e: KeyboardEvent) {
  if ((e.key !== 'Delete' && e.key !== 'Backspace') || typing(e.target)) return
  const nodes = store.selection.filter((id) => !isEnd(store.nodeOf(id)?.type ?? ''))
  if (!nodes.length && !selectedEdges.value.length) return
  e.preventDefault()
  selectedEdges.value.forEach((id) => store.disconnect(id))
  nodes.forEach((id) => store.removeNode(id))
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
watch(() => store.loadRev, fitSoon)

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
      :is-valid-connection="isValidConnection"
      :default-edge-options="{ style: { stroke: 'var(--accent)', strokeWidth: 2 } }"
      @connect="onConnect"
      @connect-end="onConnectEnd"
      @node-drag-stop="onDragStop"
      @selection-change="onSelection"
    >
      <template #node-pedal="p">
        <PedalNode v-bind="p" @param="(label, v) => store.setParam(p.id, label, v)" @stomp="(on) => store.setOn(p.id, on)" />
      </template>
      <template #node-structural="p">
        <StructuralNode v-bind="p" @param="(label, v) => store.setParam(p.id, label, v)" />
      </template>
      <Background :gap="GRID_GAP" pattern-color="var(--line)" />
      <Controls :show-interactive="false" />
    </VueFlow>
    <p v-if="refusal" class="refusal" role="status" data-testid="refusal">{{ refusal }}</p>
  </div>
</template>

<style scoped>
.canvas { position: relative; min-height: 420px; height: 100%; background: var(--bg); border: 1px solid var(--line); border-radius: var(--r-md); overflow: hidden; }
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
