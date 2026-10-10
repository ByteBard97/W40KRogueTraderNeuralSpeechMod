import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StarScore from './StarScore.vue'

describe('StarScore', () => {
  it('fills stars up to the value and emits the clicked number', async () => {
    const w = mount(StarScore, { props: { modelValue: 3, label: 'Fit' } })
    expect(w.findAll('button.on')).toHaveLength(3)
    await w.findAll('button')[4].trigger('click')
    expect(w.emitted('update:modelValue')![0]).toEqual([5])
  })
  it('clicking the current value clears it, and the group names its state', async () => {
    const w = mount(StarScore, { props: { modelValue: 2, label: 'Accent score' } })
    expect(w.attributes('aria-label')).toBe('Accent score, 2 of 5')
    await w.findAll('button')[1].trigger('click')
    expect(w.emitted('update:modelValue')![0]).toEqual([0])
    expect(mount(StarScore, { props: { modelValue: 0, label: 'Fit' } }).attributes('aria-label')).toContain('not rated')
  })
})
