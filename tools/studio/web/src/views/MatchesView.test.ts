import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { matches: vi.fn(), matchDecision: vi.fn() } }))

import MatchesView from './MatchesView.vue'

const row = (id: string) => ({ id, conversation: 'C', entry: id, name: id, label: id, gender: 'male', species: 'human', role: null, evidence: [], lines: 1, samples: ['Hi.'], gaps: [],
  speaker: 'Heinrix', has_bank: true, speaker_lines: 40, game_gender: 'male', warning: null, ambiguous_with: null, flagged: false, decision: '', effective: 'accept' })
const page = (ids: string[], total: number) => ({ total, offset: 0, limit: 50, counts: { flagged: 1, bank: 2, nobank: 3, undecided: 4 }, items: ids.map(row) })

describe('MatchesView', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('lists matches with the counts line and offers more', async () => {
    vi.mocked(api.matches).mockResolvedValueOnce(page(['a', 'b'], 3) as never).mockResolvedValueOnce(page(['c'], 3) as never)
    const w = mount(MatchesView)
    await flushPromises()
    expect(w.text()).toContain('flagged 1')
    expect(w.findAll('.row')).toHaveLength(2)
    await w.find('[data-more]').trigger('click')
    await flushPromises()
    expect(w.findAll('.row')).toHaveLength(3)
    expect(w.find('[data-more]').exists()).toBe(false)
  })

  it('saves a decision from a row', async () => {
    vi.mocked(api.matches).mockResolvedValue(page(['a'], 1) as never)
    vi.mocked(api.matchDecision).mockResolvedValue({ pools_rebuilt: false })
    const w = mount(MatchesView)
    await flushPromises()
    await w.find('[data-decision]').setValue('reject')
    await flushPromises()
    expect(api.matchDecision).toHaveBeenCalledWith('a', 'reject')
    expect(w.text()).toContain('Saved.')
  })

  it('shows an empty state and an error message', async () => {
    vi.mocked(api.matches).mockResolvedValue(page([], 0) as never)
    expect(mount(MatchesView).text()).toBeDefined()
    const w = mount(MatchesView)
    await flushPromises()
    expect(w.text()).toMatch(/no matches for these filters/i)
    vi.mocked(api.matches).mockRejectedValue(new Error('boom'))
    const w2 = mount(MatchesView)
    await flushPromises()
    expect(w2.text()).toContain('boom')
  })
})
