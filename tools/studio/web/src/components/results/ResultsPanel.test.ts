import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, ref } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { useModelStore } from '../../stores/model'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'
import { DEFAULT_OPTIONS } from '../../composables/useSpeakerState'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))
vi.mock('../../api/client', () => ({ api: { cloneGenerate: vi.fn(), takeFx: vi.fn(), takeRate: vi.fn() } }))

import ResultsPanel from './ResultsPanel.vue'

const lines = [{ guid: 'g1', text: 'Greetings.', instruct: null, baseline: null }, { guid: 'g2', text: 'Farewell.', instruct: null, baseline: null }]
const src = { key: 'real:E1', label: 'E1', wav: 'data/v/E1.wav', text: 'Hello.', origin: 'real' }

function mountPanel(over: Record<string, unknown> = {}) {
  const takes = ref<unknown[]>([])
  const ctx = {
    slug: 'pasqal', lines: ref(lines), takes, options: ref({ ...DEFAULT_OPTIONS }), fxChosen: ref<string[]>([]),
    selectedLines: ref(new Set(['g1', 'g2'])), chosenSources: computed(() => [src]),
    upsertTake: (t: unknown) => takes.value.unshift(t), ...over,
  }
  return { ctx, w: mount(ResultsPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('ResultsPanel', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('shows an empty state and a disabled generate while the model is down', () => {
    const { w } = mountPanel()
    expect(w.text()).toContain('No takes yet')
    expect(w.find('[data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/not running/i)
  })

  it('generates sources x lines and shows progress and the count on the button', async () => {
    useModelStore().state = 'ready'
    let n = 0
    vi.mocked(api.cloneGenerate).mockImplementation(async () => ({ id: `t${++n}`, guid: `g${n}`, text: `x${n}`, raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: n, rating: 0, fx: null } as never))
    const { w } = mountPanel()
    expect(w.find('[data-generate]').text()).toContain('2')
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(api.cloneGenerate).toHaveBeenCalledTimes(2)
    expect(w.text()).toContain('done, 2 takes')
  })

  it('applies chosen FX automatically after each take', async () => {
    useModelStore().state = 'ready'
    vi.mocked(api.cloneGenerate).mockResolvedValue({ id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: null } as never)
    vi.mocked(api.takeFx).mockResolvedValue({ id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: { presets: ['Clean'], wav: 'w', v: 1 } } as never)
    const { w } = mountPanel({ fxChosen: ref(['Clean']), selectedLines: ref(new Set(['g1'])) })
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(api.takeFx).toHaveBeenCalledWith('pasqal', 't1', ['Clean'])
  })

  it('stops on a backend error, shows it, and keeps takes already made', async () => {
    useModelStore().state = 'ready'
    let n = 0
    vi.mocked(api.cloneGenerate).mockImplementation(async () => {
      if (++n === 2) throw new Error('model backend is not running')
      return { id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: null } as never
    })
    const { ctx, w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('model backend is not running')
    expect(ctx.takes.value).toHaveLength(1)
  })

  it('disables generate with a hint when no source or no line is selected', () => {
    useModelStore().state = 'ready'
    const { w } = mountPanel({ selectedLines: ref(new Set()) })
    expect(w.find('[data-generate]').attributes('disabled')).toBeDefined()
    expect(w.text()).toMatch(/tick a source and some lines/i)
  })

  it('stops a running batch when the page is left, so nothing keeps using the GPU', async () => {
    useModelStore().state = 'ready'
    let release: (v: unknown) => void = () => {}
    vi.mocked(api.cloneGenerate).mockImplementation(() => new Promise((r) => { release = r }) as never)
    const { w } = mountPanel()
    await w.find('[data-generate]').trigger('click')
    await flushPromises()
    expect(api.cloneGenerate).toHaveBeenCalledTimes(1)
    w.unmount()
    release({ id: 't1', guid: 'g1', text: 'x', raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: 1, rating: 0, fx: null })
    await flushPromises()
    expect(api.cloneGenerate).toHaveBeenCalledTimes(1)
  })

  it('renders a capped number of take groups and shows more on request', async () => {
    const many = Array.from({ length: 70 }, (_, i) => ({ id: `t${i}`, guid: `g${i}`, text: `line ${i}`, raw: 'r', reference: src.wav, options: DEFAULT_OPTIONS, seed: i, rating: 0, fx: null }))
    const { w } = mountPanel({ takes: ref(many) })
    expect(w.findAll('.group')).toHaveLength(50)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.group')).toHaveLength(70)
    expect(w.find('[data-more]').exists()).toBe(false)
  })
})
