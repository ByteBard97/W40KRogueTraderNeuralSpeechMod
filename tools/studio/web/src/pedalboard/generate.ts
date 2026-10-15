// Graph -> Faust program. The graph is laid out in topological layers (longest path from the input). Between
// layers a route() picks the channels each node input needs (fan-out is several pairs from one source channel) and
// carries wires that skip a layer through with si.bus. Every wire is stereo, so a wire is two channels.
import { blockFor, INPUT_TYPE, OUTPUT_TYPE, controlKey, layerDepths, paramsFor, portCounts, sourcePortOf, validate } from './graph'
import { GraphError } from './types'
import type { Catalog, Control, Generated, Graph, GraphEdge, GraphNode } from './types'

export { paramsFor, controlKey, validate, canConnect } from './graph'

const CHANNELS_PER_WIRE = 2
const STDFAUST_IMPORT = /^[ \t]*import\(\s*"stdfaust\.lib"\s*\)\s*;[ \t]*\r?\n?/gm
const INDENT = '  '

interface Wire {
  nodeId: string
  port: number
}

function sameWire(a: Wire, b: Wire): boolean {
  return a.nodeId === b.nodeId && a.port === b.port
}

// route(nIn, nOut, (in,out), ...) with 1-based indices; null when it would be a plain wire-through.
function routeExpr(nIn: number, pairs: Array<[number, number]>): string | null {
  const identity = pairs.length === nIn && pairs.every(([i, o], idx) => i === idx + 1 && o === idx + 1)
  if (identity) return null
  return `route(${nIn}, ${pairs.length}, ${pairs.map(([i, o]) => `(${i},${o})`).join(', ')})`
}

function nodeBox(node: GraphNode, catalog: Catalog): string {
  const block = blockFor(catalog, node.type)
  if (!block) throw new GraphError([{ code: 'unknown-type', message: `unknown type ${node.type}`, nodeId: node.id }])
  return `vgroup("${node.id}", ${block.node})`
}

function layerOf(graph: Graph, depths: Map<string, number>): GraphNode[][] {
  const deepest = Math.max(...depths.values())
  const layers: GraphNode[][] = []
  for (let d = 1; d <= deepest; d++) layers.push(graph.nodes.filter((n) => depths.get(n.id) === d))
  return layers
}

function programBody(graph: Graph, catalog: Catalog, depths: Map<string, number>): string {
  const input = graph.nodes.find((n) => n.type === INPUT_TYPE) as GraphNode
  let state: Wire[] = [{ nodeId: input.id, port: 0 }]
  const stages: string[] = [`${INDENT}// ${input.id}: mono input to a stereo wire\n${INDENT}(_ <: (_, _))`]
  const layers = layerOf(graph, depths)

  layers.forEach((layer, idx) => {
    const k = idx + 1
    const incoming = (n: GraphNode): GraphEdge[] =>
      graph.edges.filter((e) => e.target === n.id).sort((a, b) => a.targetPort - b.targetPort)

    // Source wires for each node input port, in node order then port order.
    const wanted: Wire[] = []
    for (const n of layer) {
      for (const e of incoming(n)) wanted.push({ nodeId: e.source, port: sourcePortOf(e) })
    }
    // Wires still needed by a later layer travel through this one untouched.
    const keep = state.filter((w) =>
      graph.edges.some(
        (e) => e.source === w.nodeId && sourcePortOf(e) === w.port && (depths.get(e.target) ?? 0) > k,
      ),
    )
    const pairs: Array<[number, number]> = []
    ;[...wanted, ...keep].forEach((w, o) => {
      const at = state.findIndex((s) => sameWire(s, w))
      for (let c = 0; c < CHANNELS_PER_WIRE; c++) pairs.push([at * CHANNELS_PER_WIRE + c + 1, o * CHANNELS_PER_WIRE + c + 1])
    })
    pairs.sort((a, b) => a[1] - b[1])
    const route = routeExpr(state.length * CHANNELS_PER_WIRE, pairs)
    const ids = layer.map((n) => n.id).join(', ')
    if (route) stages.push(`${INDENT}// into layer ${k}: ${ids}\n${INDENT}: ${route}`)

    const boxes = layer.map((n) => nodeBox(n, catalog))
    if (keep.length) boxes.push(`si.bus(${keep.length * CHANNELS_PER_WIRE})`)
    const inner = boxes.map((b) => `${INDENT}${INDENT}${b}`).join(',\n')
    stages.push(`${INDENT}// layer ${k}: ${ids}\n${INDENT}: (\n${inner}\n${INDENT})`)

    const produced: Wire[] = []
    for (const n of layer) {
      const outs = n.type === OUTPUT_TYPE ? 1 : (portCounts(n, catalog)?.outputs ?? 0)
      for (let p = 0; p < outs; p++) produced.push({ nodeId: n.id, port: p })
    }
    state = [...produced, ...keep]
  })
  return stages.join('\n')
}

function controlsOf(graph: Graph, catalog: Catalog): Control[] {
  const out: Control[] = []
  for (const n of graph.nodes) {
    const block = n.type === INPUT_TYPE ? undefined : blockFor(catalog, n.type)
    if (!block) continue
    for (const c of block.controls) {
      out.push({
        key: controlKey(n.id, c.label),
        nodeId: n.id,
        label: c.label,
        type: c.type,
        init: c.init,
        min: c.min,
        max: c.max,
        step: c.step,
      })
    }
  }
  return out
}

export function generate(graph: Graph, catalog: Catalog, libText: string): Generated {
  const issues = validate(graph, catalog)
  if (issues.length) throw new GraphError(issues)
  const depths = layerDepths(graph) as Map<string, number>
  const lib = libText.replace(STDFAUST_IMPORT, '').replace(/\s+$/, '')
  // The outer vgroup("fx") is mandatory: Faust drops a lone top-level group from addresses, which would break the
  // /fx/<nodeId>/<label> addressing every runtime derives its keys from.
  const code =
    `import("stdfaust.lib");\n\n${lib}\n\n` +
    `process = vgroup("fx",\n${programBody(graph, catalog, depths)}\n);\n`
  return { code, controls: controlsOf(graph, catalog) }
}
