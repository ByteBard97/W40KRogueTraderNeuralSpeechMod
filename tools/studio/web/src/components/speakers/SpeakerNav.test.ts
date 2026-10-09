import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { useSpeakersStore } from '../../stores/speakers'
import SpeakerNav from './SpeakerNav.vue'

vi.mock('../../api/client', () => ({ api: { speakers: vi.fn().mockResolvedValue([]), registerAll: vi.fn() } }))

const sp = (name: string, has_pick = false) => ({ slug: name.toLowerCase(), name, origin: 'designed', line_count: 1, status: 'source', has_pick })
const link = { RouterLink: { props: ['to'], template: '<a :href="to"><slot /></a>' } }

describe('SpeakerNav', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows N / total, picked count, and links to the neighbours', () => {
    const store = useSpeakersStore()
    store.list = [sp('A', true), sp('B'), sp('C', true)] as never
    const w = mount(SpeakerNav, { props: { slug: 'b' }, global: { stubs: link } })
    expect(w.text()).toContain('2 / 3')
    expect(w.text()).toContain('2 picked')
    expect(w.find('a[data-prev]').attributes('href')).toBe('/speakers/a')
    expect(w.find('a[data-next]').attributes('href')).toBe('/speakers/c')
  })

  it('disables the arrows when the speaker is not in the list', () => {
    const w = mount(SpeakerNav, { props: { slug: 'zzz' }, global: { stubs: link } })
    expect(w.find('a[data-prev]').exists()).toBe(false)
    expect(w.find('span[data-prev]').exists()).toBe(true)
  })
})
