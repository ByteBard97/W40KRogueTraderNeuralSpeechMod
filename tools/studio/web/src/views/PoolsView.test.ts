import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ApiRequestError, api } from '../api/client'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: { pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn(), poolRename: vi.fn(), poolMerge: vi.fn(), poolSpot: vi.fn() },
}))

import PoolsView from './PoolsView.vue'

const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers/:slug', component: { template: '<i/>' } }] })
const summary = { threshold: 0.8, built: 'now', total: 3, destinations: { narrator: 0, speaker_bank: 1, speaker_nobank: 1, slot: 1 },
  slots: [{ id: 'male_human', name: 'Male human', speaker_key: 'pool_male_human', slug: 'pool_male_human', gender: 'male', species: 'human', age: null, lines: 1, spot: { checked: 0, wrong: 0 } }], queue_lines: 0, queue_entries: 0 }

describe('PoolsView', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('offers to build the pools when they do not exist yet', async () => {
    vi.mocked(api.pools).mockRejectedValue(new ApiRequestError(404, 'pools are not built yet'))
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toMatch(/not built/i)
    vi.mocked(api.poolsRebuild).mockResolvedValue(summary as never)
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([])
    await w.find('[data-build]').trigger('click')
    await flushPromises()
    expect(api.poolsRebuild).toHaveBeenCalled()
    expect(w.text()).toContain('Male human')
  })

  it('shows the summary, the slots and an empty queue', async () => {
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([])
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('Male human')
    expect(w.text()).toMatch(/nothing needs review/i)
  })

  it('shows an error message when the load fails', async () => {
    vi.mocked(api.pools).mockRejectedValue(new Error('boom'))
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    expect(w.text()).toContain('boom')
  })

  it('reports a failed rename instead of throwing', async () => {
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([])
    vi.mocked(api.poolRename).mockRejectedValue(new Error('rename refused'))
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    w.findComponent({ name: 'SlotList' }).vm.$emit('rename', 'male_human', 'New')
    await flushPromises()
    expect(w.text()).toContain('rename refused')
  })

  const two = { ...summary, slots: [...summary.slots, { ...summary.slots[0], id: 'female_human', name: 'Female human', lines: 4 }] }
  async function mergeFlow() {
    vi.mocked(api.pools).mockResolvedValue(two as never)
    vi.mocked(api.poolQueue).mockResolvedValue([])
    const w = mount(PoolsView, { global: { plugins: [router] } })
    await flushPromises()
    await w.find('[data-merge]').trigger('click')
    await w.find('[data-merge-target]').setValue('female_human')
    await w.find('[data-merge-confirm]').trigger('click')
    await flushPromises()
    return w
  }

  it('merges a slot, shows how many lines moved and reloads', async () => {
    vi.mocked(api.poolMerge).mockResolvedValue({ changed: 1 })
    const w = await mergeFlow()
    expect(api.poolMerge).toHaveBeenCalledWith('male_human', 'female_human')
    expect(w.find('[data-notice]').text()).toContain('1 line moved')
    expect(api.pools).toHaveBeenCalledTimes(2)
  })

  it('shows a failed merge as an error', async () => {
    vi.mocked(api.poolMerge).mockRejectedValue(new Error('merge needs two different existing slots'))
    const w = await mergeFlow()
    expect(w.text()).toContain('merge needs two different existing slots')
  })
})
