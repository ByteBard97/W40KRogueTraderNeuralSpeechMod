import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { defineComponent, nextTick } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useToasts } from '../composables/useToasts'
import { chainGraph, realCatalog, realLib } from '../test-utils/pedalboardCatalog'
import { usePedalboardStore } from '../stores/pedalboard'

const engine = vi.hoisted(() => ({
  status: { value: 'idle' }, error: { value: '' }, playing: { value: false }, bypassRaw: { value: false }, params: {}, taps: {},
  compile: vi.fn(), setParam: vi.fn(), loadClip: vi.fn(), play: vi.fn(), stop: vi.fn(), setBypassRaw: vi.fn(), setGap: vi.fn(), dispose: vi.fn(),
}))
vi.mock('../composables/useGraphEngine', () => ({ useGraphEngine: () => engine }))
vi.mock('../api/referenceApi', () => ({ refSpeakers: vi.fn().mockResolvedValue([{ speaker: 'Pasqal', clips: 3 }]), refLtas: vi.fn().mockResolvedValue({ speaker: 'Pasqal', freqs: [], db: [], clips_used: 1, stereo: null }) }))
vi.mock('../api/client', () => ({
  api: { pedalboardBlocks: vi.fn(), pedalboardGraphs: vi.fn(), pedalboardGraph: vi.fn(), pedalboardSave: vi.fn(), pedalboardStarters: vi.fn() },
}))

import PedalboardView from './PedalboardView.vue'

const TransportStub = defineComponent({ template: '<div data-testid="transport-stub" />', emits: ['play', 'stop', 'bypass', 'gap', 'reference', 'load-clip'] })
const stubs = {
  PedalboardCanvas: { template: '<div data-testid="canvas-stub" />', methods: { addAtCenter: vi.fn() } },
  MonitorPanel: true,
  TransportBar: TransportStub,
}

const mounted: Array<{ unmount: () => void }> = []

async function mountView() {
  const w = mount(PedalboardView, { global: { stubs }, attachTo: document.body })
  mounted.push(w)
  await flushPromises()
  return w
}
const DEBOUNCE = 300

describe('PedalboardView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useToasts().clear()
    vi.useFakeTimers()
    engine.playing.value = false
    vi.mocked(api.pedalboardBlocks).mockResolvedValue({ lib: realLib, catalog: realCatalog })
    vi.mocked(api.pedalboardGraphs).mockResolvedValue([])
    vi.mocked(api.pedalboardStarters).mockResolvedValue([])
  })
  afterEach(() => {
    // Unmount even when a test failed halfway, so window listeners do not leak into the next test.
    mounted.splice(0).forEach((w) => { try { w.unmount() } catch { /* already unmounted */ } })
    vi.useRealTimers()
    vi.unstubAllGlobals()
  })

  it('compiles once after the debounce when a node is added to a valid graph', async () => {
    const w = await mountView()
    const store = usePedalboardStore()
    store.loadGraph(chainGraph())
    await nextTick()
    vi.advanceTimersByTime(DEBOUNCE - 1)
    expect(engine.compile).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(engine.compile).toHaveBeenCalledTimes(1)
    engine.compile.mockClear()
    store.addNode('lowpass', 0, 0)
    store.connect({ source: 'highpass1', target: 'lowpass1', targetPort: 0 })
    store.disconnect('e2')
    store.connect({ source: 'lowpass1', target: 'output', targetPort: 0 })
    await nextTick()
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(engine.compile).toHaveBeenCalledTimes(1)
  })

  it('does not compile while the graph is invalid', async () => {
    const w = await mountView()
    usePedalboardStore().addNode('highpass', 0, 0)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(engine.compile).not.toHaveBeenCalled()
  })

  it('sends the program, controls and current params to the engine', async () => {
    const w = await mountView()
    const store = usePedalboardStore()
    store.loadGraph(chainGraph())
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    const [code, controls, params] = engine.compile.mock.calls[0]
    expect(code).toContain('vgroup("fx"')
    expect(controls.length).toBeGreaterThan(0)
    expect(Object.keys(params)).toContain('highpass1_Highpass_on')
  })

  it('a knob turn calls setParam by key and never compiles', async () => {
    const w = await mountView()
    const store = usePedalboardStore()
    store.loadGraph(chainGraph())
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    engine.compile.mockClear()
    const c = realCatalog.blocks.find((b) => b.id === 'highpass')!.controls.find((x) => x.type === 'hslider')!
    store.setParam('highpass1', c.label, c.max)
    await vi.advanceTimersByTimeAsync(DEBOUNCE * 2)
    expect(engine.setParam).toHaveBeenCalledTimes(1)
    expect(engine.setParam.mock.calls[0][1]).toBe(c.max)
    expect(engine.setParam.mock.calls[0][0]).toMatch(/^highpass1_/)
    expect(engine.compile).not.toHaveBeenCalled()
  })

  it('a stomp toggle calls setParam with the stomp key and no compile', async () => {
    const w = await mountView()
    const store = usePedalboardStore()
    store.loadGraph(chainGraph())
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    engine.compile.mockClear()
    store.setOn('highpass1', false)
    await vi.advanceTimersByTimeAsync(DEBOUNCE * 2)
    expect(engine.setParam).toHaveBeenCalledWith('highpass1_Highpass_on', 0)
    expect(engine.compile).not.toHaveBeenCalled()
  })

  it('Space toggles play unless a text field has focus', async () => {
    const w = await mountView()
    window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ' }))
    expect(engine.play).toHaveBeenCalledTimes(1)
    engine.playing.value = true
    window.dispatchEvent(new KeyboardEvent('keydown', { key: ' ' }))
    expect(engine.stop).toHaveBeenCalledTimes(1)
    engine.play.mockClear()
    const field = w.get('[data-testid="name-input"]').element
    field.dispatchEvent(new KeyboardEvent('keydown', { key: ' ', bubbles: true }))
    expect(engine.play).not.toHaveBeenCalled()
  })

  it('forwards transport events to the engine and loads the reference', async () => {
    const w = await mountView()
    const t = w.findComponent(TransportStub)
    t.vm.$emit('play')
    t.vm.$emit('stop')
    t.vm.$emit('bypass', true)
    t.vm.$emit('gap', 0.5)
    t.vm.$emit('reference', 'Pasqal')
    await flushPromises()
    expect(engine.play).toHaveBeenCalled()
    expect(engine.stop).toHaveBeenCalled()
    expect(engine.setBypassRaw).toHaveBeenCalledWith(true)
    expect(engine.setGap).toHaveBeenCalledWith(0.5)
    const { refLtas } = await import('../api/referenceApi')
    expect(refLtas).toHaveBeenCalledWith('Pasqal')
  })

  it('fetches the clip and hands the bytes to the engine', async () => {
    const bytes = new ArrayBuffer(4)
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, arrayBuffer: () => Promise.resolve(bytes) }))
    const w = await mountView()
    w.findComponent(TransportStub).vm.$emit('load-clip', '/file/x.wav')
    await flushPromises()
    expect(engine.loadClip).toHaveBeenCalledWith(bytes)
  })

  it('saves through the store and tells the owner', async () => {
    const w = await mountView()
    const store = usePedalboardStore()
    store.loadGraph(chainGraph())
    vi.mocked(api.pedalboardSave).mockResolvedValue({ name: 'tin', dsp: 'presets/tin.dsp', saved: true })
    await w.get('[data-testid="name-input"]').setValue('tin')
    await w.get('form').trigger('submit')
    await flushPromises()
    expect(api.pedalboardSave).toHaveBeenCalledTimes(1)
    expect(useToasts().toasts.value.some((t) => t.message.includes('tin'))).toBe(true)
  })

  it('disposes the engine and stops listening on unmount', async () => {
    const w = await mountView()
    w.unmount()
    mounted.pop()
    expect(engine.dispose).toHaveBeenCalled()
    usePedalboardStore().loadGraph(chainGraph())
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(engine.compile).not.toHaveBeenCalled()
  })
})
