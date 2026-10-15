import { readFileSync, readdirSync } from 'node:fs'
import { resolve } from 'node:path'
import { describe, expect, it } from 'vitest'
import { readDemoData } from '../../demo/buildData'
import { validate } from '../pedalboard/graph'
import { generate } from '../pedalboard/generate'
import { createDemoApi, STORAGE_KEY, type KeyValueStore } from './demoApi'

const FX_LAB = resolve(__dirname, '../../../../fx_lab')
const data = readDemoData(FX_LAB)

class FakeStorage implements KeyValueStore {
  map = new Map<string, string>()
  getItem(k: string) { return this.map.get(k) ?? null }
  setItem(k: string, v: string) { this.map.set(k, v) }
}
const make = (storage: KeyValueStore | null = new FakeStorage()) => createDemoApi({ loadData: async () => data, storage })

describe('bundled data matches the real files', () => {
  it('serves blocks.lib and catalog.json verbatim', async () => {
    const b = await make().pedalboardBlocks()
    expect(b.lib).toBe(readFileSync(resolve(FX_LAB, 'faust/blocks.lib'), 'utf8'))
    expect(b.catalog).toEqual(JSON.parse(readFileSync(resolve(FX_LAB, 'faust/catalog.json'), 'utf8')))
    expect(b.catalog.blocks.length).toBeGreaterThan(10)
  })
  it('lists every starter file, 49 today, each a graph the validator accepts', async () => {
    const s = await make().pedalboardStarters()
    const files = readdirSync(resolve(FX_LAB, 'starters')).filter((f) => f.endsWith('.json'))
    expect(s).toHaveLength(files.length)
    expect(s).toHaveLength(49)
    for (const st of s) {
      expect(typeof st.slug).toBe('string')
      expect(typeof st.name).toBe('string')
      expect(typeof st.category).toBe('string')
      expect(validate(st.graph, data.catalog), st.slug).toEqual([])
      expect(generate(st.graph, data.catalog, data.lib), st.slug).toBeTruthy()
    }
  })
  it('orders categories like the server (Clean first)', async () => {
    const s = await make().pedalboardStarters()
    expect(s[0].category).toBe('Clean')
  })
})

describe('saved graphs', () => {
  const graph = { ...data.starters[0].graph, name: 'my-chain' }
  const body = { graph, code: 'process = _;', params: {} }

  it('round-trip through storage and survive a new api object over the same storage', async () => {
    const store = new FakeStorage()
    const res = await make(store).pedalboardSave(body)
    expect(res).toEqual({ name: 'my-chain', dsp: 'my-chain.dsp', saved: true })
    const again = make(store)
    expect((await again.pedalboardGraphs()).map((g) => g.name)).toEqual(['my-chain'])
    expect(await again.pedalboardGraph('my-chain')).toEqual(graph)
    expect(store.map.has(STORAGE_KEY)).toBe(true)
  })
  it('lists newest first', async () => {
    let t = 0
    const api = createDemoApi({ loadData: async () => data, storage: new FakeStorage(), now: () => new Date(2026, 9, 15, 12, 0, t++) })
    await api.pedalboardSave({ ...body, graph: { ...graph, name: 'a' } })
    await api.pedalboardSave({ ...body, graph: { ...graph, name: 'b' } })
    expect((await api.pedalboardGraphs()).map((g) => g.name)).toEqual(['b', 'a'])
  })
  it('rejects bad names and unknown graphs, and works with no storage at all', async () => {
    const api = make(null)
    await expect(api.pedalboardSave({ ...body, graph: { ...graph, name: '../x' } })).rejects.toThrow(/letters, digits/)
    await expect(api.pedalboardGraph('nope')).rejects.toThrow(/no saved graph/)
    await api.pedalboardSave(body)
    expect((await api.pedalboardGraphs()).map((g) => g.name)).toEqual(['my-chain'])
  })
  it('survives corrupt stored text', async () => {
    const store = new FakeStorage()
    store.setItem(STORAGE_KEY, '{not json')
    expect(await make(store).pedalboardGraphs()).toEqual([])
  })
})
