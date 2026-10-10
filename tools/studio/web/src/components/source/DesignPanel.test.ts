import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { cand, designState, makeCtx, withCtx } from '../../test-utils/speakerCtx'
import { useLiveTakesStore } from '../../stores/liveTakes'
import { useModelStore } from '../../stores/model'
import { useWorkbenchJobsStore } from '../../stores/workbenchJobs'
import { useToasts } from '../../composables/useToasts'

const api = vi.hoisted(() => ({
  designGenerate: vi.fn(), designKeep: vi.fn(), designVerdict: vi.fn(), designOrder: vi.fn(), designDescription: vi.fn(),
  jobSubmit: vi.fn(), jobsActive: vi.fn(), job: vi.fn(), jobCancel: vi.fn(),
}))
vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api }))

import { ApiRequestError } from '../../api/client'
import DesignPanel from './DesignPanel.vue'

const job = { id: 'j1', kind: 'design', slug: 'ruoldo', label: 'Designing', state: 'running', total: 1, done: 0, index: 1, items: [{ n: 0, state: 'running', seed: 606, cfg: 2, timesteps: 10, text: null }], takes: [], fx: [], error: null, elapsed_s: 3, expected_s: 10, current: { n: 0, text: null, seed: 606, cfg: 2, timesteps: 10, elapsed_s: 3, expected_s: 10 } }
const live = { file: 'live_tmp/t1.wav', seed: 4242, cfg: 2, timesteps: 10, seconds: 4.1, description: 'A calm woman.', text: 'Sample.' }

function mountPanel(design = designState()) {
  const ctx = makeCtx()
  ;(ctx.detail.value as { design: unknown }).design = design
  return { ctx, w: mount(DesignPanel, { attachTo: document.body, ...withCtx(ctx) }) }
}
const openLive = (w: ReturnType<typeof mountPanel>['w']) => w.find('.live .head').trigger('click')
const errors = () => useToasts().toasts.value.filter((t) => t.kind === 'err').map((t) => t.message)

describe('DesignPanel', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); useToasts().clear(); api.jobsActive.mockResolvedValue([]) })

  it('Pick sends an explicit pick and does not touch the order; picking again clears it', async () => {
    api.designVerdict.mockResolvedValue({})
    const { ctx, w } = mountPanel()
    await w.findAll('[data-cand=c1] button').find((b) => b.text() === 'Pick')!.trigger('click')
    expect(api.designVerdict).toHaveBeenCalledWith('ruoldo', { cand: 'c1.wav', pick: true })
    expect(api.designOrder).not.toHaveBeenCalled()
    expect((ctx.detail.value as { design: { pick: string } }).design.pick).toBe('c1.wav')
    await w.findAll('[data-cand=c1] button').find((b) => b.text() === 'Picked')!.trigger('click')
    expect(api.designVerdict).toHaveBeenLastCalledWith('ruoldo', { cand: 'c1.wav', pick: false })
  })

  it('rejecting the picked candidate also clears the pick', async () => {
    api.designVerdict.mockResolvedValue({})
    const { w } = mountPanel(designState({ pick: 'c0.wav' }))
    await w.findAll('[data-cand=c0] button').find((b) => b.text() === 'Reject')!.trigger('click')
    expect(api.designVerdict).toHaveBeenCalledWith('ruoldo', { cand: 'c0.wav', reject: true, pick: false })
  })

  it('reorder keeps the pick separate (the order call carries no follow_rank) and shows the new order at once', async () => {
    api.designOrder.mockResolvedValue({})
    const { w } = mountPanel(designState({ pick: 'c2.wav' }))
    await w.find('[aria-label="Move c0 down"]').trigger('click')
    expect(api.designOrder).toHaveBeenCalledWith('ruoldo', ['c1.wav', 'c0.wav', 'c2.wav'])
    await flushPromises()
    expect(w.findAll('[role=option]').map((r) => r.attributes('data-cand'))).toEqual(['c1', 'c0', 'c2'])
  })

  it('stores accent score and fit on the candidate, optimistically', async () => {
    api.designVerdict.mockResolvedValue({})
    const { ctx, w } = mountPanel()
    await w.find('[data-cand=c0] [aria-label="Accent score 3"]').trigger('click')
    await w.find('[data-cand=c0] [aria-label="Fit 2"]').trigger('click')
    expect(api.designVerdict).toHaveBeenCalledWith('ruoldo', { cand: 'c0.wav', accent_score: 3 })
    expect((ctx.detail.value as { design: { candidates: { verdict: object }[] } }).design.candidates[0].verdict).toMatchObject({ accent_score: 3, fit: 2 })
  })

  it('shows the server error as a toast and re-reads the speaker when a verdict fails', async () => {
    api.designVerdict.mockRejectedValue(new Error('rejected pick cannot be registered'))
    const { ctx, w } = mountPanel()
    await w.find('[data-cand=c0] [aria-label="Fit 2"]').trigger('click')
    await flushPromises()
    expect(errors()).toContain('rejected pick cannot be registered')
    expect(ctx.refreshDetail).toHaveBeenCalled()
  })

  it('Edit opens the description box; saving on blur writes only a real change', async () => {
    api.designDescription.mockResolvedValue({})
    const { w } = mountPanel()
    await w.findAll('button').find((b) => b.text().startsWith('Edit'))!.trigger('click')
    const box = w.find('textarea')
    await box.trigger('blur')
    expect(api.designDescription).not.toHaveBeenCalled()
    await w.findAll('button').find((b) => b.text().startsWith('Edit'))!.trigger('click')
    await w.find('textarea').setValue('A gruff man.')
    await w.find('textarea').trigger('blur')
    expect(api.designDescription).toHaveBeenCalledWith('ruoldo', 'A gruff man.')
    await w.findAll('button').find((b) => b.text().startsWith('Edit'))!.trigger('click')
    await w.find('textarea').setValue('   ')
    await w.find('textarea').trigger('blur')
    expect(api.designDescription).toHaveBeenCalledTimes(1)
  })

  it('Generate submits a design job and shows its row with the seed, id and a Cancel', async () => {
    useModelStore().state = 'ready'
    api.jobSubmit.mockResolvedValue(job)
    const { w } = mountPanel()
    await openLive(w)
    await w.find('input[data-seed]').setValue(' 55 ')
    await w.find('.live [data-generate]').trigger('click')
    await flushPromises()
    expect(api.jobSubmit).toHaveBeenCalledWith('ruoldo', 'design', { items: [{ description: 'A calm woman.', seed: '55', cfg: 2, timesteps: 10 }], label: 'Designing' })
    const row = w.find('.job')
    expect(row.text()).toContain('c3')
    expect(row.text()).toContain('seed 606')
    await row.find('button').trigger('click')
    expect(api.jobCancel).toHaveBeenCalledWith('j1')
  })

  it('names the next candidate id from the highest existing one', async () => {
    const { w } = mountPanel(designState({ candidates: [cand('c2.wav'), cand('c7.wav')], order: [] }))
    await openLive(w)
    expect(w.text()).toContain('Keep as c8')
  })

  it('disables Generate with the model reason while the model is down', async () => {
    const { w } = mountPanel()
    await openLive(w)
    expect(w.find('.live [data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/not running/i)
  })

  it('on a server without a job queue falls back to a synchronous generate', async () => {
    useModelStore().state = 'ready'
    api.jobSubmit.mockRejectedValue(new ApiRequestError(404, 'no route'))
    api.designGenerate.mockResolvedValue(live)
    const { w } = mountPanel()
    await openLive(w)
    await w.find('.live [data-generate]').trigger('click')
    await flushPromises()
    expect(api.designGenerate).toHaveBeenCalledWith('ruoldo', { description: 'A calm woman.', seed: '', cfg: 2, timesteps: 10 })
    expect(w.text()).toContain('4242')
  })

  it('lists unkept takes, reuses a seed, and keeps once even on a double click, refreshing only the detail', async () => {
    useLiveTakesStore().add('ruoldo', live)
    let done: (v: { cand: string }) => void = () => undefined
    api.designKeep.mockReturnValue(new Promise((r) => { done = r }))
    const { ctx, w } = mountPanel()
    await openLive(w)
    await w.find('[data-seed-chip]').trigger('click')
    expect((w.find('input[data-seed]').element as HTMLInputElement).value).toBe('4242')
    const keep = w.find('[data-keep]')
    await keep.trigger('click')
    await keep.trigger('click')
    done({ cand: 'c3.wav' })
    await flushPromises()
    expect(api.designKeep).toHaveBeenCalledTimes(1)
    expect(api.designKeep).toHaveBeenCalledWith('ruoldo', expect.objectContaining({ file: 'live_tmp/t1.wav', seed: 4242 }))
    expect(ctx.refreshDetail).toHaveBeenCalled()
    expect(ctx.load).not.toHaveBeenCalled()
    expect(useLiveTakesStore().forSlug('ruoldo')).toEqual([])
  })

  it('keeps unkept takes when the panel is mounted again for the same speaker', async () => {
    useLiveTakesStore().add('ruoldo', live)
    mountPanel().w.unmount()
    const { w } = mountPanel()
    await openLive(w)
    expect(w.text()).toContain('4242')
  })

  it('shows a job already running (the page was left and re-opened)', async () => {
    useWorkbenchJobsStore().active.ruoldo = [job as never]
    const { w } = mountPanel()
    expect(w.find('.job').exists()).toBe(true)
  })
})
