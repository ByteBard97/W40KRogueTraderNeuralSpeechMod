import { describe, expect, it } from 'vitest'
import type { MatchRowData } from '../api/types'
import { decisionLabel, entryName, plural, whyFlagged } from './matchText'

const row = (o: Partial<MatchRowData> = {}) => ({ name: 'Idira', label: 'witch', entry: 'e', speaker: 'Idira', has_bank: true, warning: null, ambiguous_with: null, decision: '', ...o }) as MatchRowData

describe('matchText', () => {
  it('pluralises and names the entry', () => {
    expect(plural(1, 'line')).toBe('1 line')
    expect(plural(0, 'line')).toBe('0 lines')
    expect(entryName(row({ name: null }))).toBe('witch')
  })
  it('composes why a match was flagged from the warning and the homonyms', () => {
    expect(whyFlagged(row())).toBe('')
    expect(whyFlagged(row({ warning: 'the game tags Aurora as female on only 1 line' }))).toBe('The game tags Aurora as female on only 1 line.')
    expect(whyFlagged(row({ ambiguous_with: ['Idira the Insidious'] }))).toBe('Also matches Idira the Insidious. Accepting uses the Idira bank.')
    expect(whyFlagged(row({ ambiguous_with: ['X'], has_bank: false }))).toBe('Also matches X.')
  })
  it('labels the decision, falling back to the suggestion', () => {
    expect(decisionLabel(row({ decision: 'accept' }))).toBe('Accepted')
    expect(decisionLabel(row({ decision: 'reject' }))).toBe('Rejected')
    expect(decisionLabel(row({ suggest: 'reject' }))).toBe('suggest reject')
    expect(decisionLabel(row())).toBe('')
  })
})
