import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { Bg3Voice, LabelDef } from '../../api/types'
import LabelEditor from './LabelEditor.vue'

const SCHEMA: LabelDef[] = [
  { key: 'age', label: 'Age', kind: 'single', allow_several: true, options: ['child', 'youth', 'adult', 'old'], required: true },
  { key: 'reserve', label: 'Use', kind: 'single', options: ['free', 'do not use'], required: false },
]
const voice = (mine: Bg3Voice['mine'] = {}, labels: Bg3Voice['labels'] = mine): Bg3Voice => ({
  slug: 'v', name: 'V', lines: 1, minutes: 1, gender: 'male', f0: null, non_human: false, refs: [], used_by: [], labels, mine, complete: false })
const click = async (w: ReturnType<typeof mount>, row: number, text: string) => {
  await w.findAll('.row')[row].findAll('button').find((b) => b.text() === text)!.trigger('click')
}

describe('LabelEditor', () => {
  it('a first pick is saved as a plain value', async () => {
    const w = mount(LabelEditor, { props: { voice: voice(), schema: SCHEMA } })
    await click(w, 0, 'youth')
    expect(w.emitted('set')![0]).toEqual(['age', 'youth'])
  })

  it('a second pick on a label that allows several adds to the first', async () => {
    const w = mount(LabelEditor, { props: { voice: voice({ age: 'youth' }), schema: SCHEMA } })
    await click(w, 0, 'adult')
    expect(w.emitted('set')![0]).toEqual(['age', ['youth', 'adult']])
  })

  it('clicking a chosen value removes it, and removing the last clears the label', async () => {
    const two = mount(LabelEditor, { props: { voice: voice({ age: ['youth', 'adult'] }), schema: SCHEMA } })
    await click(two, 0, 'youth')
    expect(two.emitted('set')![0]).toEqual(['age', 'adult'])
    const one = mount(LabelEditor, { props: { voice: voice({ age: 'adult' }), schema: SCHEMA } })
    await click(one, 0, 'adult')
    expect(one.emitted('set')![0]).toEqual(['age', null])
  })

  it('a label that takes one value replaces the choice', async () => {
    const w = mount(LabelEditor, { props: { voice: voice({ reserve: 'free' }), schema: SCHEMA } })
    await click(w, 1, 'do not use')
    expect(w.emitted('set')![0]).toEqual(['reserve', 'do not use'])
  })

  it('shows the automatic guess dashed until it is confirmed', () => {
    const w = mount(LabelEditor, { props: { voice: voice({}, { age: 'adult' }), schema: SCHEMA } })
    const adult = w.findAll('.row')[0].findAll('button').find((b) => b.text() === 'adult')!
    expect(adult.classes()).toContain('guess')
    expect(adult.attributes('aria-pressed')).toBe('false')
  })
})
