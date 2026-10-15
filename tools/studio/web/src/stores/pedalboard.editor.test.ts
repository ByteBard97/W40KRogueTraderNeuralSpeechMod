import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { COALESCE_MS } from '../pedalboard/history'
import { chainGraph, realCatalog } from '../test-utils/pedalboardCatalog'
import { usePedalboardStore, type LiveChange } from './pedalboard'

const HP_HZ = 'Highpass Hz (0 off)'

function setup() {
  const s = usePedalboardStore()
  s.catalog = realCatalog
  s.loadGraph(chainGraph())
  const live: LiveChange[] = []
  s.onLive((c) => live.push(c))
  return { s, live }
}

describe('pedalboard editor', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
    vi.setSystemTime(1_000_000)
  })
  afterEach(() => vi.useRealTimers())

  describe('undo and redo', () => {
    it('undoes and redoes add, remove, connect, disconnect, param and on', () => {
      const { s } = setup()
      const base = JSON.stringify(s.graph)
      const id = s.addNode('lowpass', 10, 10) as string
      expect(s.graph.nodes.some((n) => n.id === id)).toBe(true)
      s.undo()
      expect(JSON.stringify(s.graph)).toBe(base)
      s.redo()
      expect(s.graph.nodes.some((n) => n.id === id)).toBe(true)
      s.undo()

      s.disconnect('e2')
      s.undo()
      expect(s.graph.edges.map((e) => e.id)).toEqual(['e1', 'e2'])

      s.removeNode('highpass1')
      expect(s.graph.edges).toHaveLength(0)
      s.undo()
      expect(JSON.stringify(s.graph)).toBe(base)

      s.addNode('lowpass', 0, 0)
      s.undo()
      s.addNode('lowpass', 0, 0)
      expect(s.connect({ source: 'highpass1', target: 'lowpass1', sourcePort: 0, targetPort: 0 })).toBeNull()
      s.undo()
      expect(s.graph.edges.some((e) => e.target === 'lowpass1')).toBe(false)

      s.setOn('highpass1', false)
      s.undo()
      expect(s.nodeOf('highpass1')?.on).not.toBe(false)
      s.redo()
      expect(s.nodeOf('highpass1')?.on).toBe(false)
    })

    it('counts a knob drag as one step and restores the value before the drag', () => {
      const { s } = setup()
      for (let v = 100; v <= 500; v += 100) {
        s.setParam('highpass1', HP_HZ, v)
        vi.advanceTimersByTime(50)
      }
      expect(s.undoCount).toBe(1)
      s.undo()
      expect(s.nodeOf('highpass1')?.params?.[HP_HZ]).toBeUndefined()
      s.redo()
      expect(s.nodeOf('highpass1')?.params?.[HP_HZ]).toBe(500)
    })

    it('starts a new step after a pause, for another control, or for a repeat of the same value', () => {
      const { s } = setup()
      s.setParam('highpass1', HP_HZ, 100)
      vi.advanceTimersByTime(COALESCE_MS + 10)
      s.setParam('highpass1', HP_HZ, 200)
      expect(s.undoCount).toBe(2)
      s.setParam('highpass1', HP_HZ, 200)
      expect(s.undoCount).toBe(2)
      s.undo()
      expect(s.nodeOf('highpass1')?.params?.[HP_HZ]).toBe(100)
    })

    it('sends knob and stomp undo live without a recompile, and structural undo as a recompile', () => {
      const { s, live } = setup()
      s.setParam('highpass1', HP_HZ, 300)
      s.setOn('highpass1', false)
      live.length = 0
      const rev = s.structuralRev
      s.undo()
      s.undo()
      expect(live.map((c) => c.value)).toEqual([1, 0])
      expect(live[0].key).toMatch(/highpass1/)
      expect(s.structuralRev).toBe(rev)
      s.addNode('lowpass', 0, 0)
      const rev2 = s.structuralRev
      s.undo()
      expect(s.structuralRev).toBe(rev2 + 1)
    })

    it('treats a group delete and a group move as one step each', () => {
      const { s } = setup()
      s.addNode('lowpass', 0, 0)
      s.addNode('drive', 0, 0)
      const n = s.undoCount
      s.removeMany(['lowpass1', 'drive1'])
      expect(s.undoCount).toBe(n + 1)
      s.undo()
      expect(s.graph.nodes.map((x) => x.id)).toContain('drive1')
      s.moveNodes([{ id: 'lowpass1', x: 5, y: 5 }, { id: 'drive1', x: 6, y: 6 }])
      expect(s.undoCount).toBe(n + 1)
    })

    it('starts clean after a load, a starter or New, and clears redo on a fresh edit', () => {
      const { s } = setup()
      s.addNode('lowpass', 0, 0)
      expect(s.undoCount).toBe(1)
      s.loadGraph(chainGraph())
      expect([s.undoCount, s.redoCount]).toEqual([0, 0])
      s.addNode('lowpass', 0, 0)
      s.newGraph()
      expect(s.undo()).toBe(false)
      s.addNode('lowpass', 0, 0)
      s.undo()
      expect(s.redoCount).toBe(1)
      s.addNode('drive', 0, 0)
      expect(s.redoCount).toBe(0)
    })

    it('drops selected ids that undo removed and keeps the graph name', () => {
      const { s } = setup()
      s.graph.name = 'mine'
      const id = s.addNode('lowpass', 0, 0) as string
      s.select([id])
      s.undo()
      expect(s.selection).toEqual([])
      expect(s.graph.name).toBe('mine')
    })
  })

  describe('copy, paste and duplicate', () => {
    function twoPedals() {
      const c = setup()
      c.s.addNode('lowpass', 100, 100)
      c.s.connect({ source: 'highpass1', target: 'lowpass1', sourcePort: 0, targetPort: 0 })
      c.s.setParam('lowpass1', 'Lowpass Hz (0 off)', 4000)
      return c
    }

    it('keeps settings and the wire between two copied pedals, with new ids and a 40 px offset', () => {
      const { s } = twoPedals()
      const edgesBefore = s.graph.edges.length
      s.select(['highpass1', 'lowpass1'])
      expect(s.copySelection()).toBe(true)
      const ids = s.paste()
      expect(ids.sort()).toEqual(['highpass2', 'lowpass2'])
      expect(s.nodeOf('lowpass2')).toMatchObject({ x: 140, y: 140, params: { 'Lowpass Hz (0 off)': 4000 } })
      const added = s.graph.edges.slice(edgesBefore)
      expect(added).toHaveLength(1)
      expect(added[0]).toMatchObject({ source: 'highpass2', target: 'lowpass2' })
      expect(new Set(s.graph.edges.map((e) => e.id)).size).toBe(s.graph.edges.length)
      expect(s.selection.sort()).toEqual(['highpass2', 'lowpass2'])
      s.undo()
      expect(s.nodeOf('highpass2')).toBeUndefined()
    })

    it('drops wires to pedals that were not copied and never copies Input or Output', () => {
      const { s } = twoPedals()
      s.select(['input', 'output'])
      expect(s.copySelection()).toBe(false)
      expect(s.paste()).toEqual([])
      s.select(['input', 'lowpass1'])
      s.copySelection()
      s.paste()
      expect(s.graph.nodes.filter((n) => n.type === 'input' || n.type === 'output')).toHaveLength(2)
      expect(s.nodeOf('lowpass2')).toBeDefined()
      expect(s.graph.edges.filter((e) => e.target === 'lowpass2' || e.source === 'lowpass2')).toHaveLength(0)
    })

    it('pastes further each time and duplicates without touching the clipboard', () => {
      const { s } = twoPedals()
      s.select(['lowpass1'])
      s.copySelection()
      s.paste()
      s.select(['lowpass1'])
      s.paste()
      expect(s.nodeOf('lowpass3')).toMatchObject({ x: 180, y: 180 })
      s.select(['highpass1'])
      expect(s.duplicateSelection()).toEqual(['highpass2'])
      s.paste()
      expect(s.nodeOf('lowpass4')).toBeDefined()
    })
  })

  describe('tidy', () => {
    it('is one undo step and asks the canvas to re-fit', () => {
      const { s } = setup()
      s.addNode('lowpass', 7, 7)
      const before = JSON.stringify(s.graph.nodes)
      const n = s.undoCount
      const fit = s.fitRev
      s.tidy()
      expect(s.undoCount).toBe(n + 1)
      expect(s.fitRev).toBe(fit + 1)
      expect(JSON.stringify(s.graph.nodes)).not.toBe(before)
      s.undo()
      expect(JSON.stringify(s.graph.nodes)).toBe(before)
    })
  })

  describe('bypass all and solo', () => {
    const stompKeys = (live: LiveChange[]) => Object.fromEntries(live.map((c) => [c.key, c.value]))

    it('bypass all mutes every pedal live, leaves the saved graph alone, and restores on release', () => {
      const { s, live } = setup()
      s.addNode('lowpass', 0, 0)
      s.setOn('lowpass1', false)
      const saved = JSON.stringify(s.graph)
      live.length = 0
      s.setBypassAll(true)
      expect(live.map((c) => c.value)).toEqual([0, 0])
      expect(JSON.stringify(s.graph)).toBe(saved)
      expect(Object.entries(s.compileNow()?.params ?? {}).filter(([k]) => /on$/.test(k)).every(([, v]) => v === 0)).toBe(true)
      live.length = 0
      s.setBypassAll(false)
      const restored = stompKeys(live)
      expect(Object.values(restored).sort()).toEqual([0, 1])
      expect(JSON.stringify(s.graph)).toBe(saved)
    })

    it('solo bypasses every other pedal, forces the soloed one on, and releases on a second click', () => {
      const { s, live } = setup()
      s.addNode('lowpass', 0, 0)
      s.setOn('lowpass1', false)
      const saved = JSON.stringify(s.graph)
      live.length = 0
      s.toggleSolo('lowpass1')
      expect(live.map((c) => [c.key.includes('lowpass1'), c.value])).toEqual([[false, 0], [true, 1]])
      expect(JSON.stringify(s.graph)).toBe(saved)
      live.length = 0
      s.toggleSolo('lowpass1')
      expect(live.map((c) => c.value)).toEqual([1, 0])
      expect(s.soloId).toBeNull()
      expect(JSON.stringify(s.graph)).toBe(saved)
    })

    it('keeps the override when a stomp is clicked underneath it, and the two modes exclude each other', () => {
      const { s, live } = setup()
      s.setBypassAll(true)
      live.length = 0
      s.setOn('highpass1', true)
      expect(live.at(-1)?.value).toBe(0)
      expect(s.nodeOf('highpass1')?.on).toBe(true)
      s.toggleSolo('highpass1')
      expect(s.bypassAll).toBe(false)
      s.setBypassAll(true)
      expect(s.soloId).toBeNull()
    })

    it('does not enter the undo history and is cleared by a load', () => {
      const { s } = setup()
      s.setBypassAll(true)
      s.toggleSolo('highpass1')
      expect(s.undoCount).toBe(0)
      s.loadGraph(chainGraph())
      expect([s.bypassAll, s.soloId]).toEqual([false, null])
    })
  })
})
