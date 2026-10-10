import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { ApiRequestError, api } from '../api/client'
import { useToasts } from '../composables/useToasts'
import { entryOf, slot, summaryOf } from '../test-utils/poolFixtures'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: {
    pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn(), poolRename: vi.fn(), poolMerge: vi.fn(), poolUnmerge: vi.fn(),
    poolSpot: vi.fn(), poolSpotRecord: vi.fn(), poolRoutes: vi.fn(), poolRestore: vi.fn(), poolCreateSlot: vi.fn(),
  },
}))

import PoolsView from './PoolsView.vue'

const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers/:slug', component: { template: '<i/>' } }] })
const slots = [slot('male_human', 'Male human', { lines: 8 }), slot('female_human', 'Female human', { lines: 4, spot: { checked: 10, wrong: 0 } })]

const mounted: { unmount: () => void }[] = []
function mountView() {
  const w = mount(PoolsView, { global: { plugins: [router] }, attachTo: document.body })
  mounted.push(w)
  return w
}
function key(k: string) {
  document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true }))
}
async function make(queue = [entryOf('a'), entryOf('b')]) {
  vi.mocked(api.pools).mockResolvedValue(summaryOf(slots))
  vi.mocked(api.poolQueue).mockResolvedValue(queue)
  vi.mocked(api.poolRoutes).mockResolvedValue({ total: 0, offset: 0, limit: 50, items: [] })
  vi.mocked(api.poolSpot).mockResolvedValue({ slot: 'male_human', size: 10, remaining: 2, items: [{ guid: 'u1', text: 'Sampled.', entry: null, wav: null }, { guid: 'u2', text: 'Sampled 2.', entry: null, wav: null }] })
  const w = mountView()
  await flushPromises()
  return w
}

describe('PoolsView', () => {
  afterEach(() => mounted.splice(0).forEach((w) => w.unmount()))
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); useToasts().clear() })

  it('offers to build the pools when they do not exist yet', async () => {
    vi.mocked(api.pools).mockRejectedValue(new ApiRequestError(404, 'pools are not built yet'))
    const w = mountView()
    await flushPromises()
    expect(w.text()).toMatch(/not built/i)
    vi.mocked(api.poolsRebuild).mockResolvedValue(summaryOf(slots))
    vi.mocked(api.pools).mockResolvedValue(summaryOf(slots))
    vi.mocked(api.poolQueue).mockResolvedValue([])
    vi.mocked(api.poolRoutes).mockResolvedValue({ total: 0, offset: 0, limit: 50, items: [] })
    await w.find('[data-build]').trigger('click')
    await flushPromises()
    expect(api.poolsRebuild).toHaveBeenCalled()
    expect(w.text()).toContain('Male human')
  })

  it('shows the header facts, tiles, routing summary, slots and queue', async () => {
    const w = await make()
    const t = w.text()
    expect(t).toContain('100 unnamed lines routed · built 2026-10-09 17:21 · confidence threshold 0.8')
    expect(t).toContain('Decisions saved')
    expect(t).toContain('roster entries to review')
    expect(t).toContain('1 / 2')
    expect(t).toContain('Where the unnamed lines go')
    expect(t).toContain('Review queue')
    expect(t).toContain('Male human')
    expect(t).toContain('Routes')
  })

  it('shows a load error with Retry', async () => {
    vi.mocked(api.pools).mockRejectedValue(new Error('boom'))
    const w = mountView()
    await flushPromises()
    expect(w.text()).toContain('boom')
  })

  it('A accepts the current entry and Z-style undo is offered', async () => {
    const w = await make()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3, undo: { previous: { g: {} } } })
    key('a')
    await flushPromises()
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a' })
    expect(useToasts().toasts.value[0].action?.label).toBe('Undo')
  })

  it('J and K move the review cursor, S skips', async () => {
    const w = await make()
    key('j')
    await flushPromises()
    expect(w.findAll('article')[1].attributes('aria-current')).toBe('true')
    key('k')
    key('s')
    await flushPromises()
    expect(w.findAll('article')[0].text()).toContain('Name b')
  })

  it('M moves to the chosen target when it differs from the guess', async () => {
    const w = await make()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3 })
    await w.find('select').setValue('slot:female_human')
    ;(document.activeElement as HTMLElement | null)?.blur()
    key('m')
    await flushPromises()
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a', to: 'slot', slot: 'female_human' })
  })

  it('keys do nothing while typing in a field', async () => {
    const w = await make()
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', bubbles: true }))
    expect(api.poolOverride).not.toHaveBeenCalled()
  })

  it('opens the spot check from a slot, and Y / W mark lines while the panel has focus', async () => {
    const w = await make()
    await w.find('[data-spot]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Spot check · Male human')
    key('y')
    key('w')
    await flushPromises()
    expect(w.text()).toContain('2 / 2 marked')
  })

  it('"Next unchecked slot" opens the first slot that still needs a check', async () => {
    const w = await make()
    await w.find('[data-tile-slots] button').trigger('click')
    await flushPromises()
    expect(api.poolSpot).toHaveBeenCalledWith('male_human')
  })

  it('merges a slot and offers Undo through the toast', async () => {
    const w = await make()
    vi.mocked(api.poolMerge).mockResolvedValue({ changed: 8 })
    await w.find('[data-merge]').trigger('click')
    await w.find('[data-merge-target-field] select').setValue('female_human')
    await w.find('[role="alertdialog"] button').trigger('click')
    await flushPromises()
    expect(api.poolMerge).toHaveBeenCalledWith('male_human', 'female_human')
    expect(useToasts().toasts.value[0].message).toContain('8 lines moved')
  })

  it('clicking a routing segment filters the routes table', async () => {
    const w = await make()
    await w.findAll('.bar .seg')[2].trigger('click')
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls.at(-1)![0]).toMatchObject({ to: 'narrator' })
  })

  it('a failed rename is reported as a toast, not thrown', async () => {
    const w = await make()
    vi.mocked(api.poolRename).mockRejectedValue(new Error('rename refused'))
    await w.find('[data-rename]').trigger('click')
    await w.find('[data-rename-input]').setValue('X')
    await w.find('[data-save-name]').trigger('click')
    await flushPromises()
    expect(useToasts().toasts.value[0].message).toContain('rename refused')
  })
})
