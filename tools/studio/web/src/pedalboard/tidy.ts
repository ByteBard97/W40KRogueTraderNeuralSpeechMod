// Auto-arrange: columns by signal depth, left to right, wrapped into rows so a long series does not run off the screen.
// The sizes and gaps match tools/fx_lab/migrate_scenarios.py so a tidied board looks like a shipped starting point.
import { blockFor, layerDepths } from './graph'
import type { Catalog, Graph } from './types'

export const NODE_WIDTH = 220
export const X_STEP = 260
export const COLUMNS_PER_ROW = 6
export const HEAD_PX = 57
export const ROW_PX = 62
export const ROW_GAP = 48

export function nodeHeight(type: string, catalog: Catalog): number {
  const block = blockFor(catalog, type)
  if (!block) return HEAD_PX
  return HEAD_PX + ROW_PX * block.controls.filter((c) => c.label !== block.stomp).length
}

/** New x/y per node id. Nodes of one layer stack in their current top-to-bottom order. A cyclic graph falls back to one node per layer. */
export function tidyPositions(graph: Graph, catalog: Catalog): Map<string, { x: number; y: number }> {
  const depths = layerDepths(graph)
  const order = graph.nodes.map((n, i) => ({ n, i }))
  const layerOf = (id: string, i: number) => (depths ? depths.get(id) ?? 0 : i)
  const layers = new Map<number, typeof order>()
  for (const item of order) {
    const d = layerOf(item.n.id, item.i)
    layers.set(d, [...(layers.get(d) ?? []), item])
  }
  const ranks = [...layers.keys()].sort((a, b) => a - b)
  const out = new Map<string, { x: number; y: number }>()
  let rowY = 0
  for (let start = 0; start < ranks.length; start += COLUMNS_PER_ROW) {
    let rowHeight = 0
    ranks.slice(start, start + COLUMNS_PER_ROW).forEach((rank, col) => {
      const stack = (layers.get(rank) ?? []).sort((a, b) => a.n.y - b.n.y || a.i - b.i)
      let y = rowY
      for (const { n } of stack) {
        out.set(n.id, { x: col * X_STEP, y })
        y += nodeHeight(n.type, catalog) + ROW_GAP
      }
      rowHeight = Math.max(rowHeight, y - rowY)
    })
    rowY += rowHeight
  }
  return out
}
