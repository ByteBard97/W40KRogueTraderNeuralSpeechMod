import { defineStore } from 'pinia'
import { computed, ref, toRaw } from 'vue'
import { api } from '../api/client'
import type { PedalboardStarter, PedalboardSaved } from '../api/types'
import { blockFor, canConnect, controlKey, INPUT_TYPE, OUTPUT_TYPE, paramsFor, validate } from '../pedalboard/graph'
import { generate } from '../pedalboard/generate'
import { copyNodes, PASTE_OFFSET, type Clip } from '../pedalboard/clipboard'
import { History } from '../pedalboard/history'
import { tidyPositions } from '../pedalboard/tidy'
import { describeIssue } from '../pedalboard/issueText'
import type { Catalog, CatalogBlock, Control, Graph, GraphEdge, GraphIssue, GraphNode } from '../pedalboard/types'

const GRAPH_VERSION = 1
const INPUT_ID = 'input'
const OUTPUT_ID = 'output'
const INPUT_X = 0
const OUTPUT_X = 640
const DEFAULT_Y = 0
const FIRST_PORT = 0

interface Snapshot { nodes: GraphNode[]; edges: GraphEdge[] }

const msg = (e: unknown) => (e instanceof Error ? e.message : String(e))
const clone = <T>(v: T): T => JSON.parse(JSON.stringify(toRaw(v))) as T

export interface Compiled { code: string; controls: Control[]; params: Record<string, number> }
export interface LiveChange { key: string; value: number }
export interface WireRequest { source: string; target: string; targetPort: number; sourcePort?: number }

export function emptyGraph(name = ''): Graph {
  return {
    version: GRAPH_VERSION,
    name,
    nodes: [
      { id: INPUT_ID, type: INPUT_TYPE, x: INPUT_X, y: DEFAULT_Y },
      { id: OUTPUT_ID, type: OUTPUT_TYPE, x: OUTPUT_X, y: DEFAULT_Y, params: {} },
    ],
    edges: [],
  }
}

/**
 * The graph being edited, the block catalog, and what to send to the audio engine.
 * Changes come in two kinds. Structural ones (nodes, wires, loading) bump `structuralRev` and the view recompiles.
 * Live ones (knobs, stomps) are announced through `onLive` and sent to the engine by key without recompiling.
 */
export const usePedalboardStore = defineStore('pedalboard', () => {
  const catalog = ref<Catalog>({ version: 1, blocks: [] })
  const libText = ref('')
  const graph = ref<Graph>(emptyGraph())
  const selection = ref<string[]>([])
  const dirty = ref(false)
  const starters = ref<PedalboardStarter[]>([])
  const savedNames = ref<string[]>([])
  const error = ref<string | null>(null)
  const loading = ref(false)
  const saving = ref(false)
  const structuralRev = ref(0)
  // Bumped when a whole graph replaces the board (new, load, starter), so the canvas can re-fit its view.
  const loadRev = ref(0)
  // Bumped by Tidy: the same re-fit as a load, without pretending a new graph arrived.
  const fitRev = ref(0)
  let edgeCounter = 0
  const history = new History<string>()
  const undoCount = ref(0)
  const redoCount = ref(0)
  const clip = ref<Clip | null>(null)
  let pasteCount = 0
  // View state for auditioning: never saved, never part of the graph or its undo history.
  const bypassAll = ref(false)
  const soloId = ref<string | null>(null)
  const liveListeners = new Set<(c: LiveChange) => void>()

  const issues = computed<GraphIssue[]>(() => validate(graph.value, catalog.value))
  const issueTexts = computed(() => issues.value.map((i) => describeIssue(i, graph.value, catalog.value)))
  const valid = computed(() => issues.value.length === 0)

  // Only the wiring decides the generated program, so knob moves and node drags must not regenerate it.
  const structureKey = computed(() => {
    const nodes = graph.value.nodes.map((n) => `${n.id}:${n.type}`).join(',')
    const edges = graph.value.edges.map((e) => `${e.id}:${e.source}.${e.sourcePort ?? FIRST_PORT}>${e.target}.${e.targetPort}`).join(',')
    return `${nodes}|${edges}|${libText.value.length}|${catalog.value.blocks.length}`
  })
  const generated = computed(() => {
    void structureKey.value
    if (issues.value.length) return null
    try {
      return generate(toRaw(graph.value), toRaw(catalog.value), libText.value)
    } catch {
      return null
    }
  })
  /** Whether a pedal sounds right now: its saved stomp, unless Bypass all or Solo is overriding it. Pedals without a stomp cannot be muted. */
  function viewOn(id: string): boolean {
    if (bypassAll.value) return false
    if (soloId.value !== null) return id === soloId.value
    return nodeOf(id)?.on !== false
  }

  /** The saved values with the audition overrides laid over the stomp switches; this is what the engine should hear. */
  function effectiveParams(): Record<string, number> {
    const out = paramsFor(graph.value, catalog.value)
    for (const n of graph.value.nodes) {
      const stomp = blockFor(catalog.value, n.type)?.stomp
      if (stomp) out[controlKey(n.id, stomp)] = viewOn(n.id) ? 1 : 0
    }
    return out
  }

  const compiled = computed<Compiled | null>(() => {
    const g = generated.value
    return g ? { code: g.code, controls: g.controls, params: effectiveParams() } : null
  })

  /** A fresh program with current knob values, for the debounced recompile (knobs may have moved since `compiled` was read). */
  function compileNow(): Compiled | null {
    const g = generated.value
    return g ? { code: g.code, controls: g.controls, params: effectiveParams() } : null
  }

  function structural(): void {
    dirty.value = true
    structuralRev.value++
  }

  function onLive(fn: (c: LiveChange) => void): () => void {
    liveListeners.add(fn)
    return () => liveListeners.delete(fn)
  }
  const emitLive = (c: LiveChange) => liveListeners.forEach((fn) => fn(c))

  const nodeOf = (id: string): GraphNode | undefined => graph.value.nodes.find((n) => n.id === id)
  const blockOf = (id: string): CatalogBlock | undefined => {
    const n = nodeOf(id)
    return n ? blockFor(catalog.value, n.type) : undefined
  }

  const snapshot = (): string => JSON.stringify({ nodes: toRaw(graph.value.nodes), edges: toRaw(graph.value.edges) })
  const syncCounts = () => {
    undoCount.value = history.undoCount
    redoCount.value = history.redoCount
  }
  /** Call before a change. A repeated `coalesceKey` within about 600 ms (a knob drag) stays one undo step. */
  function record(coalesceKey: string | null = null): void {
    history.record(snapshot(), Date.now(), coalesceKey)
    syncCounts()
  }

  /** Announces the stomp state the engine should have for every pedal that has one (after Bypass all, Solo, or a restore). */
  function announceStomps(): void {
    for (const n of graph.value.nodes) {
      const stomp = blockFor(catalog.value, n.type)?.stomp
      if (!stomp) continue
      const key = controlKey(n.id, stomp)
      emitLive({ key, value: viewOn(n.id) ? 1 : 0 })
    }
  }

  function setBypassAll(on: boolean): void {
    bypassAll.value = on
    if (on) soloId.value = null
    announceStomps()
  }

  function toggleSolo(id: string): void {
    if (!blockOf(id)?.stomp) return
    soloId.value = soloId.value === id ? null : id
    if (soloId.value) bypassAll.value = false
    announceStomps()
  }

  function restore(snap: string): void {
    const s = JSON.parse(snap) as Snapshot
    const keyBefore = structureKey.value
    const before = effectiveParams()
    graph.value.nodes = s.nodes
    graph.value.edges = s.edges
    selection.value = selection.value.filter((id) => nodeOf(id))
    if (soloId.value && !nodeOf(soloId.value)) soloId.value = null
    const after = effectiveParams()
    if (structureKey.value !== keyBefore) structural()
    else dirty.value = true
    // Knobs and stomps that differ are pushed live; a structural restore recompiles with these values too.
    for (const [key, value] of Object.entries(after)) if (before[key] !== value) emitLive({ key, value })
  }

  function undo(): boolean {
    const prev = history.undo(snapshot())
    syncCounts()
    if (prev === null) return false
    restore(prev)
    return true
  }

  function redo(): boolean {
    const next = history.redo(snapshot())
    syncCounts()
    if (next === null) return false
    restore(next)
    return true
  }

  function resetHistory(): void {
    history.clear()
    syncCounts()
    bypassAll.value = false
    soloId.value = null
  }

  function nextNodeId(type: string): string {
    const re = new RegExp(`^${type}(\\d+)$`)
    let top = 0
    for (const n of graph.value.nodes) {
      const m = re.exec(n.id)
      if (m) top = Math.max(top, Number(m[1]))
    }
    return `${type}${top + 1}`
  }

  function nextEdgeId(): string {
    const taken = new Set(graph.value.edges.map((e) => e.id))
    do edgeCounter++
    while (taken.has(`e${edgeCounter}`))
    return `e${edgeCounter}`
  }

  function resetEdgeCounter(): void {
    edgeCounter = graph.value.edges.reduce((top, e) => {
      const m = /^e(\d+)$/.exec(e.id)
      return m ? Math.max(top, Number(m[1])) : top
    }, 0)
  }

  /** Adds a pedal and returns its id, or null for Input/Output (single, fixed) and unknown types. */
  function addNode(type: string, x: number, y: number): string | null {
    if (type === INPUT_TYPE || type === OUTPUT_TYPE) return null
    if (!blockFor(catalog.value, type)) return null
    record()
    const id = nextNodeId(type)
    graph.value.nodes.push({ id, type, x, y })
    structural()
    return id
  }

  /** Removes pedals (never Input/Output) and wires as one undo step. Returns whether anything went. */
  function removeMany(nodeIds: string[], edgeIds: string[] = []): boolean {
    const gone = new Set(nodeIds.filter((id) => {
      const n = nodeOf(id)
      return n && n.type !== INPUT_TYPE && n.type !== OUTPUT_TYPE
    }))
    const wires = new Set(edgeIds.filter((id) => graph.value.edges.some((e) => e.id === id)))
    if (!gone.size && !wires.size) return false
    record()
    graph.value.nodes = graph.value.nodes.filter((x) => !gone.has(x.id))
    graph.value.edges = graph.value.edges.filter((e) => !wires.has(e.id) && !gone.has(e.source) && !gone.has(e.target))
    selection.value = selection.value.filter((s) => !gone.has(s))
    if (soloId.value && gone.has(soloId.value)) {
      soloId.value = null
      announceStomps()
    }
    structural()
    return true
  }

  const removeNode = (id: string): boolean => removeMany([id])

  /** Moves several nodes (a group drag) as one undo step. */
  function moveNodes(moves: Array<{ id: string; x: number; y: number }>): void {
    const changed = moves.filter((m) => {
      const n = nodeOf(m.id)
      return n && (n.x !== m.x || n.y !== m.y)
    })
    if (!changed.length) return
    record()
    for (const m of changed) {
      const n = nodeOf(m.id) as GraphNode
      n.x = m.x
      n.y = m.y
    }
    dirty.value = true
  }
  const moveNode = (id: string, x: number, y: number): void => moveNodes([{ id, x, y }])

  function copySelection(): boolean {
    const c = copyNodes(graph.value, selection.value)
    if (!c) return false
    clip.value = c
    pasteCount = 0
    return true
  }

  /** Puts a copy of `source` on the board, shifted `step` offsets, with new ids; wires between two copied pedals come along. */
  function place(source: Clip, step: number): string[] {
    const nodes = source.nodes.filter((n) => blockFor(catalog.value, n.type))
    if (!nodes.length) return []
    record()
    const ids = new Map<string, string>()
    const shift = PASTE_OFFSET * step
    for (const n of nodes) {
      const id = nextNodeId(n.type)
      ids.set(n.id, id)
      graph.value.nodes.push({ ...clone(n), id, x: n.x + shift, y: n.y + shift })
    }
    for (const e of source.edges) {
      const s = ids.get(e.source)
      const t = ids.get(e.target)
      if (s && t) graph.value.edges.push({ ...clone(e), id: nextEdgeId(), source: s, target: t })
    }
    selection.value = [...ids.values()]
    structural()
    return selection.value
  }

  function paste(): string[] {
    if (!clip.value) return []
    pasteCount++
    return place(clip.value, pasteCount)
  }

  /** Copy and paste in one go without touching the clipboard. */
  function duplicateSelection(): string[] {
    const c = copyNodes(graph.value, selection.value)
    return c ? place(c, 1) : []
  }

  /** Auto-arranges by signal depth, then asks the canvas to re-fit. One undo step. */
  function tidy(): void {
    const spots = tidyPositions(graph.value, catalog.value)
    record()
    for (const n of graph.value.nodes) {
      const p = spots.get(n.id)
      if (p) {
        n.x = p.x
        n.y = p.y
      }
    }
    dirty.value = true
    fitRev.value++
  }

  /** Makes a wire. Returns null on success or the plain-language reason it was refused. */
  function connect(req: WireRequest): string | null {
    const edge: GraphEdge = { id: nextEdgeId(), source: req.source, target: req.target, targetPort: req.targetPort }
    if (req.sourcePort) edge.sourcePort = req.sourcePort
    const verdict = canConnect(graph.value, catalog.value, edge)
    if (!verdict.ok) return verdict.reason
    record()
    graph.value.edges.push(edge)
    structural()
    return null
  }

  /** Same check as `connect` without making the wire; Vue Flow asks this while the cable is still being dragged. */
  function wireRefusal(req: WireRequest): string | null {
    const probe: GraphEdge = { id: '', source: req.source, target: req.target, targetPort: req.targetPort }
    if (req.sourcePort) probe.sourcePort = req.sourcePort
    const verdict = canConnect(graph.value, catalog.value, probe)
    return verdict.ok ? null : verdict.reason
  }

  function disconnect(edgeId: string): boolean {
    if (!graph.value.edges.some((e) => e.id === edgeId)) return false
    record()
    graph.value.edges = graph.value.edges.filter((e) => e.id !== edgeId)
    structural()
    return true
  }

  function setOn(nodeId: string, on: boolean): void {
    const n = nodeOf(nodeId)
    const stomp = blockOf(nodeId)?.stomp
    if (!n || !stomp) return
    if ((n.on !== false) !== on) record()
    n.on = on
    dirty.value = true
    // While Bypass all or Solo is active the engine keeps hearing the override; the saved stomp changes underneath it.
    emitLive({ key: controlKey(nodeId, stomp), value: viewOn(nodeId) ? 1 : 0 })
  }

  /** Stores a knob value (clamped to the catalog range) and announces it. Returns the stored value, or null for an unknown control. */
  function setParam(nodeId: string, label: string, value: number): number | null {
    const n = nodeOf(nodeId)
    const block = blockOf(nodeId)
    const control = block?.controls.find((c) => c.label === label)
    if (!n || !block || !control || !Number.isFinite(value)) return null
    if (block.stomp !== null && label === block.stomp) {
      setOn(nodeId, value >= 0.5)
      return value >= 0.5 ? 1 : 0
    }
    const v = Math.min(control.max, Math.max(control.min, value))
    if ((n.params?.[label] ?? control.init) !== v) record(`${nodeId}\u0000${label}`)
    if (!n.params) n.params = {}
    // Equal to init means "not set", which keeps saved graphs small and lets catalog default changes show through.
    if (v === control.init) delete n.params[label]
    else n.params[label] = v
    dirty.value = true
    emitLive({ key: controlKey(nodeId, label), value: v })
    return v
  }

  function select(ids: string[]): void {
    // Vue Flow reports selection back after every node update; ignoring equal sets stops that echo from looping.
    const same = ids.length === selection.value.length && ids.every((id) => selection.value.includes(id))
    if (!same) selection.value = ids
  }

  function newGraph(): void {
    graph.value = emptyGraph()
    selection.value = []
    edgeCounter = 0
    resetHistory()
    loadRev.value++
    structural()
    dirty.value = false
  }

  function loadGraph(g: Graph): void {
    graph.value = clone(g)
    selection.value = []
    resetEdgeCounter()
    resetHistory()
    loadRev.value++
    structural()
    dirty.value = false
  }

  function loadStarter(slug: string): boolean {
    const s = starters.value.find((x) => x.slug === slug)
    if (!s) return false
    // The starter is a template: the copy is unnamed so saving always asks for a name.
    loadGraph({ ...clone(s.graph), name: '' })
    return true
  }

  async function loadSaved(name: string): Promise<boolean> {
    try {
      loadGraph(await api.pedalboardGraph(name))
      graph.value.name = name
      error.value = null
      return true
    } catch (e) {
      error.value = msg(e)
      return false
    }
  }

  async function load(): Promise<void> {
    loading.value = true
    error.value = null
    try {
      const blocks = await api.pedalboardBlocks()
      catalog.value = blocks.catalog
      libText.value = blocks.lib
    } catch (e) {
      error.value = msg(e)
    }
    // Starting points ship with a later server change; a missing route just means an empty menu.
    const [graphs, startList] = await Promise.all([
      api.pedalboardGraphs().catch(() => []),
      api.pedalboardStarters().catch(() => []),
    ])
    savedNames.value = graphs.map((g) => g.name)
    starters.value = startList
    loading.value = false
  }

  async function save(name: string): Promise<PedalboardSaved | null> {
    const g = generated.value
    if (!g || !name.trim()) return null
    saving.value = true
    error.value = null
    try {
      const snapshot = { ...clone(graph.value), name: name.trim() }
      const res = await api.pedalboardSave({ graph: snapshot, code: g.code, params: paramsFor(snapshot, catalog.value), notes: '' })
      graph.value.name = res.name
      dirty.value = false
      if (!savedNames.value.includes(res.name)) savedNames.value = [...savedNames.value, res.name].sort()
      return res
    } catch (e) {
      error.value = msg(e)
      return null
    } finally {
      saving.value = false
    }
  }

  return {
    catalog, libText, graph, selection, dirty, issues, issueTexts, valid, starters, savedNames, error, loading, saving,
    structuralRev, loadRev, fitRev, undoCount, redoCount, bypassAll, soloId, compiled, compileNow, onLive, nodeOf, blockOf,
    addNode, removeNode, removeMany, moveNode, moveNodes, undo, redo, copySelection, paste, duplicateSelection, tidy, setBypassAll, toggleSolo, viewOn, connect, wireRefusal, disconnect, setParam, setOn, select, newGraph, loadGraph, loadStarter, loadSaved, load, save,
  }
})
