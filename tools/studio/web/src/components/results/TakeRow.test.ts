import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { routerKey } from 'vue-router'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))
vi.mock('../../api/client', () => ({ api: { takeRate: vi.fn(), takeFx: vi.fn() } }))

import TakeRow from './TakeRow.vue'

const take = (over = {}) => ({
  id: 't1', raw: 'data/raw.wav', text: 'Hi.', guid: 'g1', reference: 'data/voices/wav/Pasqal/E1.wav',
  options: { cfg: 2, timesteps: 10 }, instruct: null, seed: 55, seconds: 3.2, audio_s: 2.5, rating: 0, note: '', fx: null, ...over,
})
const line = { guid: 'g1', baseline: 'data/render/export/wav/g1.wav' }

function mountRow(t = take(), fxChosen: string[] = []) {
  const ctx = { slug: 'pasqal', fxChosen: ref(fxChosen), upsertTake: vi.fn() }
  return { ctx, w: mount(TakeRow, { props: { take: t as never, line: line as never }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('TakeRow', () => {
  beforeEach(() => vi.clearAllMocks())

  it('offers bank, raw and fx clips and shows seed and source', () => {
    const { w } = mountRow(take({ fx: { presets: ['Clean'], wav: 'data/studio/pasqal/fx/t1.wav', v: 9 } }))
    expect(w.text()).toContain('seed 55')
    expect(w.text()).toContain('E1')
    const labels = w.findAll('.clip').map((b) => b.text())
    expect(labels).toEqual(expect.arrayContaining(['source clip', 'bank', 'raw clone', 'fx']))
  })

  it('re-apply with an empty picker repeats the take\'s own presets instead of clearing the FX', async () => {
    vi.mocked(api.takeFx).mockResolvedValue(take() as never)
    const { w } = mountRow(take({ fx: { presets: ['Servitor', 'Clean'], wav: 'data/studio/pasqal/fx/t1.wav', v: 9 } }), [])
    expect(w.find('[data-fx]').attributes('disabled')).toBeUndefined()
    await w.find('[data-fx]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', ['Servitor', 'Clean'])
  })

  it('rates a take through the api and updates the context', async () => {
    vi.mocked(api.takeRate).mockResolvedValue(take({ rating: 4 }) as never)
    const { ctx, w } = mountRow()
    await w.findAll('.star')[3].trigger('click')
    await flushPromises()
    expect(api.takeRate).toHaveBeenCalledWith('pasqal', 't1', { rating: 4 })
    expect(ctx.upsertTake).toHaveBeenCalled()
  })

  it('applies FX with the chosen presets and shows an error from the server', async () => {
    vi.mocked(api.takeFx).mockRejectedValue(new Error('tools/fx_lab/.venv-fx is missing'))
    const { w } = mountRow(take(), ['Clean'])
    await w.find('[data-fx]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', ['Clean'])
    expect(w.text()).toContain('.venv-fx is missing')
  })

  it('disables apply when no preset is chosen and the take has no fx', () => {
    const { w } = mountRow()
    expect(w.find('[data-fx]').attributes('disabled')).toBeDefined()
  })

  it('has a clear-FX button only when the take has FX, and it sends an empty list', async () => {
    vi.mocked(api.takeFx).mockResolvedValue(take() as never)
    expect(mountRow(take()).w.find('[data-clear-fx]').exists()).toBe(false)
    const { w } = mountRow(take({ fx: { presets: ['Clean'], wav: 'data/studio/pasqal/fx/t1.wav', v: 9 } }))
    await w.find('[data-clear-fx]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', [])
  })

  it('opens the take in the FX Lab with its raw path in the query', async () => {
    const push = vi.fn()
    const ctx = { slug: 'pasqal', fxChosen: ref<string[]>([]), upsertTake: vi.fn() }
    const w = mount(TakeRow, { props: { take: take() as never, line: line as never }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx, [routerKey as symbol]: { push } } } })
    await w.find('[data-open-fx]').trigger('click')
    expect(push).toHaveBeenCalledWith({ path: '/fx', query: { clip: 'data/raw.wav' } })
  })
})
