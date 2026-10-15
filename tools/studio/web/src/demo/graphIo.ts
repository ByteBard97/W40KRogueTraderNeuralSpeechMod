// Import and export of a graph as a plain JSON file. Validation is shape-only plus "block types exist": a
// hand-edited or foreign file must produce a readable message, never a half-loaded board.
import type { Catalog, Graph } from '../pedalboard/types'

const GRAPH_VERSION = 1
const NAME_RX = /^[A-Za-z0-9_-]{1,60}$/

export class GraphFileError extends Error {}

const isObject = (v: unknown): v is Record<string, unknown> => typeof v === 'object' && v !== null && !Array.isArray(v)
const isNum = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

export function checkName(name: unknown): string {
  if (typeof name !== 'string' || !NAME_RX.test(name)) throw new GraphFileError('Graph names use 1 to 60 letters, digits, underscore or hyphen.')
  return name
}

/** Throws GraphFileError with a plain-English reason; returns the same object typed as Graph. */
export function checkGraph(value: unknown, catalog?: Catalog): Graph {
  if (!isObject(value)) throw new GraphFileError('This is not a graph file: expected a JSON object.')
  if (value.version !== GRAPH_VERSION) throw new GraphFileError(`Unsupported graph version ${JSON.stringify(value.version)}; expected ${GRAPH_VERSION}.`)
  if (!Array.isArray(value.nodes) || !Array.isArray(value.edges)) throw new GraphFileError('The graph needs a "nodes" list and an "edges" list.')
  const known = catalog ? new Set(catalog.blocks.map((b) => b.id)) : null
  const ids = new Set<string>()
  value.nodes.forEach((n: unknown, i: number) => {
    if (!isObject(n) || typeof n.id !== 'string' || typeof n.type !== 'string') throw new GraphFileError(`Node ${i + 1} needs a text id and type.`)
    if (!isNum(n.x) || !isNum(n.y)) throw new GraphFileError(`Node "${n.id}" needs numeric x and y.`)
    if (ids.has(n.id)) throw new GraphFileError(`Two nodes share the id "${n.id}".`)
    if (known && !known.has(n.type)) throw new GraphFileError(`Node "${n.id}" uses the unknown pedal type "${n.type}".`)
    if (n.params !== undefined && (!isObject(n.params) || !Object.values(n.params).every(isNum))) throw new GraphFileError(`Node "${n.id}" has parameters that are not numbers.`)
    ids.add(n.id)
  })
  value.edges.forEach((e: unknown, i: number) => {
    if (!isObject(e) || typeof e.id !== 'string' || typeof e.source !== 'string' || typeof e.target !== 'string' || !isNum(e.targetPort)) {
      throw new GraphFileError(`Wire ${i + 1} needs an id, a source, a target and a numeric targetPort.`)
    }
    if (!ids.has(e.source) || !ids.has(e.target)) throw new GraphFileError(`Wire "${e.id}" points at a pedal that is not in the file.`)
  })
  return value as unknown as Graph
}

export function parseGraphFile(text: string, catalog?: Catalog): Graph {
  let parsed: unknown
  try { parsed = JSON.parse(text) } catch { throw new GraphFileError('This file is not valid JSON.') }
  return checkGraph(parsed, catalog)
}

export const serializeGraph = (g: Graph): string => JSON.stringify(g, null, 2)

/** A safe download name from a free-text graph name. */
export function fileStem(name: string): string {
  return name.trim().replace(/[^A-Za-z0-9_-]+/g, '-').replace(/^-+|-+$/g, '').slice(0, 60) || 'pedalboard-graph'
}
