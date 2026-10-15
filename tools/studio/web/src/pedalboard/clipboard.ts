// Copy/paste of pedals. Input and Output are single and fixed, so they are never copied.
import { INPUT_TYPE, OUTPUT_TYPE } from './graph'
import type { Graph, GraphEdge, GraphNode } from './types'

export const PASTE_OFFSET = 40

export interface Clip { nodes: GraphNode[]; edges: GraphEdge[] }

const copyable = (n: GraphNode) => n.type !== INPUT_TYPE && n.type !== OUTPUT_TYPE

/** A deep copy of the chosen pedals and the wires that run between two of them; null when nothing copyable is chosen. */
export function copyNodes(graph: Graph, ids: string[]): Clip | null {
  const chosen = new Set(ids)
  const nodes = graph.nodes.filter((n) => chosen.has(n.id) && copyable(n))
  if (!nodes.length) return null
  const kept = new Set(nodes.map((n) => n.id))
  const edges = graph.edges.filter((e) => kept.has(e.source) && kept.has(e.target))
  return JSON.parse(JSON.stringify({ nodes, edges })) as Clip
}
