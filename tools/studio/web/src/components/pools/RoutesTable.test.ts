import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({ api: { poolRoutes: vi.fn(), poolOverride: vi.fn() } }))

import RoutesTable from './RoutesTable.vue'

const slots = [{ id: 'male_human', name: 'Male human' }, { id: 'female_human', name: 'Female human' }]
const item = (i: number) => ({ guid: `u${i}`, text: `Line ${i}.`, to: 'slot', slot: 'male_human', entry: 'C|a', confidence: 1, reasons: [], source: 'auto' })
const page = (total: number, n: number, offset = 0) => ({ total, offset, limit: 2, items: Array.from({ length: n }, (_, i) => item(offset + i)) })

describe('RoutesTable', () => {
  beforeEach(() => { vi.clearAllMocks(); vi.mocked(api.poolRoutes).mockResolvedValue(page(5, 2) as never) })

  it('loads the first page and shows rows with their destination', async () => {
    const w = mount(RoutesTable, { props: { slots: slots as never } })
    await flushPromises()
    expect(api.poolRoutes).toHaveBeenCalledWith({ to: undefined, slot: undefined, queued: undefined, offset: 0, limit: 25 })
    expect(w.text()).toContain('Line 0.')
    expect(w.text()).toContain('5 lines')
  })

  it('pages forward and back and disables the ends', async () => {
    vi.mocked(api.poolRoutes).mockResolvedValue(page(60, 2) as never)
    const w = mount(RoutesTable, { props: { slots: slots as never } })
    await flushPromises()
    expect(w.find('[data-prev]').attributes('disabled')).toBeDefined()
    vi.mocked(api.poolRoutes).mockResolvedValue(page(60, 2, 25) as never)
    await w.find('[data-next]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls[1][0]).toMatchObject({ offset: 25 })
  })

  it('refilters from the first page when a filter changes', async () => {
    const w = mount(RoutesTable, { props: { slots: slots as never } })
    await flushPromises()
    await w.find('[data-filter-slot]').setValue('female_human')
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls.at(-1)![0]).toMatchObject({ slot: 'female_human', offset: 0 })
    await w.find('[data-filter-queued]').setValue(true)
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls.at(-1)![0]).toMatchObject({ queued: true })
  })

  it('overrides one line to another slot and reloads', async () => {
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 1 })
    const w = mount(RoutesTable, { props: { slots: slots as never } })
    await flushPromises()
    await w.find('[data-move-line]').setValue('female_human')
    await flushPromises()
    expect(api.poolOverride).toHaveBeenCalledWith({ guids: ['u0'], to: 'slot', slot: 'female_human' })
    expect(api.poolRoutes).toHaveBeenCalledTimes(2)
  })

  it('shows an empty state when nothing matches', async () => {
    vi.mocked(api.poolRoutes).mockResolvedValue(page(0, 0) as never)
    const w = mount(RoutesTable, { props: { slots: slots as never } })
    await flushPromises()
    expect(w.text()).toMatch(/no lines match/i)
  })
})
