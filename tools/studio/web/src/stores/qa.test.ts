import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useQaStore } from './qa'

vi.mock('../api/client', () => ({ api: { qaRuns: vi.fn(), qaFacets: vi.fn(), qaClips: vi.fn(), qaVerdict: vi.fn() } }))

const clip = (guid: string, verdict: unknown = null) => ({ guid, verdict })
const page = (items: unknown[], stats = { good: 1, bad: 0, unjudged: 2 }) => ({ total: 3, offset: 0, limit: 40, items, stats })

describe('qa store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('loads runs and falls back to the first when export is missing', async () => {
    vi.mocked(api.qaRuns).mockResolvedValue([{ id: 'r1', label: 'r1', clips: 3 }])
    const s = useQaStore()
    await s.loadRuns()
    expect(s.run).toBe('r1')
  })

  it('loads a page with the filter, run and page size', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a')]) as never)
    const s = useQaStore()
    await s.setFilter({ speaker: 'Abelard', sort: 'slowest' })
    expect(api.qaClips).toHaveBeenCalledWith('export', expect.objectContaining({ speaker: 'Abelard', sort: 'slowest', offset: 0, limit: 40 }))
    expect(s.items).toHaveLength(1)
    expect(s.stats.unjudged).toBe(2)
  })

  it('switching run reloads facets and the first page', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([]) as never)
    vi.mocked(api.qaFacets).mockResolvedValue({ speakers: ['A'], refs: [], engines: [], flags: [] })
    const s = useQaStore()
    await s.setRun('r2')
    expect(api.qaFacets).toHaveBeenCalledWith('r2')
    expect(s.facets.speakers).toEqual(['A'])
  })

  it('sets a verdict optimistically and moves the counts', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a')]) as never)
    vi.mocked(api.qaVerdict).mockResolvedValue({})
    const s = useQaStore()
    await s.loadPage(0)
    const p = s.setVerdict('a', 'bad')
    expect(s.items[0].verdict).toMatchObject({ verdict: 'bad', tags: [], note: '' })
    expect(s.stats).toEqual({ good: 1, bad: 1, unjudged: 1 })
    await p
    expect(api.qaVerdict).toHaveBeenCalledWith({ run: 'export', guid: 'a', verdict: 'bad', tags: [], note: '' })
  })

  it('rolls the row and counts back when the save fails', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a', { verdict: 'good', tags: ['x'], note: 'n' })]) as never)
    vi.mocked(api.qaVerdict).mockRejectedValue(new Error('nope'))
    const s = useQaStore()
    await s.loadPage(0)
    await s.setVerdict('a', 'bad')
    expect(s.items[0].verdict).toEqual({ verdict: 'good', tags: ['x'], note: 'n' })
    expect(s.stats).toEqual({ good: 1, bad: 0, unjudged: 2 })
    expect(s.error).toBe('nope')
  })

  it('clearing sends null and counts the clip as unjudged', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a', { verdict: 'good', tags: [], note: '' })]) as never)
    vi.mocked(api.qaVerdict).mockResolvedValue({})
    const s = useQaStore()
    await s.loadPage(0)
    await s.setVerdict('a', null)
    expect(s.items[0].verdict).toBeNull()
    expect(s.stats).toEqual({ good: 0, bad: 0, unjudged: 3 })
    expect(vi.mocked(api.qaVerdict).mock.calls[0][0]).toMatchObject({ verdict: null })
  })

  it('saves tags and note with the existing verdict', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a', { verdict: 'bad', tags: [], note: '' }), clip('b')]) as never)
    vi.mocked(api.qaVerdict).mockResolvedValue({})
    const s = useQaStore()
    await s.loadPage(0)
    await s.setDetails('a', ['garbled'], 'hm')
    expect(api.qaVerdict).toHaveBeenCalledTimes(1)
    expect(vi.mocked(api.qaVerdict).mock.calls[0][0]).toEqual({ run: 'export', guid: 'a', verdict: 'bad', tags: ['garbled'], note: 'hm' })
  })

  it('with a verdict filter, next skips the clips already shown instead of trusting offsets', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValueOnce(page([clip('a'), clip('b')]) as never)
    await s.setFilter({ verdict: 'unjudged' })
    vi.mocked(api.qaVerdict).mockResolvedValue({})
    await s.setVerdict('a', 'good')
    // the server now lists only b and c; a left the filtered set
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('c')]), total: 1 } as never)    // the server skips a and b
    await s.nextPage()
    const args = vi.mocked(api.qaClips).mock.calls.at(-1)![1]
    expect(args).toMatchObject({ offset: 0, limit: 40, exclude: 'a,b' })
    expect(s.items.map((c) => c.guid)).toEqual(['c'])
    expect(s.hasNext).toBe(false)
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('b'), clip('c')]), total: 2 } as never)
    await s.prevPage()
    expect(s.items.map((c) => c.guid)).toEqual(['b', 'c'])
  })

  it('serialises saves per clip and does not roll back over a newer click', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a')]) as never)
    const order: string[] = []
    let failFirst!: (e: Error) => void
    vi.mocked(api.qaVerdict)
      .mockImplementationOnce(() => new Promise((_, rej) => { order.push('start1'); failFirst = rej }))
      .mockImplementationOnce(async () => { order.push('start2'); return {} })
    const s = useQaStore()
    await s.loadPage(0)
    const p1 = s.setVerdict('a', 'good')
    const p2 = s.setVerdict('a', 'bad')
    await Promise.resolve()
    expect(order).toEqual(['start1'])
    failFirst(new Error('boom'))
    await Promise.all([p1, p2])
    expect(order).toEqual(['start1', 'start2'])
    expect(s.items[0].verdict?.verdict).toBe('bad')
    expect(s.stats).toEqual({ good: 1, bad: 1, unjudged: 1 })
  })

  it('failed last save returns to the confirmed state and counts never go negative', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a')]) as never)
    vi.mocked(api.qaVerdict).mockResolvedValueOnce({}).mockRejectedValueOnce(new Error('x'))
    const s = useQaStore()
    await s.loadPage(0)
    s.stats = { good: 0, bad: 0, unjudged: 1 }
    await Promise.all([s.setVerdict('a', 'good'), s.setVerdict('a', 'bad')])
    expect(s.items[0].verdict?.verdict).toBe('good')
    expect(s.stats).toEqual({ good: 1, bad: 0, unjudged: 0 })
  })

  it('ignores a slow earlier page that finishes after a newer one', async () => {
    let resolveOld!: (v: never) => void
    vi.mocked(api.qaClips)
      .mockImplementationOnce(() => new Promise<never>((r) => { resolveOld = r }))
      .mockResolvedValueOnce(page([clip('new')]) as never)
    const s = useQaStore()
    const old = s.loadPage(0)
    await s.loadPage(0)
    resolveOld(page([clip('old')]) as never)
    await old
    expect(s.items.map((c) => c.guid)).toEqual(['new'])
    expect(s.loading).toBe(false)
  })

  it('facet loading does not clear the page loading flag', async () => {
    let done!: (v: never) => void
    vi.mocked(api.qaClips).mockImplementationOnce(() => new Promise<never>((r) => { done = r }))
    vi.mocked(api.qaFacets).mockResolvedValue({ speakers: [], refs: [], engines: [], flags: [] })
    const s = useQaStore()
    const p = s.loadPage(0)
    await s.loadFacets()
    expect(s.loading).toBe(true)
    done(page([]) as never)
    await p
    expect(s.loading).toBe(false)
  })

  it('pages through 500 filtered clips by exclusion without empty pages and ends with hasNext false', async () => {
    const all = Array.from({ length: 500 }, (_, i) => `g${i}`)
    vi.mocked(api.qaClips).mockImplementation((async (_run: string, f: { exclude?: string; limit?: number }) => {
      const skip = new Set((f.exclude ?? '').split(',').filter(Boolean))
      const left = all.filter((g) => !skip.has(g))
      return { ...page(left.slice(0, f.limit).map((g) => clip(g))), total: left.length }
    }) as never)
    const s = useQaStore()
    await s.setFilter({ verdict: 'bad' })
    const sizes = [s.items.length]
    while (s.hasNext) { await s.nextPage(); sizes.push(s.items.length) }
    expect(sizes.reduce((a, b) => a + b)).toBe(500)
    expect(sizes.every((n) => n > 0)).toBe(true)
    expect(s.total).toBe(500)
  })

  it('hasNext is false on an empty page', async () => {
    vi.mocked(api.qaClips).mockResolvedValue({ ...page([]), total: 7 } as never)
    const s = useQaStore()
    await s.setFilter({ verdict: 'bad' })
    expect(s.hasNext).toBe(false)
  })

  it('pushes the trail only when the page response is applied, and ignores nextPage while loading', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a')]), total: 3 } as never)
    await s.setFilter({ verdict: 'bad' })
    let done!: (v: never) => void
    vi.mocked(api.qaClips).mockImplementationOnce(() => new Promise<never>((r) => { done = r }))
    const first = s.nextPage()
    const second = s.nextPage()                    // a double click
    expect(api.qaClips).toHaveBeenCalledTimes(2)
    done({ ...page([clip('b')]), total: 2 } as never)
    await Promise.all([first, second])
    expect(s.canPrev).toBe(true)
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a')]), total: 3 } as never)
    await s.prevPage()
    expect(s.canPrev).toBe(false)
  })

  it('a failed page fetch leaves the trail alone', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a')]), total: 3 } as never)
    await s.setFilter({ verdict: 'bad' })
    vi.mocked(api.qaClips).mockRejectedValueOnce(new Error('down'))
    await s.nextPage()
    expect(s.canPrev).toBe(false)
    expect(s.items.map((c) => c.guid)).toEqual(['a'])
  })

  it('tagging an unjudged clip marks it bad', async () => {
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('b')]) as never)
    vi.mocked(api.qaVerdict).mockResolvedValue({})
    const s = useQaStore()
    await s.loadPage(0)
    await s.setDetails('b', ['garbled'], '')
    expect(vi.mocked(api.qaVerdict).mock.calls[0][0]).toEqual({ run: 'export', guid: 'b', verdict: 'bad', tags: ['garbled'], note: '' })
  })

  it('a save that fails after the run changed does not touch the new run', async () => {
    vi.mocked(api.qaClips).mockResolvedValueOnce(page([clip('a')]) as never)
    let fail!: (e: Error) => void
    vi.mocked(api.qaVerdict).mockImplementationOnce(() => new Promise((_, rej) => { fail = rej }))
    const s = useQaStore()
    await s.loadPage(0)
    const p = s.setVerdict('a', 'bad')
    vi.mocked(api.qaFacets).mockResolvedValue({ speakers: [], refs: [], engines: [], flags: [] })
    vi.mocked(api.qaClips).mockResolvedValueOnce(page([clip('a', { verdict: 'good', tags: [], note: '' })]) as never)
    await s.setRun('other')
    fail(new Error('late'))
    await p
    expect(s.items[0].verdict?.verdict).toBe('good')
    expect(s.stats).toEqual({ good: 1, bad: 0, unjudged: 2 })
  })

  it('load more appends the next batch by offset and stops at the end', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a'), clip('b')]), total: 3 } as never)
    await s.loadPage(0)
    expect(s.hasNext).toBe(true)
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('c')]), total: 3, offset: 2 } as never)
    await s.loadMore()
    expect(vi.mocked(api.qaClips).mock.calls.at(-1)![1]).toMatchObject({ offset: 2, limit: 40 })
    expect(s.items.map((c) => c.guid)).toEqual(['a', 'b', 'c'])
    expect(s.hasNext).toBe(false)
    await s.loadMore()
    expect(api.qaClips).toHaveBeenCalledTimes(2)
  })

  it('load more under a verdict filter excludes everything already shown and keeps the cursor', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a'), clip('b')]), total: 3 } as never)
    await s.setFilter({ verdict: 'unjudged' })
    s.select(1)
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('c')]), total: 1 } as never)
    await s.loadMore()
    expect(vi.mocked(api.qaClips).mock.calls.at(-1)![1]).toMatchObject({ offset: 0, exclude: 'a,b' })
    expect(s.items.map((c) => c.guid)).toEqual(['a', 'b', 'c'])
    expect(s.total).toBe(3)
    expect(s.hasNext).toBe(false)
    expect(s.index).toBe(1)
  })

  it('drops a load-more answer that arrives after the list was reloaded', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a')]), total: 5 } as never)
    await s.loadPage(0)
    let late!: (v: never) => void
    vi.mocked(api.qaClips).mockImplementationOnce(() => new Promise<never>((r) => { late = r }))
    const more = s.loadMore()
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('x')]), total: 5 } as never)
    await s.setFilter({ speaker: 'Abelard' })
    late({ ...page([clip('stale')]), total: 5, offset: 1 } as never)
    await more
    expect(s.items.map((c) => c.guid)).toEqual(['x'])
  })

  it('next unjudged loads more of the queue until it finds one, and gives up at the end', async () => {
    const s = useQaStore()
    const done = { verdict: 'good', tags: [], note: '' }
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('a'), clip('b', done)]), total: 4 } as never)
    await s.loadPage(0)
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page([clip('c', done), clip('d')]), total: 4, offset: 2 } as never)
    expect(await s.findNextUnjudged(0)).toBe(3)
    expect(s.items).toHaveLength(4)
    expect(await s.findNextUnjudged(3)).toBe(-1)
  })

  it('cursor moves stay inside the list and a new page puts it back on the first clip', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValue(page([clip('a'), clip('b')]) as never)
    await s.loadPage(0)
    s.move(5)
    expect(s.current?.guid).toBe('b')
    s.move(-9)
    expect(s.index).toBe(0)
    s.select(1)
    await s.loadPage(0)
    expect(s.index).toBe(0)
  })

  it('counts first verdicts this session, not changes, and keeps the filtered view counts in step', async () => {
    const s = useQaStore()
    vi.mocked(api.qaClips).mockResolvedValue({ ...page([clip('a'), clip('b', { verdict: 'good', tags: [], note: '' })]), view: { good: 1, bad: 0, unjudged: 1, total: 2 } } as never)
    vi.mocked(api.qaVerdict).mockResolvedValue({})
    await s.loadPage(0)
    await s.setVerdict('a', 'good')
    await s.setVerdict('a', 'bad')
    await s.setVerdict('b', null)
    expect(s.session).toBe(1)
    expect(s.view).toEqual({ good: 0, bad: 1, unjudged: 1, total: 2 })
  })
})

