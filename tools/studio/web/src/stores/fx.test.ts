import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useFxStore } from './fx'
import { useNavCountsStore } from './navCounts'

vi.mock('../api/client', () => ({
  api: { fxLibrary: vi.fn(), fxLabels: vi.fn(), fxSaveLabels: vi.fn(), fxPreview: vi.fn(), fxWrite: vi.fn(), fxUsage: vi.fn(), fxDiff: vi.fn(), fxBackups: vi.fn(), fxRestore: vi.fn() },
}))

async function loaded(labels = { machine: ['Clean'], helmet: [] as string[] }) {
  vi.mocked(api.fxLibrary).mockResolvedValue([{ name: 'Clean' }, { name: 'Mine' }] as never)
  vi.mocked(api.fxLabels).mockResolvedValue(labels)
  const s = useFxStore()
  await s.load()
  return s
}

describe('fx store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.fxUsage).mockRejectedValue(new Error('404'))
    vi.mocked(api.fxDiff).mockRejectedValue(new Error('404'))
    vi.mocked(api.fxBackups).mockRejectedValue(new Error('404'))
    vi.mocked(api.fxPreview).mockResolvedValue({ lines: 3, speakers: 1, unmapped_labels: {}, sample: [] })
  })

  it('loads library and labels, and tolerates the new routes being absent', async () => {
    const s = await loaded()
    expect(s.library).toHaveLength(2)
    expect(s.labelNames).toEqual(['machine', 'helmet'])
    expect(s.diff).toBeNull()
    expect(s.usage).toBeNull()
    expect(s.error).toBeNull()
    expect(s.preview?.lines).toBe(3)
  })

  it('tracks edits per label, mirrors the count to the nav, and discards', async () => {
    const s = await loaded()
    expect(s.dirtyCount).toBe(0)
    s.add('helmet', 'Mine')
    s.add('helmet', 'Mine')
    s.add('machine', 'Mine')
    s.move('machine', 0, 1)
    expect(s.draft.machine).toEqual(['Mine', 'Clean'])
    expect(s.dirtyLabels).toEqual(['machine', 'helmet'])
    await Promise.resolve()
    expect(useNavCountsStore().fxUnsaved).toBe(2)
    s.remove('helmet', 0)
    expect(s.isDirty('helmet')).toBe(false)
    s.discard()
    expect(s.dirtyCount).toBe(0)
    expect(s.labels.machine).toEqual(['Clean'])
  })

  it('a reload keeps unsaved edits', async () => {
    const s = await loaded()
    s.add('helmet', 'Mine')
    await s.load()
    expect(s.draft.helmet).toEqual(['Mine'])
  })

  it('keeps the old labels and shows the server error when saving fails', async () => {
    vi.mocked(api.fxSaveLabels).mockRejectedValue(new Error('machine: every preset must be in the library'))
    const s = await loaded()
    s.add('machine', 'Nope')
    await s.saveLabels()
    expect(s.labels.machine).toEqual(['Clean'])
    expect(s.draft.machine).toEqual(['Clean', 'Nope'])
    expect(s.error).toMatch(/library/)
  })

  it('writeMap saves edited labels first, then writes, then refreshes the diff', async () => {
    const s = await loaded()
    s.add('helmet', 'Mine')
    vi.mocked(api.fxSaveLabels).mockResolvedValue({ machine: ['Clean'], helmet: ['Mine'] })
    vi.mocked(api.fxWrite).mockResolvedValue({ path: 'data/fx_lab/assignments.json', lines: 3, speakers: 1, backup: 'assignments.b.bak.json' })
    vi.mocked(api.fxDiff).mockResolvedValue({ rows: [], changed: 0, unmapped_labels: {}, file_mtime: 1 })
    const w = await s.writeMap()
    expect(api.fxSaveLabels).toHaveBeenCalledWith({ machine: ['Clean'], helmet: ['Mine'] })
    expect(w?.backup).toBe('assignments.b.bak.json')
    expect(s.dirtyCount).toBe(0)
    expect(s.diff?.changed).toBe(0)
  })

  it('writeMap stops when the label save fails', async () => {
    const s = await loaded()
    s.add('helmet', 'Mine')
    vi.mocked(api.fxSaveLabels).mockRejectedValue(new Error('no'))
    expect(await s.writeMap()).toBeUndefined()
    expect(api.fxWrite).not.toHaveBeenCalled()
  })

  it('writeMap with a clean map skips the label save', async () => {
    const s = await loaded()
    vi.mocked(api.fxWrite).mockResolvedValue({ path: 'p', lines: 1, speakers: 0 })
    await s.writeMap()
    expect(api.fxSaveLabels).not.toHaveBeenCalled()
  })

  it('restore reloads', async () => {
    const s = await loaded()
    vi.mocked(api.fxRestore).mockResolvedValue({ restored: 'b', kind: 'assignments', path: 'p', backup: null })
    await s.restore('b')
    expect(api.fxRestore).toHaveBeenCalledWith('b')
    expect(api.fxLabels).toHaveBeenCalledTimes(2)
  })
})
