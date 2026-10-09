import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ApiRequestError, api } from '../api/client'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: { pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn(), poolRename: vi.fn(), poolSpot: vi.fn() },
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
})
