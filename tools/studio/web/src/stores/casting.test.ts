import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useCastingStore } from './casting'

vi.mock('../api/client', () => ({ api: { casting: vi.fn(), castingVoices: vi.fn(), castAssign: vi.fn(), castPortrait: vi.fn(), castAudition: vi.fn(), castLabels: vi.fn(), castLabelSet: vi.fn() } }))

const SCHEMA = [{ key: 'gender', label: 'Gender', kind: 'single', options: ['male', 'female'], required: true }, { key: 'age', label: 'Age', kind: 'single', options: ['youth', 'old'], required: true }]
const voice = (slug: string, mine = {}) => ({ slug, name: slug, lines: 100, minutes: 1, gender: 'male', f0: null, non_human: false, refs: [], used_by: [], labels: { ...mine }, mine, complete: false })

const char = (speaker: string, lines: number, bg3: string | null = null, kind = 'character') => ({
  speaker, display: speaker, kind, lines, rank: 1, role: 'role', status: 'voiceless', samples: [], suggestions: [], portrait: null,
  assignment: bg3 ? { bg3, name: bg3 } : null,
})
const page = (chars: unknown[]) => ({ characters: chars, total: chars.length, assigned: 0, portraits: [] })

describe('casting store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); vi.mocked(api.castingVoices).mockResolvedValue([]); vi.mocked(api.castLabels).mockResolvedValue({ schema: SCHEMA, progress: { total: 0, complete: 0, started: 0 } } as never) })

  it('lists the characters that still need a voice by default, biggest first as the server sent them', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 200), char('B', 100, 'gortash'), char('C', 50)]) as never)
    const s = useCastingStore()
    await s.load()
    expect(s.visible.map((c) => c.speaker)).toEqual(['A', 'C'])
    s.filter = 'cast'
    expect(s.visible.map((c) => c.speaker)).toEqual(['B'])
    expect(s.counts).toEqual({ total: 3, assigned: 1 })
    expect(s.linesLeft).toBe(250)
  })

  it('filters by name or role', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('Seberian', 200), char('Octaviana', 100)]) as never)
    const s = useCastingStore()
    await s.load()
    s.query = 'octa'
    expect(s.visible.map((c) => c.speaker)).toEqual(['Octaviana'])
  })

  it('assigning writes through the api and reloads from the server', async () => {
    vi.mocked(api.casting).mockResolvedValueOnce(page([char('A', 200), char('C', 50)]) as never)
      .mockResolvedValueOnce(page([char('A', 200, 'gortash'), char('C', 50)]) as never)
    vi.mocked(api.castAssign).mockResolvedValue({ speaker: 'A', bg3: 'gortash' })
    const s = useCastingStore()
    await s.load()
    await s.assign('A', 'gortash')
    expect(api.castAssign).toHaveBeenCalledWith('A', 'gortash')
    expect(s.characters[0].assignment?.bg3).toBe('gortash')
  })

  it('nextOpen moves on to the next character without a voice and wraps', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 200), char('B', 100, 'x'), char('C', 50)]) as never)
    const s = useCastingStore()
    await s.load()
    s.select('A')
    s.nextOpen()
    expect(s.selected).toBe('C')
    s.nextOpen()
    expect(s.selected).toBe('A')
  })

  it('keeps the error when a save fails', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 200)]) as never)
    vi.mocked(api.castAssign).mockRejectedValue(new Error('boom'))
    const s = useCastingStore()
    await s.load()
    await s.assign('A', 'x')
    expect(s.error).toBe('boom')
  })

  it('shows named characters by default and the nameless groups on request', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 200), char('pool_male_human', 1000, null, 'slot')]) as never)
    const s = useCastingStore()
    await s.load()
    expect(s.visible.map((c) => c.speaker)).toEqual(['A'])
    s.kind = 'slot'
    expect(s.visible.map((c) => c.speaker)).toEqual(['pool_male_human'])
    s.kind = 'all'
    expect(s.visible).toHaveLength(2)
  })

  it('a label is shown at once and counts as done when all required labels are set', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 1)]) as never)
    vi.mocked(api.castingVoices).mockResolvedValue([voice('v1', { gender: 'female' })] as never)
    vi.mocked(api.castLabelSet).mockImplementation(async (_s, k, val) => ({ gender: 'female', [k]: val }) as never)
    const s = useCastingStore()
    await s.load()
    expect(s.voices[0].complete).toBe(false)
    await s.setLabel('v1', 'age', 'youth')
    expect(api.castLabelSet).toHaveBeenCalledWith('v1', 'age', 'youth')
    expect(s.voices[0].mine).toEqual({ gender: 'female', age: 'youth' })
    expect(s.voices[0].complete).toBe(true)
  })

  it('a label that fails to save goes back to what it was', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 1)]) as never)
    vi.mocked(api.castingVoices).mockResolvedValue([voice('v1', { gender: 'female' })] as never)
    vi.mocked(api.castLabelSet).mockRejectedValue(new Error('disk full'))
    const s = useCastingStore()
    await s.load()
    await s.setLabel('v1', 'age', 'old')
    expect(s.voices[0].mine).toEqual({ gender: 'female' })
    expect(s.error).toBe('disk full')
  })

  it('clearing a label asks the server again, because the automatic guess comes back', async () => {
    vi.mocked(api.casting).mockResolvedValue(page([char('A', 1)]) as never)
    vi.mocked(api.castingVoices).mockResolvedValueOnce([voice('v1', { gender: 'female' })] as never).mockResolvedValueOnce([voice('v1', {})] as never)
    vi.mocked(api.castLabelSet).mockResolvedValue({} as never)
    const s = useCastingStore()
    await s.load()
    await s.setLabel('v1', 'gender', null)
    expect(api.castingVoices).toHaveBeenCalledTimes(2)
    expect(s.voices[0].mine).toEqual({})
  })
})
