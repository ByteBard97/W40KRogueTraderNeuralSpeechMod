import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { chainGraph, realCatalog } from '../test-utils/pedalboardCatalog'
import { usePedalboardStore } from '../stores/pedalboard'
import { installPedalboardQaHook, qaEnabled, syntheticSpeech } from './pedalboardQaHook'

function fakeEngine() {
  const buffers: unknown[] = []
  const ctx = { sampleRate: 8000, createBuffer: (_c: number, n: number) => { const d = new Float32Array(n); return { length: n, getChannelData: () => d } } }
  const engine = {
    status: ref('ready'), error: ref(''), playing: ref(false), params: { n1_Gain: 3 } as Record<string, number>,
    compile: vi.fn(async () => {}), loadClip: vi.fn(async (b: unknown) => { buffers.push(b) }),
    taps: { mid: { context: ctx } },
  }
  return { engine: engine as never, raw: engine, buffers }
}

describe('pedalboard QA hook', () => {
  let off = () => {}
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => { off(); off = () => {} })

  it('is absent unless dev or ?qa', () => {
    expect(qaEnabled(false, '')).toBe(false)
    expect(qaEnabled(false, '?x=1')).toBe(false)
    expect(qaEnabled(false, '?qa')).toBe(true)
    expect(qaEnabled(true, '')).toBe(true)
    const store = usePedalboardStore()
    off = installPedalboardQaHook({ store, engine: fakeEngine().engine, enabled: false })
    expect(window.__pedalboard).toBeUndefined()
  })

  it('exposes read-only getters', () => {
    const store = usePedalboardStore()
    store.catalog = realCatalog
    store.loadGraph(chainGraph())
    const { engine } = fakeEngine()
    off = installPedalboardQaHook({ store, engine, enabled: true })
    const qa = window.__pedalboard!
    expect(qa.graph()).toMatchObject({ nodes: expect.any(Array) })
    expect(qa.engineStatus()).toEqual({ status: 'ready', error: '' })
    expect(qa.paramValue('n1_Gain')).toBe(3)
    expect(qa.selection()).toEqual([])
    expect(qa.monitor()).toEqual({ corr: null, sideMidDb: null, balanceDb: null, bands: [], samples: 0 })
    expect(() => JSON.stringify(qa.compiled())).not.toThrow()
  })

  it('counts non-empty compileNow results and leaves the engine alone; uninstall restores', () => {
    const store = usePedalboardStore()
    store.catalog = realCatalog
    const { engine, raw } = fakeEngine()
    const original = raw.compile
    const realNow = store.compileNow
    off = installPedalboardQaHook({ store, engine, enabled: true })
    expect(raw.compile).toBe(original)
    expect(store.compileNow()).toBeNull()                 // empty graph: nothing to compile
    expect(window.__pedalboard!.compileCount()).toBe(0)
    store.loadGraph(chainGraph())
    expect(store.compileNow()).not.toBeNull()
    expect(window.__pedalboard!.compileCount()).toBe(1)
    off()
    expect(store.compileNow).toBe(realNow)
    expect(window.__pedalboard).toBeUndefined()
  })

  it('loads a synthetic clip and a starter by slug', async () => {
    const store = usePedalboardStore()
    store.starters = [{ slug: 's', name: 'S', description: '', category: 'Test', graph: chainGraph() }] as never
    const { engine, buffers } = fakeEngine()
    off = installPedalboardQaHook({ store, engine, enabled: true })
    await window.__pedalboard!.loadSyntheticClip(0.5)
    expect(buffers).toHaveLength(1)
    expect((buffers[0] as { length: number }).length).toBe(4000)
    expect(window.__pedalboard!.loadStarterBySlug('s')).toBe(true)
    expect(window.__pedalboard!.loadStarterBySlug('nope')).toBe(false)
  })

  it('synthetic speech is deterministic, bounded and not silent', () => {
    const a = syntheticSpeech(1, 8000)
    expect(a).toEqual(syntheticSpeech(1, 8000))
    expect(Math.max(...a.map(Math.abs))).toBeLessThanOrEqual(1)
    expect(a.some((v) => Math.abs(v) > 0.05)).toBe(true)
  })
})
