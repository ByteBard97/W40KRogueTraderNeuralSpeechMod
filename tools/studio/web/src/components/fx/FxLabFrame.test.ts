import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const bridge = vi.hoisted(() => ({ sendClip: vi.fn(), onPresetSaved: null as null | ((n: string) => void) }))
vi.mock('../../composables/useFxBridge', () => ({
  FX_LAB_PORT: 8908,
  fxLabUrl: () => 'http://127.0.0.1:8908/',
  useFxBridge: (o: { onPresetSaved: (n: string) => void }) => { bridge.onPresetSaved = o.onPresetSaved; return { sendClip: bridge.sendClip } },
}))
import FxLabFrame from './FxLabFrame.vue'

const fetchMock = (probe: 'up' | 'down', clipOk = true) =>
  vi.fn((url: string) => {
    if (url.startsWith('http://127.0.0.1:8908')) return probe === 'up' ? Promise.resolve({}) : Promise.reject(new Error('refused'))
    return clipOk ? Promise.resolve({ ok: true, arrayBuffer: async () => new ArrayBuffer(8) }) : Promise.reject(new Error('net'))
  })

describe('FxLabFrame', () => {
  beforeEach(() => vi.clearAllMocks())

  it('embeds the FX Lab when the server answers', async () => {
    vi.stubGlobal('fetch', fetchMock('up'))
    const w = mount(FxLabFrame)
    await flushPromises()
    expect(w.find('iframe').attributes('src')).toBe('http://127.0.0.1:8908/')
    expect(w.text()).toContain('connected')
  })

  it('shows the start command and a Retry when it is down, and no iframe', async () => {
    vi.stubGlobal('fetch', fetchMock('down'))
    const w = mount(FxLabFrame)
    await flushPromises()
    expect(w.find('iframe').exists()).toBe(false)
    expect(w.text()).toContain('python3 tools/fx_lab/server.py')
    expect(w.text()).toContain('not reachable on :8908')
  })

  it('sends the requested clip once the iframe has loaded, and reports an unfetchable clip', async () => {
    vi.stubGlobal('fetch', fetchMock('up'))
    const w = mount(FxLabFrame, { props: { clip: 'data/studio/pasqal/raw/t1.wav' } })
    await flushPromises()
    expect(bridge.sendClip).not.toHaveBeenCalled()
    await w.find('iframe').trigger('load')
    await flushPromises()
    expect(bridge.sendClip).toHaveBeenCalledWith('t1.wav', expect.any(ArrayBuffer))
    vi.stubGlobal('fetch', fetchMock('up', false))
    const w2 = mount(FxLabFrame, { props: { clip: 'data/x.wav' } })
    await flushPromises()
    await w2.find('iframe').trigger('load')
    await flushPromises()
    expect(w2.emitted('notice')![0][0]).toContain('Could not load that clip')
  })

  it('forwards a preset saved in the lab, and collapses', async () => {
    vi.stubGlobal('fetch', fetchMock('up'))
    const w = mount(FxLabFrame)
    await flushPromises()
    bridge.onPresetSaved!('Servitor')
    expect(w.emitted('presetSaved')![0]).toEqual(['Servitor'])
    await w.find('[aria-label="Collapse FX Lab"]').trigger('click')
    expect(w.find('.body').attributes('style')).toContain('display: none')
  })
})
