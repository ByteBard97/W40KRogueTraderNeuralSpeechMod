import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useSpeakersStore } from './speakers'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn() } }))

const sp = (name: string, status: string) => ({ slug: name.toLowerCase(), name, origin: 'real', line_count: 1, status })

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
})
