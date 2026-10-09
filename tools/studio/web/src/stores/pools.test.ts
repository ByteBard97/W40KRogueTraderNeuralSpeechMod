import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, api } from '../api/client'
import { usePoolsStore } from './pools'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: { pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn() },
}))

const summary = { threshold: 0.8, built: 'now', total: 3, destinations: { narrator: 0, speaker_bank: 1, speaker_nobank: 1, slot: 1 }, slots: [], queue_lines: 1, queue_entries: 1 }

describe('pools store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('loads the summary and queue', async () => {
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([{ key: 'C|a' }] as never)
    const s = usePoolsStore()
    await s.load()
    expect(s.summary?.total).toBe(3)
    expect(s.queue).toHaveLength(1)
    expect(s.notBuilt).toBe(false)
  })

  it('flags not-built on a 404 instead of showing an error', async () => {
    vi.mocked(api.pools).mockRejectedValue(new ApiRequestError(404, 'pools are not built yet'))
    const s = usePoolsStore()
    await s.load()
    expect(s.notBuilt).toBe(true)
    expect(s.error).toBeNull()
  })

  it('rebuild reloads, accept and move call the override endpoint and reload', async () => {
    vi.mocked(api.poolsRebuild).mockResolvedValue(summary as never)
    vi.mocked(api.pools).mockResolvedValue(summary as never)
    vi.mocked(api.poolQueue).mockResolvedValue([] as never)
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 2 } as never)
    const s = usePoolsStore()
    await s.rebuild()
    await s.accept('C|a')
    await s.move('C|a', { to: 'slot', slot: 'female_human' })
    expect(api.poolOverride).toHaveBeenNthCalledWith(1, { entry: 'C|a' })
    expect(api.poolOverride).toHaveBeenNthCalledWith(2, { entry: 'C|a', to: 'slot', slot: 'female_human' })
    expect(api.pools).toHaveBeenCalledTimes(3)
  })
})
