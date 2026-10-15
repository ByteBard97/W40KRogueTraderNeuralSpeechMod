import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useRtVoicesStore } from './rtVoices'

vi.mock('../api/client', () => ({ api: { rtVoices: vi.fn(), rtVoiceLabelSet: vi.fn() } }))

const SCHEMA = [{ key: 'gender', label: 'Gender', kind: 'single', options: ['male', 'female'], required: true }, { key: 'processing', label: 'Processing', kind: 'single', options: ['natural', 'processed'], required: true }]
const voice = (slug: string) => ({ slug, name: slug, lines: 10, minutes: 1, gender: 'unclear', f0: null, non_human: false, refs: [], used_by: [], labels: {}, mine: {}, complete: false })

describe('rt voices store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.rtVoices).mockResolvedValue({ voices: [voice('Pasqal'), voice('Abelard')], schema: SCHEMA, progress: { total: 2, complete: 0, started: 0 } } as never)
  })

  it('loads the speakers, the schema and the progress', async () => {
    const s = useRtVoicesStore()
    await s.load()
    expect(s.voices.map((v) => v.slug)).toEqual(['Pasqal', 'Abelard'])
    expect(s.schema).toHaveLength(2)
    expect(s.progress?.total).toBe(2)
  })

  it('shows a label at once, marks the voice done when the required labels are set, and keeps what the server returns', async () => {
    const s = useRtVoicesStore()
    await s.load()
    vi.mocked(api.rtVoiceLabelSet).mockImplementation(async (_slug, key, val) => ({ gender: 'male', [key]: val }) as never)
    await s.setLabel('Pasqal', 'gender', 'male')
    expect(s.voices[0].complete).toBe(false)
    await s.setLabel('Pasqal', 'processing', 'processed')
    expect(s.voices[0].complete).toBe(true)
    expect(api.rtVoiceLabelSet).toHaveBeenLastCalledWith('Pasqal', 'processing', 'processed')
    expect(s.voices[0].mine).toEqual({ gender: 'male', processing: 'processed' })
  })

  it('puts a label back and shows the problem when the server refuses it', async () => {
    const s = useRtVoicesStore()
    await s.load()
    vi.mocked(api.rtVoiceLabelSet).mockRejectedValue(new Error('processing has no option'))
    await s.setLabel('Pasqal', 'processing', 'shiny')
    expect(s.voices[0].mine).toEqual({})
    expect(s.error).toBe('processing has no option')
  })
})
