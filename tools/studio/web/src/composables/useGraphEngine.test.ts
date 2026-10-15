import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { CROSSFADE_S, keyOfAddress, useGraphEngine, type EngineControl, type FaustNodeLike } from './useGraphEngine'

class FakeParam {
  value = 0
  calls: [string, number, number?][] = []
  setValueAtTime(v: number, t: number) { this.calls.push(['set', v, t]) }
  linearRampToValueAtTime(v: number, t: number) { this.calls.push(['ramp', v, t]) }
}
class FakeNode {
  gain = new FakeParam()
  fftSize = 0
  smoothingTimeConstant = 0
  connected = new Set<unknown>()
  disconnectCalls = 0
  buffer: unknown = null
  loop = false
  started = false
  connect(d: unknown) { this.connected.add(d); return d }
  disconnect(d?: unknown) { this.disconnectCalls++; if (d) this.connected.delete(d); else this.connected.clear() }
  start() { this.started = true }
  stop() {}
}
class FakeBuffer {
  data: Float32Array
  constructor(public ch: number, public length: number, public sampleRate: number) { this.data = new Float32Array(length) }
  getChannelData() { return this.data }
}
function fakeCtx() {
  const nodes: FakeNode[] = []
  const mk = () => { const n = new FakeNode(); nodes.push(n); return n }
  return {
    nodes, currentTime: 1, destination: {}, sampleRate: 1000,
    createGain: mk, createAnalyser: mk, createChannelSplitter: mk, createBufferSource: mk,
    createBuffer: (c: number, l: number, sr: number) => new FakeBuffer(c, l, sr),
    decodeAudioData: vi.fn(async () => new FakeBuffer(1, 100, 1000)),
    resume: vi.fn(async () => {}),
  }
}

class FakeFaust implements FaustNodeLike {
  values = new Map<string, number>()
  connected = new Set<unknown>()
  disconnected = 0
  constructor(public descs: { address: string; type: string; label: string; init?: number; min?: number; max?: number }[]) {}
  getDescriptors() { return this.descs.map((d) => ({ ...d, shortname: 'WRONG' })) }
  setParamValue(a: string, v: number) { this.values.set(a, v) }
  connect(d: unknown) { this.connected.add(d); return d }
  disconnect() { this.disconnected++; this.connected.clear() }
}
const ring = (inst: string) => ({ address: `/fx/${inst}/Ring_Hz`, type: 'hslider', label: 'Ring Hz', init: 100, min: 10, max: 500 })
const stomp = { address: '/fx/n1/Mute', type: 'checkbox', label: 'Mute' }
const ctl = (key: string, over: Partial<EngineControl> = {}): EngineControl => ({ key, type: 'hslider', init: 100, min: 10, max: 500, step: 1, ...over })

function setup(nodes: FakeFaust[]) {
  const ctx = fakeCtx()
  let i = 0
  const makeNode = vi.fn(async () => nodes[i++] ?? null)
  const e = useGraphEngine({ ctx: ctx as unknown as AudioContext, makeNode })
  return { ctx, e, makeNode }
}

beforeEach(() => { vi.useFakeTimers() })
afterEach(() => { vi.useRealTimers() })

describe('keyOfAddress', () => {
  it('drops the root and keeps the instance', () => {
    expect(keyOfAddress('/fx/n1/Ring_Hz')).toBe('n1_Ring_Hz')
    expect(keyOfAddress('/fx/n2/Ring_Hz')).toBe('n2_Ring_Hz')
    expect(keyOfAddress('/fx/n1/Comb (ms)')).toBe('n1_Comb_ms')
  })
})

describe('compile', () => {
  it('names two instances of one label apart and applies init values', async () => {
    const f = new FakeFaust([ring('n1'), ring('n2')])
    const { e } = setup([f])
    await e.compile('code', [ctl('n1_Ring_Hz'), ctl('n2_Ring_Hz', { init: 200 })], {})
    expect(e.status.value).toBe('ready')
    expect(e.params).toEqual({ n1_Ring_Hz: 100, n2_Ring_Hz: 200 })
    expect(f.values.get('/fx/n2/Ring_Hz')).toBe(200)
  })

  it('connects the first node without a crossfade, after setting values', async () => {
    const f = new FakeFaust([ring('n1')])
    const { ctx, e } = setup([f])
    await e.compile('c', [ctl('n1_Ring_Hz')], { n1_Ring_Hz: 300 })
    expect(f.values.get('/fx/n1/Ring_Hz')).toBe(300)
    expect(f.connected.size).toBe(1)
    const g = [...f.connected][0] as FakeNode
    expect(g.gain.calls).toEqual([])
    expect(ctx.nodes).toContain(g)
  })

  it('carries live values over a swap unless params overrides them', async () => {
    const a = new FakeFaust([ring('n1')]), b = new FakeFaust([ring('n1')]), c = new FakeFaust([ring('n1')])
    const { e } = setup([a, b, c])
    await e.compile('c', [ctl('n1_Ring_Hz')], {})
    e.setParam('n1_Ring_Hz', 321)
    await e.compile('c2', [ctl('n1_Ring_Hz')], {})
    expect(b.values.get('/fx/n1/Ring_Hz')).toBe(321)
    expect(e.params.n1_Ring_Hz).toBe(321)
    await e.compile('c3', [ctl('n1_Ring_Hz')], { n1_Ring_Hz: 50 })
    expect(c.values.get('/fx/n1/Ring_Hz')).toBe(50)
  })

  it('crossfades and disconnects the old node after the ramp', async () => {
    const a = new FakeFaust([ring('n1')]), b = new FakeFaust([ring('n1')])
    const { e } = setup([a, b])
    await e.compile('c', [ctl('n1_Ring_Hz')], {})
    const oldGain = [...a.connected][0] as FakeNode
    await e.compile('c2', [ctl('n1_Ring_Hz')], {})
    const newGain = [...b.connected][0] as FakeNode
    expect(newGain.gain.calls).toEqual([['set', 0, 1], ['ramp', 1, 1 + CROSSFADE_S]])
    expect(oldGain.gain.calls).toEqual([['set', 1, 1], ['ramp', 0, 1 + CROSSFADE_S]])
    expect(a.disconnected).toBe(0)
    vi.advanceTimersByTime(CROSSFADE_S * 1000 + 100)
    expect(a.disconnected).toBe(1)
    expect(oldGain.disconnectCalls).toBe(1)
  })

  it('discards a stale compile that resolves after a newer one', async () => {
    const slow = new FakeFaust([ring('n1')]), fast = new FakeFaust([ring('n1')])
    const ctx = fakeCtx()
    let release!: (n: FaustNodeLike) => void
    const makeNode = vi.fn()
      .mockImplementationOnce(() => new Promise<FaustNodeLike>((r) => { release = r }))
      .mockImplementationOnce(async () => fast)
    const e = useGraphEngine({ ctx: ctx as unknown as AudioContext, makeNode })
    const p1 = e.compile('old', [ctl('n1_Ring_Hz')], {})
    await e.compile('new', [ctl('n1_Ring_Hz')], { n1_Ring_Hz: 77 })
    release(slow)
    await p1
    expect(slow.connected.size).toBe(0)
    expect(slow.disconnected).toBe(1)
    expect(slow.values.size).toBe(0)
    e.setParam('n1_Ring_Hz', 80)
    expect(fast.values.get('/fx/n1/Ring_Hz')).toBe(80)
    expect(e.status.value).toBe('ready')
  })

  it('on failure sets error status and keeps the old node', async () => {
    const a = new FakeFaust([ring('n1')])
    const ctx = fakeCtx()
    const makeNode = vi.fn().mockResolvedValueOnce(a).mockRejectedValueOnce(new Error('syntax error'))
    const e = useGraphEngine({ ctx: ctx as unknown as AudioContext, makeNode })
    await e.compile('ok', [ctl('n1_Ring_Hz')], {})
    await e.compile('bad', [ctl('n1_Ring_Hz')], {})
    expect(e.status.value).toBe('error')
    expect(e.error.value).toContain('syntax error')
    vi.advanceTimersByTime(1000)
    expect(a.disconnected).toBe(0)
    e.setParam('n1_Ring_Hz', 222)
    expect(a.values.get('/fx/n1/Ring_Hz')).toBe(222)
  })

  it('treats a null node as an error', async () => {
    const { e } = setup([])
    await e.compile('x', [], {})
    expect(e.status.value).toBe('error')
  })
})

describe('setParam', () => {
  it('clamps, ignores unknown keys, and drives stomps', async () => {
    const f = new FakeFaust([ring('n1'), stomp])
    const { e } = setup([f])
    await e.compile('c', [ctl('n1_Ring_Hz'), ctl('n1_Mute', { type: 'checkbox', init: 1, min: 0, max: 1, step: 1 })], {})
    e.setParam('n1_Ring_Hz', 9999)
    expect(f.values.get('/fx/n1/Ring_Hz')).toBe(500)
    expect(e.params.n1_Ring_Hz).toBe(500)
    e.setParam('nope', 3)
    expect(e.params.nope).toBeUndefined()
    expect(e.params.n1_Mute).toBe(1)
    e.setParam('n1_Mute', 0)
    expect(f.values.get('/fx/n1/Mute')).toBe(0)
  })
})

describe('transport', () => {
  it('toggles raw bypass gains', () => {
    const { ctx, e } = setup([])
    const [dry, wet] = ctx.nodes
    expect(dry.gain.value).toBe(0)
    e.setBypassRaw(true)
    expect([dry.gain.value, wet.gain.value]).toEqual([1, 0])
    expect(e.bypassRaw.value).toBe(true)
    e.setBypassRaw(false)
    expect([dry.gain.value, wet.gain.value]).toEqual([0, 1])
  })

  it('loops the clip with a gap, plays and stops', async () => {
    const f = new FakeFaust([ring('n1')])
    const { ctx, e } = setup([f])
    await e.compile('c', [ctl('n1_Ring_Hz')], {})
    await e.loadClip(new ArrayBuffer(8))
    e.setGap(0.5)
    e.play()
    expect(e.playing.value).toBe(true)
    const src = ctx.nodes[ctx.nodes.length - 1]
    expect(src.loop).toBe(true)
    expect(src.started).toBe(true)
    expect((src.buffer as FakeBuffer).length).toBe(100 + 500)
    expect(src.connected.has(f)).toBe(true)
    e.stop()
    expect(e.playing.value).toBe(false)
  })

  it('connects a running source to a newly compiled node', async () => {
    const a = new FakeFaust([ring('n1')]), b = new FakeFaust([ring('n1')])
    const { ctx, e } = setup([a, b])
    await e.compile('c', [ctl('n1_Ring_Hz')], {})
    await e.loadClip(new ArrayBuffer(8))
    e.play()
    const src = ctx.nodes[ctx.nodes.length - 1]
    await e.compile('c2', [ctl('n1_Ring_Hz')], {})
    expect(src.connected.has(b)).toBe(true)
    vi.advanceTimersByTime(1000)
    expect(src.connected.has(a)).toBe(false)
  })
})
