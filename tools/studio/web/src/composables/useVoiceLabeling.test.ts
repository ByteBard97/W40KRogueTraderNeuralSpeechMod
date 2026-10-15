import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useCastingStore } from '../stores/casting'
import { useVoiceLabeling } from './useVoiceLabeling'

vi.mock('../api/client', () => ({ api: { casting: vi.fn(), castingVoices: vi.fn(), castLabels: vi.fn(), castLabelSet: vi.fn() } }))
vi.mock('./useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), stop: vi.fn(), playing: { value: null } }) }))

const SCHEMA = [{ key: 'gender', label: 'Gender', kind: 'single', options: ['male', 'female'], required: true }, { key: 'age', label: 'Age', kind: 'single', options: ['youth', 'old'], required: true },
  { key: 'reserve', label: 'Use', kind: 'single', options: ['free', 'do not use'], required: false }]
const voice = (slug: string, lines: number, mine: Record<string, string> = {}) => ({
  slug, name: slug, lines, minutes: 1, gender: 'male', f0: null, non_human: false, refs: [], used_by: [], labels: { ...mine }, mine, complete: false })

describe('useVoiceLabeling', () => {
  beforeEach(async () => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.casting).mockResolvedValue({ characters: [], total: 0, assigned: 0, portraits: [] } as never)
    vi.mocked(api.castingVoices).mockResolvedValue([voice('a', 300), voice('b', 200), voice('c', 100)] as never)
    vi.mocked(api.castLabels).mockResolvedValue({ schema: SCHEMA, progress: { total: 3, complete: 0, started: 0 } } as never)
    vi.mocked(api.castLabelSet).mockImplementation(async (slug, key, val) => ({ ...(slug === 'a' ? { gender: 'male' } : {}), [key]: val }) as never)
    await useCastingStore().load()
  })

  it('moves to the next voice in the list when the last required label is set', async () => {
    const L = useVoiceLabeling()
    L.select('a')
    await L.label('gender', 'male')
    expect(L.current.value?.slug).toBe('a')                   // not done yet: stay
    await L.label('age', 'old')
    expect(L.current.value?.slug).toBe('b')                   // done: on to the next, which is the one after it in the list
  })

  it('moves on from where you were, not from the top of the list', async () => {
    const L = useVoiceLabeling()
    L.select('b')
    await L.label('gender', 'male')
    await L.label('age', 'old')
    expect(L.current.value?.slug).toBe('c')
  })

  it('does not move on when the option is off', async () => {
    const L = useVoiceLabeling()
    L.autoAdvance.value = false
    L.select('a')
    await L.label('gender', 'male')
    await L.label('age', 'old')
    expect(L.current.value?.slug).toBe('a')
  })

  it('x marks the voice do not use and moves on even with auto advance off; again it clears the mark', async () => {
    const L = useVoiceLabeling()
    L.autoAdvance.value = false
    L.select('a')
    await L.toggleSkip()
    expect(api.castLabelSet).toHaveBeenCalledWith('a', 'reserve', 'do not use')
    expect(L.current.value?.slug).toBe('b')
    L.select('a')
    vi.mocked(api.castingVoices).mockResolvedValue([{ ...voice('a', 300, { reserve: 'do not use' }), complete: true }, voice('b', 200), voice('c', 100)] as never)
    await useCastingStore().load()
    await L.toggleSkip()
    expect(api.castLabelSet).toHaveBeenLastCalledWith('a', 'reserve', null)
    expect(L.current.value?.slug).toBe('a')                   // undoing stays put
  })

  it('x does nothing on a label set that has no use label, like the Rogue Trader voices', async () => {
    vi.mocked(api.castLabels).mockResolvedValue({ schema: SCHEMA.filter((d) => d.key !== 'reserve'), progress: { total: 3, complete: 0, started: 0 } } as never)
    await useCastingStore().load()
    const L = useVoiceLabeling()
    L.select('a')
    await L.toggleSkip()
    expect(api.castLabelSet).not.toHaveBeenCalled()
    expect(L.current.value?.slug).toBe('a')
  })
})
