import { readdirSync, readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { describe, expect, it } from 'vitest'
import { realCatalog } from '../test-utils/pedalboardCatalog'
import { COLUMNS_PER_ROW, HEAD_PX, nodeHeight, NODE_WIDTH, ROW_PX, tidyPositions } from './tidy'
import type { Graph } from './types'

const STARTERS = join(dirname(fileURLToPath(import.meta.url)), '..', '..', '..', '..', 'fx_lab', 'starters')

function overlaps(g: Graph, pos: Map<string, { x: number; y: number }>): string[] {
  const boxes = g.nodes.map((n) => {
    const p = pos.get(n.id) as { x: number; y: number }
    return { id: n.id, x: p.x, y: p.y, w: NODE_WIDTH, h: nodeHeight(n.type, realCatalog) }
  })
  const bad: string[] = []
  for (let i = 0; i < boxes.length; i++) {
    for (let j = i + 1; j < boxes.length; j++) {
      const a = boxes[i]
      const b = boxes[j]
      if (a.x < b.x + b.w && b.x < a.x + a.w && a.y < b.y + b.h && b.y < a.y + a.h) bad.push(`${a.id}/${b.id}`)
    }
  }
  return bad
}

function series(count: number): Graph {
  const types = ['highpass', 'lowpass', 'drive', 'chorus']
  const nodes: Graph['nodes'] = [{ id: 'input', type: 'input', x: 0, y: 0 }]
  const edges: Graph['edges'] = []
  let prev = 'input'
  for (let i = 0; i < count; i++) {
    const id = `p${i}`
    nodes.push({ id, type: types[i % types.length], x: 0, y: 0 })
    edges.push({ id: `e${i}`, source: prev, target: id, targetPort: 0 })
    prev = id
  }
  nodes.push({ id: 'output', type: 'output', x: 0, y: 0 })
  edges.push({ id: 'eo', source: prev, target: 'output', targetPort: 0 })
  return { version: 1, name: '', nodes, edges }
}

describe('tidy', () => {
  it('estimates height as the title plus a row per non-stomp control', () => {
    const hp = realCatalog.blocks.find((b) => b.id === 'highpass')
    expect(nodeHeight('highpass', realCatalog)).toBe(HEAD_PX + ROW_PX * ((hp?.controls.length ?? 0) - 1))
  })

  it('leaves no two nodes overlapping in any of the shipped starting points', () => {
    const files = readdirSync(STARTERS).filter((f) => f.endsWith('.json'))
    expect(files.length).toBeGreaterThanOrEqual(49)
    for (const f of files) {
      const g = (JSON.parse(readFileSync(join(STARTERS, f), 'utf8')) as { graph: Graph }).graph
      const pos = tidyPositions(g, realCatalog)
      expect(pos.size, f).toBe(g.nodes.length)
      expect(overlaps(g, pos), f).toEqual([])
    }
  })

  it('orders columns by signal depth', () => {
    const g = series(3)
    const pos = tidyPositions(g, realCatalog)
    const xs = ['input', 'p0', 'p1', 'p2', 'output'].map((id) => pos.get(id)?.x as number)
    expect(xs).toEqual([...xs].sort((a, b) => a - b))
    expect(new Set(xs).size).toBe(5)
  })

  it('stacks parallel branches of one layer in the same column', () => {
    const g: Graph = { version: 1, name: '', nodes: [
      { id: 'input', type: 'input', x: 0, y: 0 }, { id: 'a', type: 'highpass', x: 0, y: 300 }, { id: 'b', type: 'lowpass', x: 0, y: 10 },
      { id: 'mix2', type: 'mix2', x: 0, y: 0 }, { id: 'output', type: 'output', x: 0, y: 0 },
    ], edges: [
      { id: 'e1', source: 'input', target: 'a', targetPort: 0 }, { id: 'e2', source: 'input', target: 'b', targetPort: 0 },
      { id: 'e3', source: 'a', target: 'mix2', targetPort: 0 }, { id: 'e4', source: 'b', target: 'mix2', targetPort: 1 },
      { id: 'e5', source: 'mix2', target: 'output', targetPort: 0 },
    ] }
    const pos = tidyPositions(g, realCatalog)
    expect(pos.get('a')?.x).toBe(pos.get('b')?.x)
    expect((pos.get('b')?.y as number) < (pos.get('a')?.y as number)).toBe(true)   // keeps the existing top-to-bottom order
    expect(overlaps(g, pos)).toEqual([])
  })

  it('wraps a 28-pedal series into rows of at most six columns without overlap', () => {
    const g = series(28)
    const pos = tidyPositions(g, realCatalog)
    expect(overlaps(g, pos)).toEqual([])
    const columns = new Set([...pos.values()].map((p) => p.x))
    expect(columns.size).toBeLessThanOrEqual(COLUMNS_PER_ROW)
    expect(Math.max(...[...pos.values()].map((p) => p.y))).toBeGreaterThan(0)
  })
})
