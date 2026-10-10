import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { MatchRowData } from '../../api/types'
import MatchRow from './MatchRow.vue'

const row = { id: 'C|a', conversation: 'IdiraLab', entry: 'a', name: 'Idira', label: 'witch', lines: 1, speaker: 'Idira the Insidious', has_bank: true,
  flagged: true, decision: '', effective: '', suggest: 'accept' } as MatchRowData

describe('MatchRow', () => {
  it('shows who, the speaker, the source with a singular line count and the suggestion', () => {
    const t = mount(MatchRow, { props: { row, selected: false } }).text()
    for (const s of ['Idira', 'Idira the Insidious', 'IdiraLab · 1 line', 'suggest accept']) expect(t).toContain(s)
    expect(t).not.toContain('1 lines')
  })
  it('shows the decision instead of the suggestion, with a named dot', () => {
    const w = mount(MatchRow, { props: { row: { ...row, decision: 'reject' }, selected: false } })
    expect(w.text()).toContain('Rejected')
    expect(w.find('[role=img]').attributes('aria-label')).toBe('Rejected')
  })
  it('marks the selected row and emits select', async () => {
    const w = mount(MatchRow, { props: { row, selected: true } })
    expect(w.attributes('aria-current')).toBe('true')
    await w.trigger('click')
    expect(w.emitted('select')).toHaveLength(1)
  })
})
