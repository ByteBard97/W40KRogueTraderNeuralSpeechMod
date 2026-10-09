import { mount, flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import SpeakersView from './SpeakersView.vue'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn() } }))

const sp = (name: string, status: string, origin = 'real') => ({ slug: name.toLowerCase(), name, origin, line_count: 3, status })
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
