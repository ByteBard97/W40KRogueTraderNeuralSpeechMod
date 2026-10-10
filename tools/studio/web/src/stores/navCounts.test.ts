import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useNavCountsStore } from './navCounts'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn(), pools: vi.fn(), matches: vi.fn(), qaRuns: vi.fn() } }))

describe('navCounts', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('loads each count and tolerates one endpoint failing', async () => {
    vi.mocked(api.speakers).mockResolvedValue([{ status: 'needs_voice' }, { status: 'profile' }, { status: 'needs_voice' }] as never)
    vi.mocked(api.pools).mockRejectedValue(new Error('404'))
    vi.mocked(api.matches).mockResolvedValue({ counts: { undecided: 277 } } as never)
    vi.mocked(api.qaRuns).mockResolvedValue([{ id: 'r1', label: '', clips: 5 }, { id: 'export', label: '', clips: 11051 }])
    const s = useNavCountsStore()
    await s.load()
    expect(s.speakersLeft).toBe(2)
    expect(s.pools).toBeNull()
    expect(s.matchesUndecided).toBe(277)
    expect(s.qaClips).toBe(11051)
  })
})
