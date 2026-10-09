import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useSpeakersStore } from './speakers'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn(), registerAll: vi.fn() } }))

const sp = (name: string, status: string, has_pick = false) => ({ slug: name.toLowerCase(), name, origin: 'real', line_count: 1, status, has_pick })

describe('speakers store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('loads and groups by status', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('A', 'needs_voice'), sp('B', 'profile'), sp('C', 'needs_voice')] as never)
    const s = useSpeakersStore()
    await s.load()
    expect(s.byStatus.needs_voice.map((x) => x.name)).toEqual(['A', 'C'])
    expect(s.byStatus.profile).toHaveLength(1)
    expect(s.byStatus.source).toEqual([])
  })

  it('records an error and keeps the list empty', async () => {
    vi.mocked(api.speakers).mockRejectedValue(new Error('down'))
    const s = useSpeakersStore()
    await s.load()
    expect(s.error).toBe('down')
    expect(s.list).toEqual([])
  })

  it('counts picks, finds neighbours with wrap-around, and tracks a pick change', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('A', 'source', true), sp('B', 'needs_voice'), sp('C', 'source')] as never)
    const s = useSpeakersStore()
    await s.load()
    expect(s.pickedCount).toBe(1)
    expect(s.position('b')).toEqual({ index: 2, total: 3 })
    expect(s.neighbours('a')).toEqual({ prev: 'c', next: 'b' })
    expect(s.neighbours('missing')).toEqual({ prev: null, next: null })
    s.setPick('b', true)
    expect(s.pickedCount).toBe(2)
  })

  it('registers all picks and reloads the list', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('A', 'source', true)] as never)
    vi.mocked(api.registerAll).mockResolvedValue({ registered: ['A'], skipped: [] })
    const s = useSpeakersStore()
    const r = await s.registerAll()
    expect(r.registered).toEqual(['A'])
    expect(api.speakers).toHaveBeenCalled()
  })
})
