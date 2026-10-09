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

  it('with a state filter, show-more asks from the rows that still match', async () => {
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('a', { flagged: true, effective: '' }), row('b', { flagged: true, effective: '' })], 4) as never)
    vi.mocked(api.matchDecision).mockResolvedValue({ pools_rebuilt: false })
    const s = useMatchesStore()
    await s.setFilter({ state: 'undecided' })
    await s.decide('a', 'accept')
    expect(s.remaining).toBe(2)
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('c', { flagged: true, effective: '' })], 3) as never)
    await s.load(true)
    expect(vi.mocked(api.matches).mock.calls.at(-1)![0]).toMatchObject({ offset: 1 })
  })

  it('serialises saves per row and keeps a newer click when an older save fails', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([row('a')]) as never)
    const order: string[] = []
    let failFirst!: (e: Error) => void
    vi.mocked(api.matchDecision)
      .mockImplementationOnce(() => new Promise((_, rej) => { order.push('1'); failFirst = rej }))
      .mockImplementationOnce(async () => { order.push('2'); return { pools_rebuilt: false } })
    const s = useMatchesStore()
    await s.load()
    const p1 = s.decide('a', 'reject')
    const p2 = s.decide('a', 'accept')
    await Promise.resolve()
    expect(order).toEqual(['1'])
    failFirst(new Error('x'))
    await Promise.all([p1, p2])
    expect(order).toEqual(['1', '2'])
    expect(s.items[0].decision).toBe('accept')
  })

  it('drops a slow earlier load', async () => {
    let old!: (v: never) => void
    vi.mocked(api.matches).mockImplementationOnce(() => new Promise<never>((r) => { old = r })).mockResolvedValueOnce(page([row('new')]) as never)
    const s = useMatchesStore()
    const p = s.load()
    await s.setFilter({ group: 'bank' })
    old(page([row('old')]) as never)
    await p
    expect(s.items.map((r) => r.id)).toEqual(['new'])
    expect(s.loading).toBe(false)
  })

  it('show more ignores an unconfirmed decision, de-dupes rows and waits for saves', async () => {
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('a', { flagged: true, effective: '' }), row('b', { flagged: true, effective: '' })], 4) as never)
    let landed!: (v: { pools_rebuilt: boolean }) => void
    vi.mocked(api.matchDecision).mockImplementationOnce(() => new Promise((r) => { landed = r }))
    const s = useMatchesStore()
    await s.setFilter({ state: 'undecided' })
    const saving = s.decide('a', 'accept')
    expect(s.busy).toBe(true)
    await s.load(true)                                    // refused while the save is in flight
    expect(api.matches).toHaveBeenCalledTimes(1)
    landed({ pools_rebuilt: false })
    await saving
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('b', { flagged: true, effective: '' }), row('c', { flagged: true, effective: '' })], 3) as never)
    await s.load(true)
    expect(vi.mocked(api.matches).mock.calls.at(-1)![0]).toMatchObject({ offset: 1 })
    expect(s.items.map((r) => r.id)).toEqual(['a', 'b', 'c'])
  })

  it('after a failed save the offset still counts the row the server still lists', async () => {
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('a', { flagged: true, effective: '' })], 3) as never)
    vi.mocked(api.matchDecision).mockRejectedValueOnce(new Error('no'))
    const s = useMatchesStore()
    await s.setFilter({ state: 'undecided' })
    await s.decide('a', 'accept')
    vi.mocked(api.matches).mockResolvedValueOnce(page([row('b', { flagged: true, effective: '' })], 3) as never)
    await s.load(true)
    expect(vi.mocked(api.matches).mock.calls.at(-1)![0]).toMatchObject({ offset: 1 })
  })
})
