import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { MatchRowData } from '../../api/types'
import MatchDetail from './MatchDetail.vue'

const row = { id: 'C|a', conversation: 'Jail', entry: 'a', name: 'Harbinger of Aurora', label: null, gender: 'male', species: 'human', role: 'cultist', evidence: ['holds a rod'],
  lines: 2, samples: ['One.', 'Two.'], gaps: [true], speaker: 'Aurora', has_bank: false, speaker_lines: 1, game_gender: 'female',
  warning: 'the game tags Aurora as female on only 1 line', ambiguous_with: null, flagged: true, decision: '', effective: '', suggest: 'reject',
  suggest_reason: 'r', speaker_sample: null } as MatchRowData
const mk = (o: Partial<MatchRowData> = {}, hearing = false) => mount(MatchDetail, { props: { row: { ...row, ...o }, position: '1 of 25 flagged', hearing } })

describe('MatchDetail', () => {
  it('shows both sides, why it was flagged, the samples with a gap marker and the suggestion', () => {
    const t = mk().text()
    for (const s of ['Harbinger of Aurora', 'no bank', 'cultist', 'game gender female', '1 line', 'Why flagged', 'The game tags Aurora', 'One.', 'Two.', 'other speakers', 'holds a rod', 'Suggested: Reject', '1 of 25 flagged']) expect(t).toContain(s)
  })
  it('emits accept and reject and marks the chosen one pressed', async () => {
    const w = mk({ decision: 'accept' })
    const [acc, rej] = w.findAll('.judge button')
    expect(acc.attributes('aria-pressed')).toBe('true')
    expect(rej.attributes('aria-pressed')).toBe('false')
    await acc.trigger('click')
    await rej.trigger('click')
    expect(w.emitted('decide')).toEqual([['accept'], ['reject']])
  })
  it('disables Hear without a bank sample and enables it with one', async () => {
    expect(mk().find('.hear').attributes('disabled')).toBeDefined()
    const w = mk({ has_bank: true, speaker_sample: 'data/voices/a.wav' })
    expect(w.find('.hear').attributes('disabled')).toBeUndefined()
    await w.find('.hear').trigger('click')
    expect(w.emitted('hear')).toHaveLength(1)
  })
  it('hides the flag box and the suggestion for a clean match from an older server', () => {
    const w = mk({ warning: null, flagged: false, suggest: undefined })
    expect(w.text()).not.toContain('Why flagged')
    expect(w.text()).not.toContain('Suggested')
  })
})
