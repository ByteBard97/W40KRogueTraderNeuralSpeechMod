import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { paramsFor } from '../pedalboard/graph'
import { chainGraph, realCatalog, realLib } from '../test-utils/pedalboardCatalog'
import { usePedalboardStore } from './pedalboard'

vi.mock('../api/client', () => ({
  api: { pedalboardBlocks: vi.fn(), pedalboardGraphs: vi.fn(), pedalboardGraph: vi.fn(), pedalboardSave: vi.fn(), pedalboardStarters: vi.fn() },
}))

async function loaded() {
  const s = usePedalboardStore()
  await s.load()
  return s
}

describe('pedalboard store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.pedalboardBlocks).mockResolvedValue({ lib: realLib, catalog: realCatalog })
    vi.mocked(api.pedalboardGraphs).mockResolvedValue([{ name: 'zeta', updated: 1 }, { name: 'alpha', updated: 2 }])
    vi.mocked(api.pedalboardStarters).mockResolvedValue([
      { slug: 'chain', name: 'Chain', description: 'd', category: 'Test', graph: chainGraph() },
    ])
  })

  it('loads the catalog, saved names and starters; a missing starters route gives an empty list', async () => {
    let s = await loaded()
    expect(s.catalog.blocks.length).toBeGreaterThan(20)
    expect(s.savedNames).toEqual(['zeta', 'alpha'])
    expect(s.starters).toHaveLength(1)
    setActivePinia(createPinia())
    vi.mocked(api.pedalboardStarters).mockRejectedValue(new Error('404'))
    s = await loaded()
    expect(s.starters).toEqual([])
    expect(s.error).toBeNull()
  })

  it('starts as Input and Output, invalid until wired', async () => {
    const s = await loaded()
    expect(s.graph.nodes.map((n) => n.type)).toEqual(['input', 'output'])
    expect(s.valid).toBe(false)
    expect(s.compiled).toBeNull()
    expect(s.issueTexts).toContain('The Output is not connected')
  })

  it('adds nodes with unique valid ids and refuses a second Input or Output', async () => {
    const s = await loaded()
    const a = s.addNode('highpass', 10, 20)
    const b = s.addNode('highpass', 30, 40)
    expect(a).toBe('highpass1')
    expect(b).toBe('highpass2')
    expect(a).toMatch(/^[A-Za-z][A-Za-z0-9]*$/)
    expect(s.addNode('input', 0, 0)).toBeNull()
    expect(s.addNode('output', 0, 0)).toBeNull()
    expect(s.addNode('nope', 0, 0)).toBeNull()
    s.removeNode('highpass1')
    expect(s.addNode('highpass', 0, 0)).toBe('highpass3')
    expect(s.dirty).toBe(true)
  })

  it('removes a node with its wires but never Input or Output', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    expect(s.removeNode('input')).toBe(false)
    expect(s.removeNode('output')).toBe(false)
    expect(s.removeNode('highpass1')).toBe(true)
    expect(s.graph.edges).toEqual([])
    expect(s.graph.nodes).toHaveLength(2)
  })

  it('moves a node without a structural change', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    const rev = s.structuralRev
    s.moveNode('highpass1', 5, 6)
    expect(s.nodeOf('highpass1')).toMatchObject({ x: 5, y: 6 })
    expect(s.structuralRev).toBe(rev)
    expect(s.dirty).toBe(true)
  })

  it('connects, then refuses a cycle, a taken port, a wire into Input and a wire out of Output', async () => {
    const s = await loaded()
    s.addNode('highpass', 0, 0)
    s.addNode('lowpass', 0, 0)
    expect(s.connect({ source: 'input', target: 'highpass1', targetPort: 0 })).toBeNull()
    expect(s.connect({ source: 'highpass1', target: 'lowpass1', targetPort: 0 })).toBeNull()
    expect(s.connect({ source: 'lowpass1', target: 'highpass1', targetPort: 0 })).toMatch(/already has a wire|loop/)
    expect(s.connect({ source: 'lowpass1', target: 'highpass1', targetPort: 0 })).not.toBeNull()
    expect(s.connect({ source: 'input', target: 'lowpass1', targetPort: 0 })).toBe('that input already has a wire')
    expect(s.connect({ source: 'highpass1', target: 'input', targetPort: 0 })).toBe('the input node takes no wire')
    expect(s.connect({ source: 'output', target: 'lowpass1', targetPort: 0 })).not.toBeNull()
    expect(s.graph.edges).toHaveLength(2)
  })

  it('refuses a real loop with the loop reason', async () => {
    const s = await loaded()
    s.addNode('highpass', 0, 0)
    s.addNode('lowpass', 0, 0)
    s.connect({ source: 'highpass1', target: 'lowpass1', targetPort: 0 })
    expect(s.connect({ source: 'lowpass1', target: 'highpass1', targetPort: 0 })).toBe('this wire would make a loop')
  })

  it('refuses a missing Mix port and ids are unique across wires', async () => {
    const s = await loaded()
    s.addNode('mix2', 0, 0)
    expect(s.connect({ source: 'input', target: 'mix21', targetPort: 2 })).toBe('no such input port')
    expect(s.connect({ source: 'input', target: 'mix21', targetPort: 0 })).toBeNull()
    expect(s.connect({ source: 'input', target: 'mix21', targetPort: 1 })).toBeNull()
    const ids = s.graph.edges.map((e) => e.id)
    expect(new Set(ids).size).toBe(ids.length)
  })

  it('disconnects a wire and reports an unknown one', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    expect(s.disconnect('e1')).toBe(true)
    expect(s.disconnect('e1')).toBe(false)
    expect(s.valid).toBe(false)
  })

  it('stores a parameter only when it differs from init, clamped to the catalog range', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    const block = realCatalog.blocks.find((b) => b.id === 'highpass')!
    const c = block.controls.find((x) => x.label !== block.stomp)!
    expect(s.setParam('highpass1', c.label, c.max + 1000)).toBe(c.max)
    expect(s.nodeOf('highpass1')!.params![c.label]).toBe(c.max)
    expect(s.setParam('highpass1', c.label, c.min - 1000)).toBe(c.min)
    s.setParam('highpass1', c.label, c.init)
    expect(s.nodeOf('highpass1')!.params).toEqual({})
    expect(s.setParam('highpass1', 'No such knob', 1)).toBeNull()
  })

  it('announces knob and stomp changes live by key and does not bump the structure', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    const seen: Array<{ key: string; value: number }> = []
    const off = s.onLive((c) => seen.push(c))
    const rev = s.structuralRev
    const block = realCatalog.blocks.find((b) => b.id === 'highpass')!
    const c = block.controls.find((x) => x.label !== block.stomp)!
    s.setParam('highpass1', c.label, c.max)
    s.setOn('highpass1', false)
    expect(seen[0].key).toMatch(/^highpass1_/)
    expect(seen[0].value).toBe(c.max)
    expect(seen[1]).toEqual({ key: `highpass1_${block.stomp!.replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '')}`, value: 0 })
    expect(s.nodeOf('highpass1')!.on).toBe(false)
    expect(s.structuralRev).toBe(rev)
    off()
    s.setOn('highpass1', true)
    expect(seen).toHaveLength(2)
  })

  it('treats the stomp label as the on switch and ignores stomp on blocks without one', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    const stomp = realCatalog.blocks.find((b) => b.id === 'highpass')!.stomp!
    s.setParam('highpass1', stomp, 0)
    expect(s.nodeOf('highpass1')!.on).toBe(false)
    s.setOn('output', false)
    expect(s.nodeOf('output')!.on).toBeUndefined()
  })

  it('newGraph resets to Input and Output and clears dirty', async () => {
    const s = await loaded()
    s.addNode('highpass', 0, 0)
    s.newGraph()
    expect(s.graph.nodes.map((n) => n.id)).toEqual(['input', 'output'])
    expect(s.dirty).toBe(false)
  })

  it('a whole graph replacing the board bumps loadRev (so the canvas re-fits) but a single edit does not', async () => {
    const s = await loaded()
    const start = s.loadRev
    s.loadStarter('chain')
    expect(s.loadRev).toBe(start + 1)
    s.newGraph()
    expect(s.loadRev).toBe(start + 2)
    s.addNode('highpass', 10, 10)
    s.moveNode('input', 5, 5)
    expect(s.loadRev).toBe(start + 2)
  })

  it('loadStarter copies the graph and does not alias the starter', async () => {
    const s = await loaded()
    expect(s.loadStarter('chain')).toBe(true)
    expect(s.loadStarter('missing')).toBe(false)
    s.moveNode('highpass1', 99, 99)
    s.setParam('highpass1', realCatalog.blocks.find((b) => b.id === 'highpass')!.controls.find((c) => c.type === 'hslider')!.label, 1)
    expect(s.starters[0].graph.nodes[1]).toMatchObject({ x: 200 })
    expect(s.starters[0].graph.nodes[1].params).toBeUndefined()
    expect(s.dirty).toBe(true)
    expect(s.valid).toBe(true)
  })

  it('compiles a valid graph into code, controls and params', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    expect(s.compiled).not.toBeNull()
    expect(s.compiled!.code).toContain('vgroup("fx"')
    expect(s.compiled!.controls.some((c) => c.nodeId === 'highpass1')).toBe(true)
    expect(s.compiled!.params).toEqual(paramsFor(chainGraph(), realCatalog))
  })

  it('bumps the structure for add, remove, connect, disconnect and load only', async () => {
    const s = await loaded()
    let rev = s.structuralRev
    const bumped = () => { const r = s.structuralRev !== rev; rev = s.structuralRev; return r }
    s.addNode('highpass', 0, 0)
    expect(bumped()).toBe(true)
    s.connect({ source: 'input', target: 'highpass1', targetPort: 0 })
    expect(bumped()).toBe(true)
    s.connect({ source: 'input', target: 'highpass1', targetPort: 0 })
    expect(bumped()).toBe(false)
    s.disconnect('e1')
    expect(bumped()).toBe(true)
    s.loadGraph(chainGraph())
    expect(bumped()).toBe(true)
    s.removeNode('highpass1')
    expect(bumped()).toBe(true)
  })

  it('compileNow reads the knob values at call time', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    void s.compiled
    const c = realCatalog.blocks.find((b) => b.id === 'highpass')!.controls.find((x) => x.type === 'hslider')!
    s.setParam('highpass1', c.label, c.max)
    const key = s.compileNow()!.controls.find((x) => x.nodeId === 'highpass1' && x.label === c.label)!.key
    expect(s.compileNow()!.params[key]).toBe(c.max)
  })

  it('save posts the generated code and flat params, names the graph and clears dirty', async () => {
    const s = await loaded()
    s.loadGraph(chainGraph())
    s.moveNode('highpass1', 1, 1)
    vi.mocked(api.pedalboardSave).mockResolvedValue({ name: 'mine', dsp: 'presets/mine.dsp', saved: true })
    const res = await s.save(' mine ')
    expect(res?.name).toBe('mine')
    const body = vi.mocked(api.pedalboardSave).mock.calls[0][0]
    expect(body.graph.name).toBe('mine')
    expect(body.code).toBe(s.compiled!.code)
    expect(body.params).toEqual(paramsFor(body.graph, realCatalog))
    expect(s.dirty).toBe(false)
    expect(s.savedNames).toContain('mine')
  })

  it('save does nothing for an invalid graph or an empty name, and keeps the error from the server', async () => {
    const s = await loaded()
    expect(await s.save('x')).toBeNull()
    s.loadGraph(chainGraph())
    expect(await s.save('  ')).toBeNull()
    expect(api.pedalboardSave).not.toHaveBeenCalled()
    vi.mocked(api.pedalboardSave).mockRejectedValue(new Error('bad name'))
    expect(await s.save('x')).toBeNull()
    expect(s.error).toBe('bad name')
  })

  it('loadSaved fetches by name and sets the name', async () => {
    const s = await loaded()
    vi.mocked(api.pedalboardGraph).mockResolvedValue(chainGraph())
    expect(await s.loadSaved('alpha')).toBe(true)
    expect(s.graph.name).toBe('alpha')
    expect(s.dirty).toBe(false)
  })
})
