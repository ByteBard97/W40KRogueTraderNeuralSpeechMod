import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useAssignmentsStore } from './assignments'

vi.mock('../api/client', () => ({ api: { assignments: vi.fn(), assignmentsRun: vi.fn(), assignmentOverride: vi.fn(), castingVoices: vi.fn(), assignmentsRegisterPreview: vi.fn(), assignmentsRegister: vi.fn() } }))
import { useToasts } from '../composables/useToasts'

const item = (key: string, over: Record<string, unknown> = {}) => ({
  key, kind: 'character', name: key, gender: 'male', species: 'human', age: null, role: 'guard', description: '', lines: 10, conversation: null,
  status: 'assigned', bg3: 'v1', voice_name: 'Voice One', alts: [], samples: [], research: null, ...over })
const voice = (slug: string, name: string) => ({ slug, name, lines: 100, minutes: 1, gender: 'male', f0: null, non_human: false, refs: [{ wav: `data/${slug}.wav`, text: 't', seconds: 5 }], used_by: [], labels: {}, mine: {}, complete: true })

describe('assignments store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    vi.mocked(api.assignments).mockResolvedValue({ generated_at: 'x', summary: {}, items: [
      item('a', { name: 'Guard Hobb', lines: 50 }), item('g:b', { kind: 'group', name: 'Sailor', lines: 5 }), item('c', { status: 'needs_info', bg3: undefined, name: 'Ghost', lines: 2 }),
      item('d', { owner: true, name: 'Mine', lines: 1 })] } as never)
    vi.mocked(api.castingVoices).mockResolvedValue([voice('v1', 'Voice One'), voice('v2', 'Voice Two')] as never)
  })

  it('filters by status, by kind and by search, keeping the order the server gave', async () => {
    const s = useAssignmentsStore()
    await s.load()
    expect(s.visible.map((i) => i.key)).toEqual(['a', 'g:b', 'c', 'd'])
    s.status = 'needs_info'
    expect(s.visible.map((i) => i.key)).toEqual(['c'])
    s.status = 'mine'
    expect(s.visible.map((i) => i.key)).toEqual(['d'])
    s.status = 'all'; s.kind = 'group'
    expect(s.visible.map((i) => i.key)).toEqual(['g:b'])
    s.kind = 'all'; s.query = 'hobb'
    expect(s.visible.map((i) => i.key)).toEqual(['a'])
  })

  it('selects the first visible item until one is chosen and finds the voice for its clip', async () => {
    const s = useAssignmentsStore()
    await s.load()
    expect(s.current?.key).toBe('a')
    expect(s.voiceOf(s.current)?.refs[0].wav).toBe('data/v1.wav')
    s.select('g:b')
    expect(s.current?.key).toBe('g:b')
  })

  it('an override is sent and the page is reloaded; a failure is shown, not thrown', async () => {
    const s = useAssignmentsStore()
    await s.load()
    vi.mocked(api.assignmentOverride).mockResolvedValue({})
    await s.override('a', 'v2')
    expect(api.assignmentOverride).toHaveBeenCalledWith('a', 'v2')
    expect(api.assignments).toHaveBeenCalledTimes(2)
    vi.mocked(api.assignmentOverride).mockRejectedValue(new Error('unknown voice'))
    await s.override('a', 'zzz')
    expect(s.error).toBe('unknown voice')
  })

  const preview = { counts: { assigned: 3, not_assigned: 1, add: 2, update: 0, unchanged: 0, skipped: 1, processed: 1 }, items: [], skipped: [{ key: 'x', bg3: 'v1', reason: 'no clip' }] }

  it('register: the preview is fetched first, cancel drops it without writing', async () => {
    const s = useAssignmentsStore()
    vi.mocked(api.assignmentsRegisterPreview).mockResolvedValue(preview as never)
    await s.previewRegister()
    expect(s.registerPreview?.counts.add).toBe(2)
    s.cancelRegister()
    expect(s.registerPreview).toBeNull()
    expect(api.assignmentsRegister).not.toHaveBeenCalled()
  })

  it('register: confirming writes once, clears the preview and toasts the result', async () => {
    const s = useAssignmentsStore()
    useToasts().clear()
    vi.mocked(api.assignmentsRegisterPreview).mockResolvedValue(preview as never)
    vi.mocked(api.assignmentsRegister).mockResolvedValue({ registered: ['a', 'b'], unchanged: 0, skipped: [{ key: 'x', bg3: 'v1', reason: 'r' }], backup: 'prompts.1.bak.json' })
    await s.previewRegister()
    await Promise.all([s.confirmRegister(), s.confirmRegister()])
    expect(api.assignmentsRegister).toHaveBeenCalledTimes(1)
    expect(s.registerPreview).toBeNull()
    expect(useToasts().toasts.value[0].message).toContain('Registered 2 voices, 1 skipped')
  })

  it('register: a failure keeps the preview and shows an error toast', async () => {
    const s = useAssignmentsStore()
    useToasts().clear()
    vi.mocked(api.assignmentsRegisterPreview).mockResolvedValue(preview as never)
    vi.mocked(api.assignmentsRegister).mockRejectedValue(new Error('disk full'))
    await s.previewRegister()
    await s.confirmRegister()
    expect(s.registerPreview).not.toBeNull()
    expect(s.error).toBe('disk full')
    expect(useToasts().toasts.value[0].kind).toBe('err')
  })
})
