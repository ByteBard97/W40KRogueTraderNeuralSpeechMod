import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { slot, summaryOf } from '../test-utils/poolFixtures'
import { usePoolRoutesStore } from './poolRoutes'
import { usePoolsStore } from './pools'

vi.mock('../api/client', () => ({ api: { poolRoutes: vi.fn() } }))

function setup() {
  setActivePinia(createPinia())
  vi.clearAllMocks()
  vi.mocked(api.poolRoutes).mockResolvedValue({ total: 120, offset: 0, limit: 50, items: [] })
  usePoolsStore().summary = summaryOf([slot('male_human', 'Male human')])
  return usePoolRoutesStore()
}
const lastParams = () => vi.mocked(api.poolRoutes).mock.calls.at(-1)![0]

describe('pool routes store', () => {
  beforeEach(() => vi.useRealTimers())

  it('asks for 50 rows and describes the range', async () => {
    const s = setup()
    s.items = [{ guid: 'a' }] as never
    await s.load()
    expect(lastParams()).toMatchObject({ offset: 0, limit: 50 })
    expect(s.total).toBe(120)
  })

  it('maps the bank destinations to to=speaker plus bank', async () => {
    const s = setup()
    await s.setDest('bank')
    expect(lastParams()).toMatchObject({ to: 'speaker', bank: 1 })
    await s.setDest('nobank')
    expect(lastParams()).toMatchObject({ to: 'speaker', bank: 0 })
    await s.setDest('narrator')
    expect(lastParams()).toMatchObject({ to: 'narrator', bank: undefined })
  })

  it('filters by slot, confidence threshold and review state', async () => {
    const s = setup()
    await s.setSlot('male_human')
    await s.setLowConf(true)
    await s.setReviewOnly(true)
    expect(lastParams()).toMatchObject({ to: 'slot', slot: 'male_human', conf_lt: 0.8, queued: true })
    expect(s.filters.map((f) => f.label)).toEqual(['Shared slot voice', 'Male human', 'Below 0.8', 'Needs review'])
  })

  it('removes one filter or clears all, going back to page one', async () => {
    const s = setup()
    await s.setLowConf(true)
    await s.step(1)
    expect(s.offset).toBe(50)
    await s.remove('conf')
    expect(s.offset).toBe(0)
    expect(lastParams().conf_lt).toBeUndefined()
    await s.setDest('slot')
    await s.clear()
    expect(s.filters).toEqual([])
  })

  it('pages forward and stops at the end', async () => {
    const s = setup()
    await s.load()
    s.items = new Array(50).fill({}) as never
    await s.step(1)
    expect(s.offset).toBe(50)
    await s.step(1)
    expect(s.offset).toBe(100)
    expect(s.last).toBe(true)
    await s.step(-9)
    expect(s.offset).toBe(0)
  })

  it('debounces the search box', async () => {
    const s = setup()
    vi.useFakeTimers()
    s.search('vox')
    s.search('vox master')
    expect(api.poolRoutes).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(400)
    expect(api.poolRoutes).toHaveBeenCalledTimes(1)
    expect(lastParams().q).toBe('vox master')
  })

  it('keeps an error from a failed load', async () => {
    const s = setup()
    vi.mocked(api.poolRoutes).mockRejectedValue(new Error('boom'))
    await s.load()
    expect(s.error).toBe('boom')
  })
})
