import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { slot } from '../../test-utils/poolFixtures'
import SlotList from './SlotList.vue'

const slots = [
  slot('male_human', 'Male human', { lines: 1300, spot: { checked: 10, wrong: 0 } }),
  slot('female_human', 'Female human', { lines: 4, spot: { checked: 10, wrong: 1 } }),
  slot('old', 'Old', { lines: 1 }),
]
const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers/:slug', component: { template: '<i/>' } }] })
const make = (list = slots, selectedId: string | null = null) => mount(SlotList, { props: { slots: list, selectedId }, global: { plugins: [router] } })

describe('SlotList', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists slots with line counts, a total, and a link to the slot page', () => {
    const w = make()
    expect(w.text()).toContain('1,300')
    expect(w.text()).toContain('3 · 1,305 lines')
    expect(w.find('a').attributes('href')).toBe('/speakers/pool_male_human')
  })

  it('shows the check state as a dot name and the button label', () => {
    const w = make()
    const dots = w.findAll('[role="img"]').map((d) => d.attributes('aria-label'))
    expect(dots).toEqual(['spot-checked', '1 wrong in spot check', 'not checked'])
    const labels = w.findAll('[data-spot]').map((b) => b.text())
    expect(labels).toEqual(['Re-check', 'Re-check', 'Spot check'])
  })

  it('emits spot with the slot id, and marks the selected one', async () => {
    const w = make(slots, 'old')
    await w.findAll('[data-spot]')[2].trigger('click')
    expect(w.emitted('spot')![0]).toEqual(['old'])
    expect(w.findAll('[aria-current="true"]')).toHaveLength(1)
  })

  it('renames a slot', async () => {
    const w = make()
    await w.find('[data-rename]').trigger('click')
    await w.find('[data-rename-input]').setValue('Dockhands')
    await w.find('[data-save-name]').trigger('click')
    expect(w.emitted('rename')![0]).toEqual(['male_human', 'Dockhands'])
  })

  it('merge states the consequence, then confirms with the chosen target', async () => {
    const w = make()
    await w.find('[data-merge]').trigger('click')
    expect(w.find('[data-merge-note]').exists()).toBe(false)
    await w.find('[data-merge-target-field] select').setValue('female_human')
    expect(w.find('[data-merge-note]').text()).toBe('1,300 lines move to Female human; the slot and its name are removed.')
    await w.find('[role="alertdialog"] button').trigger('click')
    expect(w.emitted('merge')![0]).toEqual(['male_human', 'female_human'])
    expect(w.find('[data-merge-note]').exists()).toBe(false)
  })

  it('Esc cancels a merge', async () => {
    const w = make()
    await w.find('[data-merge]').trigger('click')
    await w.find('[data-merge-target-field] select').setValue('old')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await w.vm.$nextTick()
    expect(w.emitted('merge')).toBeUndefined()
    expect(w.find('[data-merge-note]').exists()).toBe(false)
  })

  it('hides Merge when there is only one slot', () => {
    expect(make([slots[0]]).find('[data-merge]').exists()).toBe(false)
  })

  it('creates a new voice from the form', async () => {
    const w = make()
    await w.find('[data-new-voice]').trigger('click')
    await w.find('[data-nv-name]').setValue('Dock foreman')
    await w.find('form').trigger('submit')
    expect(w.emitted('create')![0][0]).toMatchObject({ name: 'Dock foreman', gender: 'any' })
  })

  it('has an empty state', () => {
    expect(make([]).text()).toContain('No slots yet')
  })
})
