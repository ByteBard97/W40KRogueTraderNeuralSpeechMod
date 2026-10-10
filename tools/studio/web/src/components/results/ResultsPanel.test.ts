import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { lineOf, makeCtx, takeOf, withCtx } from '../../test-utils/speakerCtx'
import { useModelStore } from '../../stores/model'
import { useWorkbenchJobsStore } from '../../stores/workbenchJobs'
import { useToasts } from '../../composables/useToasts'

const api = vi.hoisted(() => ({ cloneGenerate: vi.fn(), takeFx: vi.fn(), takeRate: vi.fn(), jobSubmit: vi.fn(), jobsActive: vi.fn(), job: vi.fn(), jobCancel: vi.fn() }))
vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
import { ApiRequestError } from '../../api/client'
import ResultsPanel from './ResultsPanel.vue'

const src2 = { key: 'real:E1', label: 'E1', wav: 'data/v/E1.wav', text: 'Hello.', origin: 'real' }
const src1 = { key: 'cand:c2.wav', label: 'candidate c2', wav: 'data/vd/c2.wav', text: 'Sample.', origin: 'designed' }
const mk = (over: Record<string, unknown> = {}) => {
  const ctx = makeCtx({ chosenSources: computed(() => [src1]), ...over })
  return { ctx, w: mount(ResultsPanel, { attachTo: document.body, ...withCtx(ctx) }) }
}
const job = (over: Record<string, unknown> = {}) => ({ id: 'j1', kind: 'clone', slug: 'ruoldo', label: 'Generating', state: 'running', total: 4, done: 1, index: 2, items: [], takes: [], fx: [], error: null, elapsed_s: 6, expected_s: 10, current: { n: 1, text: 'Oh! Yes! Yes, of course, this very day', seed: 1, cfg: 2, timesteps: 10, elapsed_s: 6, expected_s: 10 }, ...over })
const errors = () => useToasts().toasts.value.filter((t) => t.kind === 'err').map((t) => t.message)

describe('ResultsPanel', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); useToasts().clear(); api.jobsActive.mockResolvedValue([]) })

  it('shows an empty state and a disabled Generate with the reason while the model is down', () => {
    const { w } = mk()
    expect(w.text()).toContain('No takes yet')
    expect(w.find('[data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/not running/i)
  })

  it('the header names the source, line count and FX count; the button carries the take count', () => {
    const { w } = mk({ fxChosen: ref(['Clean', 'Servitor']) })
    expect(w.text()).toContain('source c2 · 2 lines · 2 FX')
    expect(w.find('[data-generate]').text()).toContain('Generate 2 takes')
  })

  it('submits one clone job: every ticked line for every source, one seed per line shared by the sources, FX attached', async () => {
    useModelStore().state = 'ready'
    api.jobSubmit.mockResolvedValue(job())
    const { w } = mk({ chosenSources: computed(() => [src1, src2]), fxChosen: ref(['Clean']) })
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    const [slug, kind, body] = api.jobSubmit.mock.calls[0]
    expect([slug, kind]).toEqual(['ruoldo', 'clone'])
    expect(body.fx).toEqual(['Clean'])
    expect(body.items).toHaveLength(4)
    expect(body.items.map((i: { guid: string }) => i.guid)).toEqual(['g1', 'g1', 'g2', 'g2'])
    expect(body.items[0].options.seed).toBe(body.items[1].options.seed)
    expect(body.items[0].options.seed).not.toBe(body.items[2].options.seed)
    expect(body.items[0].reference).toEqual({ wav: 'data/vd/c2.wav', text: 'Sample.' })
  })

  it('"One seed for all" uses a single seed for the whole batch and "Fixed" the typed one', async () => {
    useModelStore().state = 'ready'
    api.jobSubmit.mockResolvedValue(job())
    const one = mk({ seedPolicy: ref('one') })
    await one.w.find('[data-generate]').trigger('click')
    const seeds = api.jobSubmit.mock.calls[0][2].items.map((i: { options: { seed: string } }) => i.options.seed)
    expect(new Set(seeds).size).toBe(1)
    const opts = { ...makeCtx().options.value, seed: '4821' }
    const fixed = mk({ seedPolicy: ref('fixed'), options: ref(opts) })
    await fixed.w.find('[data-generate]').trigger('click')
    expect(api.jobSubmit.mock.calls[1][2].items.map((i: { options: { seed: string } }) => i.options.seed)).toEqual(['4821', '4821'])
  })

  it('needs a source and lines before it can run', () => {
    useModelStore().state = 'ready'
    const { w } = mk({ chosenSources: computed(() => []) })
    expect(w.find('[data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Tick a source and some lines first.')
  })

  it('shows a running job as a card with take n of m, the queue and a Cancel that finishes the current take', async () => {
    useWorkbenchJobsStore().active.ruoldo = [job()] as never
    api.jobCancel.mockResolvedValue(job())
    const { w } = mk()
    expect(w.find('[role=status]').text()).toContain('Take 2 of 4 · Oh! Yes! Yes, of course, this very day')
    expect(w.text()).toContain('2 more queued · finishes the current take')
    await w.findAll('button').find((b) => b.text() === 'Cancel')!.trigger('click')
    expect(api.jobCancel).toHaveBeenCalledWith('j1')
  })

  it('a failed job is explained next to the Generate button', () => {
    useWorkbenchJobsStore().problem.ruoldo = 'the model is down'
    const { w } = mk()
    expect(w.find('[role=alert]').text()).toContain('the model is down')
  })

  it('estimates the time from the speaker\'s earlier takes', () => {
    useModelStore().state = 'ready'
    const { w } = mk({ takes: ref([takeOf('t1', { seconds: 10 }), takeOf('t2', { seconds: 20 })]) })
    expect(w.text()).toContain('~30 s on the current model · runs in the background; keep ranking')
  })

  it('without a job queue it generates one take at a time, applies FX after each, and shows a failure', async () => {
    useModelStore().state = 'ready'
    api.jobSubmit.mockRejectedValue(new ApiRequestError(404, 'no route'))
    let n = 0
    api.cloneGenerate.mockImplementation(async () => { n++; if (n === 2) throw new Error('model backend is not running'); return takeOf(`t${n}`) })
    api.takeFx.mockResolvedValue(takeOf('t1'))
    const { ctx, w } = mk({ fxChosen: ref(['Clean']) })
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(api.cloneGenerate).toHaveBeenCalledTimes(2)
    expect(api.takeFx).toHaveBeenCalledWith('ruoldo', 't1', ['Clean'])
    expect(ctx.upsertTake).toHaveBeenCalled()
    expect(errors()).toContain('model backend is not running')
  })

  it('groups takes by line with a page of groups and Show more', async () => {
    const lines = Array.from({ length: 25 }, (_, i) => lineOf(`g${i}`))
    const takes = lines.map((l, i) => takeOf(`t${i}`, { guid: l.guid, text: l.text }))
    const { w } = mk({ lines: ref(lines), takes: ref(takes) })
    expect(w.findAll('.res')).toHaveLength(20)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.res')).toHaveLength(25)
  })
})
