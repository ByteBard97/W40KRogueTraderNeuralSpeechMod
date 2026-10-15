import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { lineFixture, optionsFixture, recipeFixture, takeFixture } from '../test-utils/labFixtures'

vi.mock('../api/client', () => ({
  api: {
    labOptions: vi.fn(), labSpeakers: vi.fn(), labRecipes: vi.fn(), labLines: vi.fn(), labPrepare: vi.fn(), labTakes: vi.fn(), labRender: vi.fn(), labJob: vi.fn(),
    labJobCancel: vi.fn(), labTakeUpdate: vi.fn(), labRecipeSave: vi.fn(), labLexicon: vi.fn(), health: vi.fn(),
  },
}))
const audio = { src: '', currentTime: 0, duration: 10, volume: 1, loop: false, playbackRate: 1, ended: false, play: vi.fn().mockResolvedValue(undefined), pause: vi.fn(), addEventListener: vi.fn() }
vi.stubGlobal('Audio', vi.fn(() => audio))

import { useModelStore } from '../stores/model'
import LabView from './LabView.vue'

async function mountView() {
  vi.mocked(api.labOptions).mockResolvedValue(optionsFixture())
  vi.mocked(api.labSpeakers).mockResolvedValue([{ speaker: 'Vladaym Tocara the Liege', slug: 'v', lines: 3, chars: 100 }])
  vi.mocked(api.labRecipes).mockResolvedValue([recipeFixture()])
  vi.mocked(api.labLines).mockResolvedValue({
    speaker: 'Vladaym Tocara the Liege', ref: { wav: 'data/ref.wav' },
    lines: [lineFixture('a', 0, 14), lineFixture('b', 1, 9, 'overdriven'), lineFixture('c', 2, null)],
  })
  vi.mocked(api.labPrepare).mockResolvedValue({
    stages: [{ name: 'source', text: 'one — two' }, { name: 'split', text: 'one␞two' }],
    pieces: [{ text: 'one', kind: 'phrase', gap_ms: 260, display: 'one' }, { text: 'two', kind: 'phrase', gap_ms: null, display: 'two' }], recipe: recipeFixture(),
  })
  vi.mocked(api.labTakes).mockResolvedValue([takeFixture('t1', { metrics: { seconds: 2, peak_db: 0, crest_db: 9, clip_runs: 1, flag: 'overdriven', model_peak: 1.4 } })])
  const w = mount(LabView, { attachTo: document.body })
  await flushPromises()
  return w
}

describe('LabView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useModelStore().state = 'ready'
  })

  it('lists the lines, prepares the first and shows the pipeline with a pause divider', async () => {
    const w = await mountView()
    expect(w.findAll('[data-line]')).toHaveLength(3)
    expect(w.findAll('[data-stage]')).toHaveLength(2)
    expect(w.findAll('[data-piece]')).toHaveLength(2)
    expect(w.find('[data-gap]').text()).toContain('260 ms')
    w.unmount()
  })

  it('sorts worst first and marks the flagged crest', async () => {
    const w = await mountView()
    await w.findAll('.seg button').find((b) => b.text() === 'worst first')!.trigger('click')
    expect(w.findAll('[data-line] .txt')[0].text()).toBe('Line b text')
    expect(w.find('[data-line] [data-crest]').classes()).toContain('t-bad')
    w.unmount()
  })

  it('shows the current render and the lab take, with the model-exceeded warning', async () => {
    const w = await mountView()
    expect(w.findAll('[data-take]')).toHaveLength(2)
    expect(w.find('[data-exceeded]').text()).toContain('model exceeded full scale')
    expect(w.find('[data-recipe]').text()).toBe('cfg 3 · 10 steps · whole · em-dash keep')
    w.unmount()
  })

  it('re-prepares after the recipe changes (debounced)', async () => {
    vi.useFakeTimers()
    const w = await mountView()
    vi.mocked(api.labPrepare).mockClear()
    await w.find('[data-cfg]').setValue('2.5')
    expect(api.labPrepare).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(350)
    expect(api.labPrepare).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.labPrepare).mock.calls[0][0].recipe.cfg).toBe(2.5)
    vi.useRealTimers()
    w.unmount()
  })

  it('selects all flagged lines and renders them as a batch', async () => {
    const w = await mountView()
    vi.mocked(api.labRender).mockResolvedValue({ id: 'j', state: 'done', total: 1, done: 1, take_ids: [], error: null })
    await w.find('[data-check-flagged]').trigger('click')
    await w.find('[data-render-checked]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.labRender).mock.calls[0][0].items).toEqual([{ guid: 'b' }])
    expect(w.find('[data-progress]').text()).toContain('1/1')
    w.unmount()
  })

  it('disables rendering and says why when the model is down', async () => {
    const w = await mountView()
    useModelStore().state = 'down'
    await flushPromises()
    expect(w.find('[data-model-down]').exists()).toBe(true)
    expect(w.find('[data-render-selected]').attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('plays A and B after two takes are ticked', async () => {
    const w = await mountView()
    const marks = w.findAll('[data-mark]')
    await marks[0].trigger('click')
    await marks[1].trigger('click')
    await w.find('[data-play-b]').trigger('click')
    expect(audio.src).toContain(encodeURIComponent('data/studio/lab/x/takes/t1.wav'))
    w.unmount()
  })
})
