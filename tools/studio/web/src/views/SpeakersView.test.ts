import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import SpeakersView from './SpeakersView.vue'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn(), registerAll: vi.fn() } }))

const sp = (name: string, status: string, origin = 'real', has_pick = false) => ({ slug: name.toLowerCase(), name, origin, line_count: 3, status, has_pick })
const link = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

describe('SpeakersView', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('groups speakers and links to their page', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('Pasqal', 'source'), sp('Muaran', 'needs_voice', 'designed')] as never)
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w.text()).toContain('Needs a voice')
    expect(w.find('a[href="/speakers/muaran"]').exists()).toBe(true)
    expect(w.text()).toContain('designed')
  })

  it('marks speakers that have a pick and shows the picked count', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('Pasqal', 'source'), sp('Muaran', 'source', 'designed', true)] as never)
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w.findAll('[data-pick]')).toHaveLength(1)
    expect(w.find('a[href="/speakers/muaran"] [data-pick]').exists()).toBe(true)
    expect(w.find('[data-progress]').text()).toContain('1 picked')
    expect(w.find('[data-register-all]').exists()).toBe(true)
  })

  it('filters by name and shows a no-match message', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('Pasqal', 'source')] as never)
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    await w.find('input').setValue('zzz')
    expect(w.text()).toContain('No speakers match')
  })

  it('shows an empty state and an error message', async () => {
    vi.mocked(api.speakers).mockResolvedValue([])
    const w = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w.text()).toContain('No speakers yet')
    vi.mocked(api.speakers).mockRejectedValue(new Error('server down'))
    const w2 = mount(SpeakersView, { global: { stubs: link } })
    await flushPromises()
    expect(w2.text()).toContain('server down')
  })
})
