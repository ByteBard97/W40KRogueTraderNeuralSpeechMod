// Graph validation, connection checks and parameter mapping. Pure functions, no DOM.
import type {
  CanConnectResult,
  Catalog,
  CatalogBlock,
  Graph,
  GraphEdge,
  GraphIssue,
  GraphNode,
} from './types'

export const INPUT_TYPE = 'input'
export const OUTPUT_TYPE = 'output'
const NODE_ID_PATTERN = /^[A-Za-z][A-Za-z0-9]*$/
const FIRST_PORT = 0

// Same rule as dd_render.short in Python and keyOf in render_wasm.mjs: it is how a control address becomes a flat key.
export function short(text: string): string {
  return text.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
}

export function controlKey(nodeId: string, label: string): string {
  return `${nodeId}_${short(label)}`
}

export function blockFor(catalog: Catalog, type: string): CatalogBlock | undefined {
  return catalog.blocks.find((b) => b.id === type)
}

// Stereo wires in and out of a node. The input node has no catalog entry requirement; the output node never feeds anything.
export function portCounts(node: GraphNode, catalog: Catalog): { inputs: number; outputs: number } | null {
  if (node.type === INPUT_TYPE) return { inputs: 0, outputs: 1 }
  const block = blockFor(catalog, node.type)
  if (!block) return null
  if (node.type === OUTPUT_TYPE) return { inputs: block.inputs, outputs: 0 }
  return { inputs: block.inputs, outputs: block.outputs }
}

export function sourcePortOf(edge: GraphEdge): number {
  return edge.sourcePort ?? FIRST_PORT
}

// True when `to` can be reached from `from` by following wires forwards.
function reaches(edges: GraphEdge[], from: string, to: string): boolean {
  const seen = new Set<string>([from])
  const stack = [from]
  while (stack.length) {
    const cur = stack.pop() as string
    if (cur === to) return true
    for (const e of edges) {
      if (e.source === cur && !seen.has(e.target)) {
        seen.add(e.target)
        stack.push(e.target)
      }
    }
  }
  return false
}

export function canConnect(graph: Graph, catalog: Catalog, edge: GraphEdge): CanConnectResult {
  const src = graph.nodes.find((n) => n.id === edge.source)
  const dst = graph.nodes.find((n) => n.id === edge.target)
  if (!src || !dst) return { ok: false, reason: 'wire end points at a missing node' }
  if (src.id === dst.id) return { ok: false, reason: 'a node cannot feed itself' }
  const srcPorts = portCounts(src, catalog)
  const dstPorts = portCounts(dst, catalog)
  if (!srcPorts || !dstPorts) return { ok: false, reason: 'unknown block type' }
  if (src.type === OUTPUT_TYPE) return { ok: false, reason: 'the output node has nothing to give' }
  if (dst.type === INPUT_TYPE) return { ok: false, reason: 'the input node takes no wire' }
  if (sourcePortOf(edge) < 0 || sourcePortOf(edge) >= srcPorts.outputs || !Number.isInteger(sourcePortOf(edge))) {
    return { ok: false, reason: 'no such output port' }
  }
  if (!Number.isInteger(edge.targetPort) || edge.targetPort < 0 || edge.targetPort >= dstPorts.inputs) {
    return { ok: false, reason: 'no such input port' }
  }
  const taken = graph.edges.some((e) => e.id !== edge.id && e.target === edge.target && e.targetPort === edge.targetPort)
  if (taken) return { ok: false, reason: 'that input already has a wire' }
  if (reaches(graph.edges, dst.id, src.id)) return { ok: false, reason: 'this wire would make a loop' }
  return { ok: true }
}

// Longest-path depth from the input node per node id, or null when the graph has a cycle (or no input).
export function layerDepths(graph: Graph): Map<string, number> | null {
  const indegree = new Map<string, number>(graph.nodes.map((n) => [n.id, 0]))
  for (const e of graph.edges) indegree.set(e.target, (indegree.get(e.target) ?? 0) + 1)
  const depth = new Map<string, number>(graph.nodes.map((n) => [n.id, 0]))
  const queue = graph.nodes.filter((n) => indegree.get(n.id) === 0).map((n) => n.id)
  let visited = 0
  while (queue.length) {
    const id = queue.shift() as string
    visited++
    for (const e of graph.edges) {
      if (e.source !== id) continue
      depth.set(e.target, Math.max(depth.get(e.target) ?? 0, (depth.get(id) ?? 0) + 1))
      indegree.set(e.target, (indegree.get(e.target) ?? 0) - 1)
      if (indegree.get(e.target) === 0) queue.push(e.target)
    }
  }
  return visited === graph.nodes.length ? depth : null
}

function reachableFrom(graph: Graph, start: string, forward: boolean): Set<string> {
  const seen = new Set<string>([start])
  const stack = [start]
  while (stack.length) {
    const cur = stack.pop() as string
    for (const e of graph.edges) {
      const from = forward ? e.source : e.target
      const to = forward ? e.target : e.source
      if (from === cur && !seen.has(to)) {
        seen.add(to)
        stack.push(to)
      }
    }
  }
  return seen
}

export function validate(graph: Graph, catalog: Catalog): GraphIssue[] {
  const issues: GraphIssue[] = []
  const ids = new Set<string>()
  const nodeById = new Map<string, GraphNode>()
  for (const n of graph.nodes) {
    if (!NODE_ID_PATTERN.test(n.id)) {
      issues.push({ code: 'bad-id', message: `node id "${n.id}" must match ${NODE_ID_PATTERN}`, nodeId: n.id })
    }
    if (ids.has(n.id)) issues.push({ code: 'duplicate-id', message: `node id "${n.id}" is used twice`, nodeId: n.id })
    ids.add(n.id)
    nodeById.set(n.id, n)
    if (!portCounts(n, catalog)) {
      issues.push({ code: 'unknown-type', message: `node ${n.id} has unknown type "${n.type}"`, nodeId: n.id })
    }
  }
  const inputs = graph.nodes.filter((n) => n.type === INPUT_TYPE)
  const outputs = graph.nodes.filter((n) => n.type === OUTPUT_TYPE)
  if (inputs.length !== 1) {
    issues.push({ code: 'no-path', message: `the graph needs exactly one input node, found ${inputs.length}` })
  }
  if (outputs.length !== 1) {
    issues.push({ code: 'no-path', message: `the graph needs exactly one output node, found ${outputs.length}` })
  }

  const edgeIds = new Set<string>()
  const taken = new Map<string, string>()
  const sound: GraphEdge[] = []
  for (const e of graph.edges) {
    if (edgeIds.has(e.id)) issues.push({ code: 'duplicate-id', message: `edge id "${e.id}" is used twice`, edgeId: e.id })
    edgeIds.add(e.id)
    const src = nodeById.get(e.source)
    const dst = nodeById.get(e.target)
    if (!src || !dst) {
      issues.push({ code: 'bad-edge', message: `edge ${e.id} points at a missing node`, edgeId: e.id })
      continue
    }
    sound.push(e)
    const sp = portCounts(src, catalog)
    const dp = portCounts(dst, catalog)
    if (sp && (!Number.isInteger(sourcePortOf(e)) || sourcePortOf(e) < 0 || sourcePortOf(e) >= sp.outputs)) {
      issues.push({ code: 'bad-port', message: `edge ${e.id}: ${src.id} has no output port ${sourcePortOf(e)}`, edgeId: e.id })
    }
    if (dp && (!Number.isInteger(e.targetPort) || e.targetPort < 0 || e.targetPort >= dp.inputs)) {
      issues.push({ code: 'bad-port', message: `edge ${e.id}: ${dst.id} has no input port ${e.targetPort}`, edgeId: e.id })
    }
    const slot = `${e.target}:${e.targetPort}`
    const prior = taken.get(slot)
    if (prior) {
      issues.push({ code: 'port-taken', message: `edge ${e.id} and ${prior} both feed ${slot}`, edgeId: e.id, nodeId: e.target })
    } else {
      taken.set(slot, e.id)
    }
  }

  for (const n of graph.nodes) {
    const pc = portCounts(n, catalog)
    if (!pc) continue
    for (let p = 0; p < pc.inputs; p++) {
      if (!taken.has(`${n.id}:${p}`)) {
        issues.push({ code: 'missing-input', message: `node ${n.id} input ${p} has no wire`, nodeId: n.id })
      }
    }
  }

  const sane: Graph = { ...graph, edges: sound }
  if (layerDepths(sane) === null) {
    issues.push({ code: 'cycle', message: 'the wires form a loop' })
  } else if (inputs.length === 1 && outputs.length === 1) {
    const fromInput = reachableFrom(sane, inputs[0].id, true)
    const toOutput = reachableFrom(sane, outputs[0].id, false)
    for (const n of graph.nodes) {
      if (!fromInput.has(n.id) || !toOutput.has(n.id)) {
        issues.push({ code: 'no-path', message: `node ${n.id} is not on a path from the input to the output`, nodeId: n.id })
      }
    }
  }
  return issues
}

// Flat key -> value for every control of every node that has a Faust box, with catalog defaults filled in.
export function paramsFor(graph: Graph, catalog: Catalog): Record<string, number> {
  const out: Record<string, number> = {}
  for (const n of graph.nodes) {
    if (n.type === INPUT_TYPE) continue
    const block = blockFor(catalog, n.type)
    if (!block) continue
    for (const c of block.controls) {
      const key = controlKey(n.id, c.label)
      if (block.stomp !== null && c.label === block.stomp) out[key] = n.on === false ? 0 : 1
      else out[key] = n.params?.[c.label] ?? c.init
    }
  }
  return out
}
