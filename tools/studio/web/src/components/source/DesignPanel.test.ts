import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { useModelStore } from '../../stores/model'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const play = vi.hoisted(() => vi.fn())
vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play, playing: null }) }))
vi.mock('../../api/client', () => ({
  api: { designGenerate: vi.fn(), designKeep: vi.fn(), designVerdict: vi.fn(), designOrder: vi.fn(), designDescription: vi.fn() },
}))

import DesignPanel from './DesignPanel.vue'

const design = { description: 'A calm woman.', text: 'Sample.', order: [], pick: null, candidates: [], clones: [] }
function mountPanel() {
  const ctx = { slug: 'muaran', detail: ref({ design }), load: vi.fn(), refreshDetail: vi.fn() }
  return { ctx, w: mount(DesignPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('DesignPanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('disables Generate with a reason while the model is down', () => {
    const { w } = mountPanel()
    const btn = w.find('[data-generate]')
    expect(btn.attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/not running/i)
  })

  it('generates a take, lists it, reuses its seed, and keeps it', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.designGenerate).mockResolvedValue({ file: 'live_tmp/t1.wav', seed: 4242, cfg: 2, timesteps: 10, seconds: 4.1, description: 'A calm woman.', text: 'Sample.' })
    vi.mocked(api.designKeep).mockResolvedValue({ cand: 'c6.wav' })
    const { ctx, w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.designGenerate).mock.calls[0][0]).toBe('muaran')
    expect(w.text()).toContain('4242')
    await w.find('[data-seed-chip]').trigger('click')
    expect((w.find('input[data-seed]').element as HTMLInputElement).value).toBe('4242')
    await w.find('[data-keep]').trigger('click')
    await flushPromises()
    expect(api.designKeep).toHaveBeenCalledWith('muaran', expect.objectContaining({ file: 'live_tmp/t1.wav', seed: 4242 }))
    expect(ctx.refreshDetail).toHaveBeenCalled()
    expect(ctx.load).not.toHaveBeenCalled()      // load() would reset the ticked sources and unsaved options
  })

  it('shows the error and keeps earlier takes when generation fails', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.designGenerate).mockRejectedValue(new Error('model backend is not running'))
    const { w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('model backend is not running')
  })

  it('saves the description on blur only when it changed and is not empty', async () => {
    vi.mocked(api.designDescription).mockClear()
    const { w } = mountPanel()
    const ta = w.find('textarea')
    await ta.trigger('blur')
    expect(api.designDescription).not.toHaveBeenCalled()
    await ta.setValue('   ')
    await ta.trigger('blur')
    expect(api.designDescription).not.toHaveBeenCalled()
    await ta.setValue('A gruff man.')
    await ta.trigger('blur')
    expect(api.designDescription).toHaveBeenCalledWith('muaran', 'A gruff man.')
  })

  it('shows the error when a verdict, keep or reorder call fails', async () => {
    vi.mocked(api.designOrder).mockRejectedValue(new Error('audit.json is not valid JSON'))
    const { w } = mountPanel()
    await (w.findComponent({ name: 'CandidateRanker' }).vm as unknown as { $emit: (e: string, o: string[]) => void }).$emit('reorder', ['c1.wav'])
    await flushPromises()
    expect(w.text()).toContain('audit.json is not valid JSON')
  })

  it('keeps a take once even when Keep is clicked twice quickly', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.designKeep).mockClear()
    vi.mocked(api.designGenerate).mockResolvedValue({ file: 'live_tmp/t2.wav', seed: 1, cfg: 2, timesteps: 10, seconds: 1, description: 'd', text: 't' })
    vi.mocked(api.designKeep).mockImplementation(() => new Promise((r) => setTimeout(() => r({ cand: 'c7.wav' }), 20)))
    const { w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    await w.find('[data-keep]').trigger('click')
    await w.find('[data-keep]').trigger('click')
    await new Promise((r) => setTimeout(r, 40))
    expect(api.designKeep).toHaveBeenCalledTimes(1)
  })

  it('plays a new take as soon as it is generated', async () => {
    useModelStore().state = 'ready'
    play.mockClear()
    vi.mocked(api.designGenerate).mockResolvedValue({ file: 'live_tmp/t5.wav', seed: 5, cfg: 2, timesteps: 10, seconds: 1, description: 'd', text: 't' })
    const { w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(play).toHaveBeenCalledWith('data/voice_design/live_tmp/t5.wav')
  })

  it('keeps unkept takes when the panel is remounted for the same speaker (navigating away and back)', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.designGenerate).mockResolvedValue({ file: 'live_tmp/t6.wav', seed: 6666, cfg: 2, timesteps: 10, seconds: 1, description: 'd', text: 't' })
    const first = mountPanel()
    await first.w.find('[data-generate]').trigger('click')
    await flushPromises()
    first.w.unmount()
    const again = mountPanel()
    expect(again.w.text()).toContain('6666')
  })
})
