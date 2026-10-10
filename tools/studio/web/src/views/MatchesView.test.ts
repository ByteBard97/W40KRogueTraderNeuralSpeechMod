import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useGlobalAudio } from '../composables/globalAudio'
import { useShortcutOverlay } from '../composables/useShortcuts'
import { useToasts } from '../composables/useToasts'

vi.mock('../api/client', () => ({ api: { matches: vi.fn(), matchDecision: vi.fn(), matchesRebuild: vi.fn() } }))

import MatchesView from './MatchesView.vue'

const row = (id: string, o = {}) => ({ id, conversation: `Conv_${id}`, entry: id, name: `Name ${id}`, label: id, gender: 'male', species: 'human', role: null, evidence: [], lines: 2, samples: ['Hi.'], gaps: [],
  speaker: 'Heinrix', has_bank: true, speaker_lines: 40, game_gender: 'male', warning: 'tag mismatch', ambiguous_with: null, flagged: true, decision: '', effective: '',
  suggest: 'reject', suggest_reason: 'x', speaker_sample: 'data/voices/h.wav', ...o })
const counts = { flagged: 3, bank: 0, nobank: 0, undecided: 3, total: 9, accepted: 1, rejected: 1, reviewed: 2, unreviewed: 7, flagged_unreviewed: 3 }
const page = (ids: string[], total = ids.length) => ({ total, offset: 0, limit: 50, counts, items: ids.map((i) => row(i)) })
const press = (key: string) => document.dispatchEvent(new KeyboardEvent('keydown', { key, bubbles: true, cancelable: true }))
let mounted: ReturnType<typeof mount> | null = null
const mountView = async () => { mounted = mount(MatchesView, { attachTo: document.body }); await flushPromises(); return mounted }

describe('MatchesView', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks(); useToasts().clear(); useGlobalAudio().stop() })
  afterEach(() => { mounted?.unmount(); mounted = null })

  it('asks for flagged, not reviewed matches and shows progress, filters with counts, queue and detail', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a', 'b', 'c']) as never)
    const w = await mountView()
    expect(vi.mocked(api.matches).mock.calls[0][0]).toMatchObject({ group: 'flagged', state: 'unreviewed' })
    expect(w.text()).toContain('2 / 9')
    expect(w.text()).toContain('Flagged 3')
    expect(w.findAll('.q-row')).toHaveLength(3)
    expect(w.find('.from').text()).toBe('Name a')
    expect(w.text()).toContain('1 of 3 flagged')
    expect(w.find('.list-head').text()).toContain('Flagged, not reviewed')
  })

  it('A accepts the current match, moves on, and offers an undo that restores it', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a', 'b']) as never)
    vi.mocked(api.matchDecision).mockResolvedValue({ pools_rebuilt: false, pools_stale: true })
    const w = await mountView()
    press('a')
    await flushPromises()
    expect(api.matchDecision).toHaveBeenCalledWith('a', 'accept', false)
    expect(w.find('.from').text()).toBe('Name b')
    expect(w.text()).toContain('3 / 9')
    const toast = useToasts().toasts.value[0]
    expect(toast.message).toContain('Accepted Name a → Heinrix')
    toast.action!.run()
    await flushPromises()
    expect(api.matchDecision).toHaveBeenLastCalledWith('a', '', false)
    expect(w.find('.from').text()).toBe('Name a')
    expect(w.text()).toContain('2 / 9')
  })

  it('R rejects, J and K move, N jumps to the next unreviewed', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a', 'b', 'c']) as never)
    vi.mocked(api.matchDecision).mockResolvedValue({ pools_rebuilt: false })
    const w = await mountView()
    press('j'); await flushPromises()
    expect(w.find('.from').text()).toBe('Name b')
    press('k'); await flushPromises()
    expect(w.find('.from').text()).toBe('Name a')
    press('r'); await flushPromises()
    expect(api.matchDecision).toHaveBeenCalledWith('a', 'reject', false)
    expect(w.find('.from').text()).toBe('Name b')
    press('n'); await flushPromises()
    expect(w.find('.from').text()).toBe('Name c')
  })

  it('leaves keys alone while typing in a field', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a']) as never)
    await mountView()
    const input = document.querySelector('input') as HTMLInputElement
    input.focus()
    input.dispatchEvent(new KeyboardEvent('keydown', { key: 'a', bubbles: true }))
    expect(api.matchDecision).not.toHaveBeenCalled()
  })

  it('Space plays the proposed speaker sample through the global player', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a']) as never)
    await mountView()
    const play = vi.spyOn(HTMLMediaElement.prototype, 'play').mockResolvedValue()
    press(' ')
    expect(useGlobalAudio().state.id).toBe('data/voices/h.wav')
    expect(play).toHaveBeenCalled()
    play.mockRestore()
  })

  it('registers its shortcuts for the overlay', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a']) as never)
    await mountView()
    expect(useShortcutOverlay().page.value?.title).toBe('Matches')
  })

  it('shows more rows on request', async () => {
    vi.mocked(api.matches).mockResolvedValueOnce(page(['a', 'b'], 3) as never).mockResolvedValueOnce(page(['c'], 3) as never)
    const w = await mountView()
    await w.find('[data-more]').trigger('click')
    await flushPromises()
    expect(w.findAll('.q-row')).toHaveLength(3)
    expect(w.find('[data-more]').exists()).toBe(false)
  })

  it('shows an empty state with a way out, and an error with retry', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([], 0) as never)
    const w = await mountView()
    expect(w.text()).toMatch(/nothing left to review/i)
    await w.find('.empty button').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.matches).mock.calls.at(-1)![0]).toMatchObject({ group: '', state: '' })
    mounted?.unmount()
    vi.mocked(api.matches).mockRejectedValue(new Error('boom'))
    const w2 = await mountView()
    expect(w2.text()).toContain('boom')
    expect(w2.text()).toContain('Retry')
  })
})
