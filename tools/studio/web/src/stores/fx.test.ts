import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useFxStore } from './fx'

vi.mock('../api/client', () => ({ api: { fxLibrary: vi.fn(), fxLabels: vi.fn(), fxSaveLabels: vi.fn(), fxPreview: vi.fn(), fxWrite: vi.fn() } }))

describe('fx store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('loads the library and labels', async () => {
    vi.mocked(api.fxLibrary).mockResolvedValue([{ name: 'Clean' }] as never)
    vi.mocked(api.fxLabels).mockResolvedValue({ machine: ['Clean'] })
    const s = useFxStore()
    await s.load()
    expect(s.library).toHaveLength(1)
    expect(s.labels.machine).toEqual(['Clean'])
  })

  it('keeps the old labels and shows the server error when saving fails', async () => {
    vi.mocked(api.fxSaveLabels).mockRejectedValue(new Error('machine: every preset must be in the library'))
    const s = useFxStore()
    s.labels = { machine: ['Clean'] }
    await s.saveLabels({ machine: ['Nope'] })
    expect(s.labels.machine).toEqual(['Clean'])
    expect(s.error).toMatch(/library/)
  })

  it('saving labels clears a stale preview; write reports the path', async () => {
    vi.mocked(api.fxSaveLabels).mockResolvedValue({ machine: [] })
    vi.mocked(api.fxPreview).mockResolvedValue({ lines: 3, speakers: 0, unmapped_labels: {}, sample: [] })
    vi.mocked(api.fxWrite).mockResolvedValue({ path: 'data/fx_lab/assignments.json', lines: 3, speakers: 0 })
    const s = useFxStore()
    await s.loadPreview()
    expect(s.preview?.lines).toBe(3)
    await s.write()
    expect(s.written?.path).toContain('assignments.json')
    await s.saveLabels({ machine: [] })
    expect(s.preview).toBeNull()
  })
})
