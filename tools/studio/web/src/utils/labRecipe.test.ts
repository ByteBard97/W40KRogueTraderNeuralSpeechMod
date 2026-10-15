import { describe, expect, it } from 'vitest'
import type { LabLine, LabRecipe } from '../api/labTypes'
import { buildRenderBody, carrierSentence, cleanRecipe, filterLines, flagTone, recipeSummary, seedsFor, sortLines, variantLabel, variantRecipe } from './labRecipe'
import { recipeFixture } from '../test-utils/labFixtures'

const line = (guid: string, order: number, crest: number | null, flag: 'overdriven' | 'clipped' | null = null, text = guid): LabLine => ({
  guid, cue: 'c', order, text, chars: text.length, instruct: null, ref: { wav: 'r.wav' },
  current: crest === null ? null : { wav: `${guid}.wav`, seconds: 2, peak_db: -1, crest_db: crest, clip_runs: 0, flag },
})

describe('sortLines', () => {
  const lines = [line('a', 3, 14), line('b', 1, 9, 'overdriven'), line('c', 2, null), line('d', 0, 12)]
  it('keeps line order', () => expect(sortLines(lines, 'order').map((l) => l.guid)).toEqual(['d', 'b', 'c', 'a']))
  it('puts the lowest crest first and unrendered lines last', () => expect(sortLines(lines, 'worst').map((l) => l.guid)).toEqual(['b', 'd', 'a', 'c']))
  it('does not mutate the input', () => {
    const copy = [...lines]
    sortLines(lines, 'worst')
    expect(lines).toEqual(copy)
  })
})

describe('filterLines', () => {
  const lines = [line('a', 0, 14, null, 'Hello there'), line('b', 1, 9, 'overdriven', 'Von Valancius'), line('c', 2, 15, 'clipped', 'Clipped one')]
  it('shows flagged lines only', () => expect(filterLines(lines, 'flagged', '').map((l) => l.guid)).toEqual(['b', 'c']))
  it('searches text, case-insensitively, together with the filter', () => {
    expect(filterLines(lines, 'all', 'VALANCIUS').map((l) => l.guid)).toEqual(['b'])
    expect(filterLines(lines, 'flagged', 'hello')).toEqual([])
  })
  it('finds em-dash lines when two hyphens or either dash are typed', () => {
    const d = [line('a', 0, 14, null, 'Well — fine'), line('b', 1, 14, null, 'Tech-Priest'), line('c', 2, 14, null, 'One – two')]
    expect(filterLines(d, 'all', '--').map((l) => l.guid)).toEqual(['a', 'c'])
    expect(filterLines(d, 'all', '—').map((l) => l.guid)).toEqual(['a', 'c'])
    expect(filterLines(d, 'all', '-').map((l) => l.guid)).toEqual(['b'])
  })
})

describe('flagTone', () => {
  it('is red for overdriven or a low crest, amber for clipped, ok otherwise', () => {
    expect(flagTone({ flag: 'overdriven', crest_db: 9 })).toBe('bad')
    expect(flagTone({ flag: null, crest_db: 10.9 })).toBe('bad')
    expect(flagTone({ flag: 'clipped', crest_db: 14 })).toBe('warn')
    expect(flagTone({ flag: null, crest_db: 14 })).toBe('ok')
    expect(flagTone({ flag: null, crest_db: null })).toBe('none')
    expect(flagTone(null)).toBe('none')
  })
})

describe('seedsFor', () => {
  const recipe = (seed: string) => ({ ...recipeFixture(), seed })
  it('counts up from a typed seed', () => expect(seedsFor(recipe('100'), 3)).toEqual([100, 101, 102]))
  it('draws random seeds when blank', () => {
    let n = 0
    expect(seedsFor(recipe(''), 2, () => (n += 0.25))).toEqual([Math.floor(0.25 * 2 ** 31), Math.floor(0.5 * 2 ** 31)])
  })
  it('clamps the count to 1..6', () => {
    expect(seedsFor(recipe('1'), 0)).toHaveLength(1)
    expect(seedsFor(recipe('1'), 99)).toHaveLength(6)
    expect(seedsFor(recipe('1'), Number.NaN)).toHaveLength(1)
  })
})

describe('buildRenderBody', () => {
  it('sends items, a cleaned recipe, seeds and the reference', () => {
    const r: LabRecipe = { ...recipeFixture(), seed: '5', pronunciation: [{ word: ' ', mode: 'plain', value: 'x' }, { word: 'Valancius', mode: 'plain', value: 'vah-LAN-see-us' }] }
    const body = buildRenderBody({ speaker: 'Vladaym Tocara the Liege', items: [{ guid: 'g1' }], recipe: r, seedCount: 2, ref: { wav: 'data/r.wav' } })
    expect(body).toMatchObject({ speaker: 'Vladaym Tocara the Liege', items: [{ guid: 'g1' }], seeds: [5, 6], ref: { wav: 'data/r.wav' } })
    expect(body.recipe.pronunciation).toEqual([{ word: 'Valancius', mode: 'plain', value: 'vah-LAN-see-us' }])
    expect(r.pronunciation).toHaveLength(2)
  })
  it('leaves ref out when there is none', () => {
    expect('ref' in buildRenderBody({ speaker: 's', items: [{ text: 'x' }], recipe: recipeFixture(), seedCount: 1 })).toBe(false)
  })
})

describe('recipe text helpers', () => {
  it('summarises the recipe', () => {
    const r = recipeFixture()
    expect(recipeSummary(r)).toBe('cfg 3 · 10 steps · whole · em-dash keep')
    expect(recipeSummary({ ...r, punctuation: { ...r.punctuation, em_dash: 'pause' }, pause_ms: 300 })).toContain('em-dash pause 300ms')
  })
  it('fills a carrier sentence', () => expect(carrierSentence('He said {w} and left, {w}.', 'X')).toBe('He said X and left, X.'))
  it('builds a one-override variant recipe without touching the base', () => {
    const base = { ...recipeFixture(), pronunciation: [{ word: 'old', mode: 'plain' as const, value: 'o' }] }
    const v = variantRecipe(base, 'von Valancius', { mode: 'arpabet', value: 'V AH0 L AE1 N' })
    expect(v.pronunciation).toEqual([{ word: 'von Valancius', mode: 'arpabet', value: 'V AH0 L AE1 N' }])
    expect(base.pronunciation).toHaveLength(1)
    expect(variantRecipe(base, 'w', { mode: 'plain', value: '' }).pronunciation).toEqual([])
    expect(variantLabel({ mode: 'plain', value: '' })).toBe('no override')
    expect(variantLabel({ mode: 'plain', value: 'x' })).toBe('plain: x')
  })
  it('cleanRecipe copies', () => {
    const r = recipeFixture()
    expect(cleanRecipe(r)).not.toBe(r)
  })
})
