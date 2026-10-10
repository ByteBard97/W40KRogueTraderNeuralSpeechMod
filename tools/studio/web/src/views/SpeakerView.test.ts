import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { designState } from '../test-utils/speakerCtx'

const api = vi.hoisted(() => ({
  speaker: vi.fn(), lines: vi.fn(), takes: vi.fn(), fxPresets: vi.fn(), fxLibrary: vi.fn(), speakers: vi.fn(), jobsActive: vi.fn(),
  pools: vi.fn(), matches: vi.fn(), qaRuns: vi.fn(),
}))
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
import SpeakerView from './SpeakerView.vue'

const summary = { slug: 'ruoldo', name: 'Governor Ruoldo', origin: 'designed', line_count: 1, status: 'source', has_pick: false }
const stubs = { RouterLink: { template: '<a><slot /></a>' } }

describe('SpeakerView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    api.speaker.mockResolvedValue({ summary, clips: [], design: designState(), profile: null })
    api.lines.mockResolvedValue([{ guid: 'g1', text: 'Hello there.', emotion: 'neutral', intensity: 0.2, pace: 'normal', instruct: null, baseline: null }])
    api.takes.mockResolvedValue([])
    api.fxPresets.mockResolvedValue(['Clean'])
    api.fxLibrary.mockResolvedValue([])
    api.speakers.mockResolvedValue([summary])
    api.jobsActive.mockResolvedValue([])
    for (const f of [api.pools, api.matches, api.qaRuns]) f.mockRejectedValue(new Error('x'))
  })

  it('loads the speaker and shows the five numbered sections, with the results beside them', async () => {
    const w = mount(SpeakerView, { props: { slug: 'ruoldo' }, global: { stubs } })
    await flushPromises()
    expect(w.text()).toContain('Governor Ruoldo')
    for (const t of ['Source · designed voice', 'Test lines', 'Options', 'Post-processing', 'Results']) expect(w.text()).toContain(t)
    expect(w.find('aside.results').exists()).toBe(true)
    expect(api.speaker).toHaveBeenCalledWith('ruoldo')
  })

  it('shows an error block when the speaker cannot be loaded', async () => {
    api.speaker.mockRejectedValue(new Error('no speaker \'nobody\''))
    const w = mount(SpeakerView, { props: { slug: 'nobody' }, global: { stubs } })
    await flushPromises()
    expect(w.find('[role=alert]').text()).toContain('no speaker')
  })

  it('starts following the speaker\'s jobs, so a batch started earlier shows up again', async () => {
    mount(SpeakerView, { props: { slug: 'ruoldo' }, global: { stubs } })
    await flushPromises()
    expect(api.jobsActive).toHaveBeenCalledWith('ruoldo')
  })
})
