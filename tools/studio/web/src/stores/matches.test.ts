import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useMatchesStore } from './matches'

vi.mock('../api/client', () => ({ api: { matches: vi.fn(), matchDecision: vi.fn() } }))

const row = (id: string, over = {}) => ({ id, flagged: false, decision: '', effective: 'accept', ...over })
const page = (items: unknown[], total = items.length) => ({ total, offset: 0, limit: 50, counts: { flagged: 0, bank: 0, nobank: 0, undecided: 0 }, items })

describe('matches store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('loads a page and appends the next one', async () => {
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('a'), row('b')], 3) as never).mockResolvedValueOnce(page([row('c')], 3) as never)
    const s = useMatchesStore()
    await s.load()
    await s.load(true)
    expect(s.items.map((r) => r.id)).toEqual(['a', 'b', 'c'])
    expect(vi.mocked(api.matches).mock.calls[1][0]).toMatchObject({ offset: 2 })
  })

  it('a new filter starts again from the first page', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([row('a')]) as never)
    const s = useMatchesStore()
    await s.setFilter({ group: 'bank' })
    expect(vi.mocked(api.matches)).toHaveBeenCalledWith({ group: 'bank', offset: 0, limit: 50 })
  })

  it('decides optimistically and reports a pools rebuild', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([row('a', { flagged: true, effective: '' })]) as never)
    vi.mocked(api.matchDecision).mockResolvedValue({ pools_rebuilt: true, queue_entries: 61 })
    const s = useMatchesStore()
    await s.load()
    const p = s.decide('a', 'reject')
    expect(s.items[0].decision).toBe('reject')
    await p
    expect(s.notice).toContain('61')
  })

  it('puts the row back and shows the error when the save fails', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([row('a')]) as never)
    vi.mocked(api.matchDecision).mockRejectedValue(new Error('nope'))
    const s = useMatchesStore()
    await s.load()
    await s.decide('a', 'reject')
    expect(s.items[0]).toMatchObject({ decision: '', effective: 'accept' })
    expect(s.error).toBe('nope')
  })

  it('clearing a clean row goes back to accepted, a flagged one to undecided', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([row('a', { decision: 'reject', effective: 'reject' }), row('b', { flagged: true, decision: 'accept', effective: 'accept' })]) as never)
    vi.mocked(api.matchDecision).mockResolvedValue({ pools_rebuilt: false })
    const s = useMatchesStore()
    await s.load()
    await s.decide('a', '')
    await s.decide('b', '')
    expect(s.items.map((r) => r.effective)).toEqual(['accept', ''])
  })
})
