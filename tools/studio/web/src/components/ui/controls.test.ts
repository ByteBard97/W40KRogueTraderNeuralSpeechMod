import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import ActiveFilters from './ActiveFilters.vue'
import FilterChips from './FilterChips.vue'
import JudgePair from './JudgePair.vue'
import SearchField from './SearchField.vue'
import SelectField from './SelectField.vue'
import Seg from './Seg.vue'

describe('Seg', () => {
  const options = [{ value: 'off', label: 'Off' }, { value: 'mild', label: 'Mild' }]
  it('marks the current option pressed and emits the chosen value', async () => {
    const w = mount(Seg, { props: { options, modelValue: 'off', ariaLabel: 'Compressor' } })
    const b = w.findAll('button')
    expect(b[0].attributes('aria-pressed')).toBe('true')
    expect(b[1].attributes('aria-pressed')).toBe('false')
    await b[1].trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['mild'])
    expect(w.attributes('aria-label')).toBe('Compressor')
  })
})

describe('FilterChips', () => {
  const options = [{ value: 'all', label: 'All', count: 79 }, { value: 'sad', label: 'sad', count: 5 }]
  it('shows counts and toggles a single choice', async () => {
    const w = mount(FilterChips, { props: { options, modelValue: 'all', clearable: true } })
    expect(w.text()).toContain('79')
    await w.findAll('button')[1].trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['sad'])
    await w.findAll('button')[0].trigger('click')
    expect(w.emitted('update:modelValue')?.[1]).toEqual([null])
  })
  it('keeps a set in multiple mode', async () => {
    const w = mount(FilterChips, { props: { options, modelValue: ['all'], multiple: true } })
    await w.findAll('button')[1].trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual([['all', 'sad']])
  })
})

describe('SearchField', () => {
  it('emits typed text and "/" focuses it outside inputs', async () => {
    const w = mount(SearchField, { props: { modelValue: '' }, attachTo: document.body })
    const input = w.find('input')
    await input.setValue('abc')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['abc'])
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '/', bubbles: true }))
    expect(document.activeElement).toBe(input.element)
    w.unmount()
  })
})

describe('SelectField', () => {
  it('emits the selected value', async () => {
    const w = mount(SelectField, { props: { label: 'Speaker', modelValue: 'a', options: [{ value: 'a', label: 'A' }, { value: 'b', label: 'B' }] } })
    await w.find('select').setValue('b')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['b'])
  })
})

describe('ActiveFilters', () => {
  it('renders nothing without filters, removes one, and clears all', async () => {
    expect(mount(ActiveFilters, { props: { filters: [] } }).html()).toBe('<!--v-if-->')
    const w = mount(ActiveFilters, { props: { filters: [{ key: 'flag', label: 'flag: cap_hit' }, { key: 'v', label: 'verdict' }], shown: 412, total: 11051 } })
    expect(w.text()).toContain('11,051')
    await w.findAll('.chip')[0].trigger('click')
    expect(w.emitted('remove')?.[0]).toEqual(['flag'])
    await w.find('.btn').trigger('click')
    expect(w.emitted('clear')).toBeTruthy()
  })
})

describe('JudgePair', () => {
  it('toggles good/bad and clears when the active one is clicked again', async () => {
    const w = mount(JudgePair, { props: { modelValue: 'bad' } })
    const [good, bad] = w.findAll('button')
    expect(bad.attributes('aria-pressed')).toBe('true')
    await good.trigger('click')
    expect(w.emitted('update:modelValue')?.[0]).toEqual(['good'])
    await bad.trigger('click')
    expect(w.emitted('update:modelValue')?.[1]).toEqual([null])
  })
})
