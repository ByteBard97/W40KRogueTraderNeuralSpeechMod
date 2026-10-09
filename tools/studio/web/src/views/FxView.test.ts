import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { api } from '../api/client'

const bridge = vi.hoisted(() => ({ sendClip: vi.fn(), onPresetSaved: null as null | ((n: string) => void) }))
vi.mock('../composables/useFxBridge', () => ({
  fxLabUrl: () => 'http://127.0.0.1:8908/',
  useFxBridge: (o: { onPresetSaved: (n: string) => void }) => { bridge.onPresetSaved = o.onPresetSaved; return { sendClip: bridge.sendClip } },
}))
vi.mock('../api/client', () => ({ api: { fxLibrary: vi.fn(), fxLabels: vi.fn(), fxSaveLabels: vi.fn(), fxPreview: vi.fn(), fxWrite: vi.fn() } }))

import FxView from './FxView.vue'

async function mountAt(url: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/fx', component: FxView }] })
  router.push(url)
  await router.isReady()
  return mount(FxView, { global: { plugins: [router] } })
}

describe('FxView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.fxLibrary).mockResolvedValue([{ name: 'Clean', source: 'scenario', dsp: 'chain.dsp', notes: '' }])
    vi.mocked(api.fxLabels).mockResolvedValue({})
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ arrayBuffer: async () => new ArrayBuffer(8) }))
  })

  it('shows the library and embeds the FX Lab', async () => {
    const w = await mountAt('/fx')
    await flushPromises()
    expect(w.text()).toContain('Clean')
    expect(w.find('iframe').attributes('src')).toBe('http://127.0.0.1:8908/')
  })

  it('sends the requested take to the FX Lab once the iframe has loaded', async () => {
    const w = await mountAt('/fx?clip=data/studio/pasqal/raw/t1.wav')
    await flushPromises()
    expect(bridge.sendClip).not.toHaveBeenCalled()
    await w.find('iframe').trigger('load')
    await flushPromises()
    expect(fetch).toHaveBeenCalledWith('/file?p=data%2Fstudio%2Fpasqal%2Fraw%2Ft1.wav')
    expect(bridge.sendClip).toHaveBeenCalledWith('t1.wav', expect.any(ArrayBuffer))
  })

  it('does not send anything without a clip, and says so when the clip cannot be fetched', async () => {
    const w = await mountAt('/fx')
    await w.find('iframe').trigger('load')
    expect(bridge.sendClip).not.toHaveBeenCalled()
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('net')))
    const w2 = await mountAt('/fx?clip=data/x.wav')
    await w2.find('iframe').trigger('load')
    await flushPromises()
    expect(w2.text()).toContain('Could not load that clip')
  })

  it('reloads the library and tells the user when a preset is saved in the FX Lab', async () => {
    const w = await mountAt('/fx')
    await flushPromises()
    vi.mocked(api.fxLibrary).mockResolvedValue([{ name: 'Clean', source: 'scenario', dsp: 'chain.dsp', notes: '' }, { name: 'Servitor', source: 'saved', dsp: 'chain.dsp', notes: '' }])
    await bridge.onPresetSaved!('Servitor')
    await flushPromises()
    expect(w.text()).toContain('Saved preset “Servitor”')
    expect(w.text()).toContain('Servitor')
  })
})
