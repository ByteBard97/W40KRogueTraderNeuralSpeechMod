import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, api } from '../api/client'
import { useToasts } from '../composables/useToasts'
import { entryOf, slot, summaryOf } from '../test-utils/poolFixtures'
import { useNavCountsStore } from './navCounts'
import { slotCheck, usePoolsStore } from './pools'

vi.mock('../api/client', async (orig) => ({
  ...(await orig<typeof import('../api/client')>()),
  api: {
    pools: vi.fn(), poolQueue: vi.fn(), poolsRebuild: vi.fn(), poolOverride: vi.fn(), poolRestore: vi.fn(), poolMerge: vi.fn(), poolUnmerge: vi.fn(),
    poolCreateSlot: vi.fn(), poolRename: vi.fn(), poolSpotRecord: vi.fn(),
  },
}))

const slots = [slot('male_human', 'Male human'), slot('female_human', 'Female human', { spot: { checked: 10, wrong: 0 } }), slot('old', 'Old', { spot: { checked: 10, wrong: 2 } })]
const A = entryOf('a')
const B = entryOf('b', { to: 'narrator', slot: null })

async function loaded() {
  vi.mocked(api.pools).mockResolvedValue(summaryOf(slots))
  vi.mocked(api.poolQueue).mockResolvedValue([A, B])
  const s = usePoolsStore()
  await s.load()
  return s
}

describe('pools store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); useToasts().clear() })

  it('loads the summary and queue and feeds the nav badge', async () => {
    const s = await loaded()
    expect(s.summary?.total).toBe(100)
    expect(s.queue).toHaveLength(2)
    expect(useNavCountsStore().pools).toBe(2)
  })

  it('treats a 404 as not built, not as an error', async () => {
    vi.mocked(api.pools).mockRejectedValue(new ApiRequestError(404, 'not built'))
    const s = usePoolsStore()
    await s.load()
    expect(s.notBuilt).toBe(true)
    expect(s.error).toBeNull()
  })

  it('reports other load failures', async () => {
    vi.mocked(api.pools).mockRejectedValue(new Error('boom'))
    const s = usePoolsStore()
    await s.load()
    expect(s.error).toBe('boom')
    expect(s.notBuilt).toBe(false)
  })

  it('classifies slots for the spot-check dot and tile', async () => {
    const s = await loaded()
    expect(slots.map(slotCheck)).toEqual(['unchecked', 'clean', 'wrong'])
    expect(s.checkedSlots).toBe(1)
    expect(s.nextUnchecked?.id).toBe('male_human')
  })

  it('accepts an entry and offers Undo that restores the previous routes', async () => {
    const s = await loaded()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3, undo: { previous: { g1: { to: 'narrator' } } } })
    vi.mocked(api.poolRestore).mockResolvedValue({ changed: 3 })
    await s.accept(A)
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a' })
    const t = useToasts().toasts.value[0]
    expect(t.message).toBe('Accepted Name a → Male human · 3 lines')
    expect(t.action?.key).toBe('Z')
    expect(s.handled).toBe(1)
    t.action!.run()
    await vi.waitFor(() => expect(api.poolRestore).toHaveBeenCalledWith({ g1: { to: 'narrator' } }))
    await vi.waitFor(() => expect(s.handled).toBe(0))
  })

  it('shows a plain toast when the server sends no undo data', async () => {
    const s = await loaded()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 1 })
    await s.accept(A)
    expect(useToasts().toasts.value[0].action).toBeUndefined()
  })

  it('shows an error toast and keeps the entry when an override fails', async () => {
    const s = await loaded()
    vi.mocked(api.poolOverride).mockRejectedValue(new Error('refused'))
    expect(await s.accept(A)).toBe(false)
    expect(useToasts().toasts.value[0]).toMatchObject({ kind: 'err', message: 'refused' })
    expect(s.handled).toBe(0)
  })

  it('cannot accept a group without a roster entry', async () => {
    const s = await loaded()
    expect(await s.accept(entryOf('x', { entry: null }))).toBe(false)
    expect(api.poolOverride).not.toHaveBeenCalled()
  })

  it('moves an entry to the chosen target', async () => {
    const s = await loaded()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3 })
    s.setChoice(A, 'slot:female_human')
    await s.moveChosen(A)
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a', to: 'slot', slot: 'female_human' })
    expect(useToasts().toasts.value[0].message).toContain('Moved Name a → Female human')
  })

  it('opens the new-voice form instead of moving when "New designed voice" is chosen', async () => {
    const s = await loaded()
    s.setChoice(A, '__new__')
    expect(s.creating).toBe('a')
    expect(await s.moveChosen(A)).toBe(false)
    expect(api.poolOverride).not.toHaveBeenCalled()
  })

  it('creates a voice, then moves the entry into it', async () => {
    const s = await loaded()
    vi.mocked(api.poolCreateSlot).mockResolvedValue(slot('custom_boss', 'Boss', { custom: true }))
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3 })
    s.setChoice(A, '__new__')
    await s.moveToNewVoice(A, { name: 'Boss', gender: 'male' })
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a', to: 'slot', slot: 'custom_boss' })
    expect(s.creating).toBeNull()
  })

  it('does not move when creating the voice fails (name taken)', async () => {
    const s = await loaded()
    vi.mocked(api.poolCreateSlot).mockRejectedValue(new ApiRequestError(409, 'name taken'))
    expect(await s.moveToNewVoice(A, { name: 'Boss', gender: 'male' })).toBeNull()
    expect(api.poolOverride).not.toHaveBeenCalled()
    expect(useToasts().toasts.value[0].message).toBe('name taken')
  })

  it('skips an entry to the end of the queue without saving anything', async () => {
    const s = await loaded()
    s.skip(A)
    expect(s.ordered.map((e) => e.key)).toEqual(['b', 'a'])
    s.skip(B)
    expect(s.ordered.map((e) => e.key)).toEqual(['a', 'b'])
    expect(api.poolOverride).not.toHaveBeenCalled()
  })

  it('moves the cursor within bounds', async () => {
    const s = await loaded()
    s.moveCursor(5)
    expect(s.current?.key).toBe('b')
    s.moveCursor(-9)
    expect(s.current?.key).toBe('a')
  })

  it('merges a slot and Undo unmerges it', async () => {
    const s = await loaded()
    vi.mocked(api.poolMerge).mockResolvedValue({ changed: 10 })
    vi.mocked(api.poolUnmerge).mockResolvedValue({ changed: 10 })
    await s.merge('male_human', 'female_human')
    const t = useToasts().toasts.value[0]
    expect(t.message).toBe('Merged Male human into Female human · 10 lines moved')
    t.action!.run()
    await vi.waitFor(() => expect(api.poolUnmerge).toHaveBeenCalledWith('male_human'))
  })

  it('reports a failed merge', async () => {
    const s = await loaded()
    vi.mocked(api.poolMerge).mockRejectedValue(new Error('needs two slots'))
    await s.merge('male_human', 'male_human')
    expect(useToasts().toasts.value[0].message).toContain('needs two slots')
  })

  it('reports a failed Undo (merge made before undo data existed)', async () => {
    const s = await loaded()
    vi.mocked(api.poolUnmerge).mockRejectedValue(new ApiRequestError(404, 'no recorded merge'))
    await s.unmerge('male_human', 'Male human')
    expect(useToasts().toasts.value[0]).toMatchObject({ kind: 'err', message: 'Undo failed: no recorded merge' })
  })

  it('records a spot check and says when something was wrong', async () => {
    const s = await loaded()
    vi.mocked(api.poolSpotRecord).mockResolvedValue({ checked: 10, wrong: 1 })
    await s.recordSpot('male_human', { g: false })
    expect(useToasts().toasts.value[0].message).toContain('1 wrong')
  })

  it('rebuilds, resets the session and confirms', async () => {
    const s = await loaded()
    vi.mocked(api.poolsRebuild).mockResolvedValue(summaryOf(slots))
    s.skip(A)
    await s.rebuild()
    expect(s.skipped).toEqual([])
    expect(useToasts().toasts.value[0].message).toContain('Routing rebuilt')
  })

  it('progress counts handled entries against the starting queue', async () => {
    const s = await loaded()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3 })
    vi.mocked(api.poolQueue).mockResolvedValue([B])
    await s.accept(A)
    expect(s.reviewFraction).toBe(0.5)
  })
})
