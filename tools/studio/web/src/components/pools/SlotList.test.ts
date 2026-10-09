import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({ api: { poolSpot: vi.fn().mockResolvedValue({ slot: 'male_human', size: 10, remaining: 1, items: [{ guid: 'u1', text: 'Sampled line.', entry: null }] }), poolSpotRecord: vi.fn() } }))
import { createRouter, createMemoryHistory } from 'vue-router'
import SlotList from './SlotList.vue'

const slots = [{ id: 'male_human', name: 'Male human', speaker_key: 'pool_male_human', slug: 'pool_male_human', gender: 'male', species: 'human', age: null, lines: 1300, spot: { checked: 4, wrong: 1 } }]
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers/:slug', component: { template: '<i/>' } }] })

describe('SlotList', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists slots with counts, spot-check progress and a link to the slot page', () => {
    const w = mount(SlotList, { props: { slots }, global: { plugins: [router] } })
    expect(w.text()).toContain('Male human')
    expect(w.text()).toContain('1300')
    expect(w.text()).toContain('4 checked')
    expect(w.find('a').attributes('href')).toBe('/speakers/pool_male_human')
  })

  it('emits rename with the new name', async () => {
    const w = mount(SlotList, { props: { slots }, global: { plugins: [router] } })
    await w.find('[data-rename]').trigger('click')
    await w.find('input').setValue('Dockhands')
    await w.find('[data-save-name]').trigger('click')
    expect(w.emitted('rename')![0]).toEqual(['male_human', 'Dockhands'])
  })

  it('shows an empty state with no slots', () => {
    expect(mount(SlotList, { props: { slots: [] }, global: { plugins: [router] } }).text()).toMatch(/no slots/i)
  })

  it('tells its parent when a spot check was recorded, so the counts can refresh', async () => {
    vi.mocked(api.poolSpotRecord).mockResolvedValue({ checked: 1, wrong: 0 })
    const w = mount(SlotList, { props: { slots }, global: { plugins: [router] } })
    await w.find('[data-spot]').trigger('click')
    await flushPromises()
    await w.find('[data-ok]').trigger('click')
    await w.find('[data-submit]').trigger('click')
    await flushPromises()
    expect(w.emitted('recorded')).toHaveLength(1)
  })

  it('opens a spot check for a slot on demand', async () => {
    const w = mount(SlotList, { props: { slots }, global: { plugins: [router] } })
    expect(api.poolSpot).not.toHaveBeenCalled()
    await w.find('[data-spot]').trigger('click')
    await flushPromises()
    expect(api.poolSpot).toHaveBeenCalledWith('male_human')
    expect(w.text()).toContain('Sampled line.')
    await w.find('[data-spot]').trigger('click')
    expect(w.text()).not.toContain('Sampled line.')
  })

  it('merges a slot into another after showing how many lines move', async () => {
    const two = [...slots, { ...slots[0], id: 'female_human', name: 'Female human', lines: 50 }]
    const w = mount(SlotList, { props: { slots: two }, global: { plugins: [router] } })
    await w.find('[data-merge]').trigger('click')
    expect(w.find('[data-merge-confirm]').exists()).toBe(false)
    await w.find('[data-merge-target]').setValue('female_human')
    expect(w.find('[data-merge-note]').text()).toBe('Move 1300 lines from Male human into Female human?')
    await w.find('[data-merge-confirm]').trigger('click')
    expect(w.emitted('merge')![0]).toEqual(['male_human', 'female_human'])
    expect(w.find('[data-merge-target]').exists()).toBe(false)
  })

  it('offers no merge with a single slot', () => {
    expect(mount(SlotList, { props: { slots }, global: { plugins: [router] } }).find('[data-merge]').exists()).toBe(false)
  })
})
