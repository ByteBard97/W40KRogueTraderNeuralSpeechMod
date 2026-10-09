import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MatchRow from './MatchRow.vue'

const row = { id: 'C|a', conversation: 'C', entry: 'a', name: 'Heinrix', label: 'The inquisitor', gender: 'female', species: 'human', role: 'ally',
  evidence: ['said x'], lines: 4, samples: ['One.', 'Two.'], gaps: [true], speaker: 'Heinrix', has_bank: true, speaker_lines: 40, game_gender: 'male',
  warning: 'game tags Heinrix as male on only 5 line(s)', ambiguous_with: ['Heinrix Two'], flagged: true, decision: '', effective: '' }

describe('MatchRow', () => {
  it('shows the match, the warnings, the evidence and the samples with a gap marker', () => {
    const t = mount(MatchRow, { props: { row: row as never } }).text()
    for (const s of ['Heinrix', 'bank', 'game tags Heinrix as male', 'also matches: Heinrix Two', 'said x', 'One.', 'Two.', 'other speakers']) expect(t).toContain(s)
  })

  it('emits the chosen decision', async () => {
    const w = mount(MatchRow, { props: { row: row as never } })
    await w.find('[data-decision]').setValue('reject')
    expect(w.emitted('decide')![0]).toEqual(['reject'])
  })

  it('marks flagged rows and shows no-bank rows differently', () => {
    expect(mount(MatchRow, { props: { row: row as never } }).classes()).toContain('flag')
    const w = mount(MatchRow, { props: { row: { ...row, flagged: false, has_bank: false, warning: null, ambiguous_with: null } as never } })
    expect(w.classes()).not.toContain('flag')
    expect(w.text()).toContain('no bank')
  })
})
