import { flushPromises, mount } from '@vue/test-utils'
import { ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { lineOf, makeCtx, takeOf, withCtx } from '../../test-utils/speakerCtx'
import { useGlobalAudio } from '../../composables/globalAudio'
import { useToasts } from '../../composables/useToasts'

const api = vi.hoisted(() => ({ takeFx: vi.fn(), takeRate: vi.fn() }))
vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api }))
const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
import TakeRow from './TakeRow.vue'

const withFx = takeOf('t1', { fx: { presets: ['Clean'], wav: 'data/fx/t1.wav', v: 3, dur: 3.4 } })
const mk = (take = takeOf('t1'), ctxOver: Record<string, unknown> = {}, line: ReturnType<typeof lineOf> | null = lineOf('g1', { baseline: 'data/b/g1.wav', dur: 2.9 })) => {
  const ctx = makeCtx(ctxOver)
  return { ctx, w: mount(TakeRow, { attachTo: document.body, props: { take, line }, ...withCtx(ctx) }) }
}
const btn = (w: ReturnType<typeof mk>['w'], label: string) => w.findAll('button').find((b) => b.text().includes(label))!

describe('TakeRow', () => {
  beforeEach(() => { vi.clearAllMocks(); useToasts().clear(); useGlobalAudio().stop() })

  it('offers Real (never available), Bank, Clone and + FX with their durations', () => {
    const { w } = mk(withFx)
    const slots = w.findAll('.ab button')
    expect(slots.map((b) => b.find('b').text())).toEqual(['Real', 'Bank', 'Clone', '+ FX'])
    expect(slots[0].attributes('disabled')).toBeDefined()
    expect(slots[1].text()).toContain('2.9 s')
    expect(slots[2].text()).toContain('3.1 s')
    expect(slots[3].text()).toContain('3.4 s')
    expect(w.text()).toContain('E1 · seed 5 · cfg 2 · 10 steps')
  })

  it('disables Bank and + FX when there is no such clip', () => {
    const { w } = mk(takeOf('t1'), {}, null)
    const slots = w.findAll('.ab button')
    expect(slots[1].attributes('disabled')).toBeDefined()
    expect(slots[3].attributes('disabled')).toBeDefined()
  })

  it('plays a version through the global player and keeps the playhead when switching', async () => {
    const audio = useGlobalAudio()
    const { w } = mk(withFx)
    await w.findAll('.ab button')[2].trigger('click')
    expect(audio.state.id).toBe('data/t/t1.wav')
    await w.findAll('.ab button')[3].trigger('click')
    expect(audio.state.id).toBe('data/fx/t1.wav?v=3')
    expect(w.findAll('.ab button')[3].attributes('aria-pressed')).toBe('true')
  })

  it('rates through the api, updates the context and shows Saved; digit keys rate the focused take', async () => {
    api.takeRate.mockResolvedValue(takeOf('t1', { rating: 4 }))
    const { ctx, w } = mk()
    expect(w.text()).toContain('Not rated · 1–5')
    await w.find('[aria-label="Take rating 4"]').trigger('click')
    await flushPromises()
    expect(api.takeRate).toHaveBeenCalledWith('ruoldo', 't1', { rating: 4 })
    expect(ctx.upsertTake).toHaveBeenCalled()
    await w.find('.take').trigger('keydown', { key: '2' })
    expect(api.takeRate).toHaveBeenLastCalledWith('ruoldo', 't1', { rating: 2 })
  })

  it('applies the chosen FX, and shows the server error with a retry', async () => {
    api.takeFx.mockRejectedValueOnce(new Error('fx env missing')).mockResolvedValue(withFx)
    const { w } = mk(takeOf('t1'), { fxChosen: ref(['Clean']) })
    await btn(w, 'Apply FX').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('ruoldo', 't1', ['Clean'])
    const toast = useToasts().toasts.value[0]
    expect(toast.message).toBe('fx env missing')
    toast.action?.run()
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledTimes(2)
  })

  it('disables Apply with nothing chosen and no FX on the take; re-apply repeats the take\'s own presets; Clear sends none', async () => {
    api.takeFx.mockResolvedValue(withFx)
    expect(btn(mk().w, 'Apply FX').attributes('disabled')).toBeDefined()
    const { w } = mk(withFx)
    await btn(w, 'Re-apply FX').trigger('click')
    expect(api.takeFx).toHaveBeenLastCalledWith('ruoldo', 't1', ['Clean'])
    await btn(w, 'Clear FX').trigger('click')
    expect(api.takeFx).toHaveBeenLastCalledWith('ruoldo', 't1', [])
  })

  it('opens the take in the FX Lab with its raw path', async () => {
    const { w } = mk()
    await btn(w, 'Open in FX Lab').trigger('click')
    expect(push).toHaveBeenCalledWith({ path: '/fx', query: { clip: 'data/t/t1.wav' } })
  })
})
