import { describe, expect, it } from 'vitest'
import type { Bg3Voice } from '../api/types'
import { filterVoices, filtersForCharacter, labelSummary, labelsComplete, requiredDone } from './castVoices'
import type { LabelDef } from '../api/types'

const v = (name: string, lines: number, gender: string): Bg3Voice => ({ slug: name, name, lines, minutes: 1, gender, f0: null, non_human: false, refs: [], used_by: [], labels: {}, mine: {}, complete: false })
const voices = [v('Zevlor', 615, 'male'), v('astarion', 10000, 'male'), v('Karlach', 8696, 'female'), v('Halsin', 5888, 'male'), v('Mizora', 776, 'female')]

describe('filterVoices', () => {
  it('sorts by line count, biggest first', () => {
    expect(filterVoices(voices, '', 'all', 'lines').map((x) => x.name)).toEqual(['astarion', 'Karlach', 'Halsin', 'Mizora', 'Zevlor'])
  })

  it('sorts alphabetically without regard to case', () => {
    expect(filterVoices(voices, '', 'all', 'name').map((x) => x.name)).toEqual(['astarion', 'Halsin', 'Karlach', 'Mizora', 'Zevlor'])
  })

  it('filters by gender and keeps the order', () => {
    expect(filterVoices(voices, '', 'female', 'lines').map((x) => x.name)).toEqual(['Karlach', 'Mizora'])
    expect(filterVoices(voices, '', 'male', 'name').map((x) => x.name)).toEqual(['astarion', 'Halsin', 'Zevlor'])
  })

  it('combines the search with the gender filter', () => {
    expect(filterVoices(voices, 'a', 'male', 'name').map((x) => x.name)).toEqual(['astarion', 'Halsin'])
  })

  it('finds a voice by another name it is known by', () => {
    const list = [{ ...v('Nightsong', 601, 'female'), aliases: ['Dame Aylin', 'Aylin'] }, v('Karlach', 8696, 'female')]
    expect(filterVoices(list, 'aylin', 'all', 'lines').map((x) => x.name)).toEqual(['Nightsong'])
  })

  it('does not change the list it was given', () => {
    const before = voices.map((x) => x.name)
    filterVoices(voices, '', 'all', 'name')
    expect(voices.map((x) => x.name)).toEqual(before)
  })
})

const lab = (name: string, labels: Record<string, string | string[]>): Bg3Voice => ({ ...v(name, 100, 'male'), labels, mine: labels })

describe('label filters', () => {
  const list = [lab('A', { gender: 'female', age: 'youth', class: 'low', texture: ['raspy', 'smooth'] }), lab('B', { gender: 'female', age: 'old', class: 'low' }),
    lab('C', { gender: 'male', age: 'youth' }), v('D', 1, 'male')]

  it('keeps voices that match every active label', () => {
    expect(filterVoices(list, '', 'all', 'name', { gender: ['female'], age: ['youth'] }).map((x) => x.name)).toEqual(['A'])
  })

  it('a label with several values passes a voice with any of them', () => {
    expect(filterVoices(list, '', 'all', 'name', { age: ['youth', 'old'] }).map((x) => x.name)).toEqual(['A', 'B', 'C'])
  })

  it('matches one value inside a multi label, and drops voices without the label', () => {
    expect(filterVoices(list, '', 'all', 'name', { texture: ['smooth'] }).map((x) => x.name)).toEqual(['A'])
    expect(filterVoices(list, '', 'all', 'name', { class: ['low'] }).map((x) => x.name)).toEqual(['A', 'B'])
  })

  it('an empty selection filters nothing', () => {
    expect(filterVoices(list, '', 'all', 'name', { gender: [] })).toHaveLength(4)
  })

  it('counts how many required labels are set by me, and summarises the labels', () => {
    const schema = [{ key: 'gender', required: true }, { key: 'age', required: true }, { key: 'note', required: false }] as LabelDef[]
    expect(requiredDone(list[0], schema)).toBe(2)
    expect(requiredDone(list[3], schema)).toBe(0)
    expect(labelSummary(lab('X', { gender: 'female', age: 'youth', class: 'low', pitch: 'high' }))).toBe('female · youth · low class · high pitch')
  })

  it('a voice in between shows up under either of its values, and the summary lists both', () => {
    const both = lab('Both', { age: ['youth', 'adult'], pitch: 'high' })
    expect(filterVoices([both], '', 'all', 'name', { age: ['youth'] })).toHaveLength(1)
    expect(filterVoices([both], '', 'all', 'name', { age: ['adult'] })).toHaveLength(1)
    expect(filterVoices([both], '', 'all', 'name', { age: ['old'] })).toHaveLength(0)
    expect(labelSummary(both)).toBe('youth/adult · high pitch')
  })

  it('turns a character into filters (young becomes youth)', () => {
    expect(filtersForCharacter({ gender: 'female', age: 'young' })).toEqual({ gender: ['female'], age: ['youth'] })
    expect(filtersForCharacter({ gender: null, age: null })).toEqual({})
  })
})

describe('in-between class and pitch', () => {
  const list = [lab('a', { pitch: 'low' }), lab('b', { pitch: 'low-middle' }), lab('c', { pitch: 'middle' }), lab('d', { pitch: 'middle-high' }), lab('e', { pitch: 'high' })]
  const names = (f: string[]) => filterVoices(list, '', 'all', 'name', { pitch: f }).map((x) => x.name)

  it('finds an in-between voice under both of its neighbours, as a voice with two picks was found before', () => {
    expect(names(['low'])).toEqual(['a', 'b'])
    expect(names(['middle'])).toEqual(['b', 'c', 'd'])
    expect(names(['high'])).toEqual(['d', 'e'])
  })

  it('finds only the in-between voices when that step itself is chosen', () => {
    expect(names(['low-middle'])).toEqual(['b'])
  })
})

describe('labelsComplete', () => {
  const schema = [{ key: 'gender', label: 'Gender', kind: 'single', options: ['male'], required: true }, { key: 'reserve', label: 'Use', kind: 'single', options: [], required: false }] as LabelDef[]
  it('needs every required label', () => {
    expect(labelsComplete({}, schema)).toBe(false)
    expect(labelsComplete({ gender: 'male' }, schema)).toBe(true)
  })
  it('counts a voice marked do not use as done', () => {
    expect(labelsComplete({ reserve: 'do not use' }, schema)).toBe(true)
    expect(labelsComplete({ reserve: 'free' }, schema)).toBe(false)
  })
})
