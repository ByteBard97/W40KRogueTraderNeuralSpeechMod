import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import PresetBar from './PresetBar.vue'

const starters = [
  { slug: 'a', name: 'Alpha', description: 'first', category: 'Machine', graph: { version: 1, name: '', nodes: [], edges: [] } },
  { slug: 'b', name: 'Beta', description: 'second', category: 'Vox', graph: { version: 1, name: '', nodes: [], edges: [] } },
  { slug: 'c', name: 'Gamma', description: 'third', category: 'Machine', graph: { version: 1, name: '', nodes: [], edges: [] } },
]
const base = { starters, saved: ['mine', 'other'], name: 'x', dirty: false, valid: true, issues: [] as string[] }
const mk = (over: Record<string, unknown> = {}) => mount(PresetBar, { props: { ...base, ...over } })

describe('PresetBar', () => {
  it('disables Save for an invalid graph and for an empty name', () => {
    expect(mk({ valid: false }).get('[data-testid="save-btn"]').attributes('disabled')).toBeDefined()
    expect(mk({ name: '   ' }).get('[data-testid="save-btn"]').attributes('disabled')).toBeDefined()
    expect(mk().get('[data-testid="save-btn"]').attributes('disabled')).toBeUndefined()
  })

  it('emits save with the trimmed name', async () => {
    const w = mk({ name: ' tin ' })
    await w.get('form').trigger('submit')
    expect(w.emitted('save')).toEqual([['tin']])
  })

  it('does not emit save when invalid', async () => {
    const w = mk({ valid: false })
    await w.get('form').trigger('submit')
    expect(w.emitted('save')).toBeUndefined()
  })

  it('lists starting points grouped by category and loads one', async () => {
    const w = mk()
    await w.get('[data-testid="preset-starters"]').trigger('click')
    expect(w.findAll('.cat-name').map((c) => c.text())).toEqual(['Machine', 'Vox'])
    await w.get('[data-testid="starter-b"]').trigger('click')
    expect(w.emitted('load-starter')).toEqual([['b']])
    expect(w.find('[data-testid="starter-a"]').exists()).toBe(false)
  })

  it('lists saved graphs and loads one', async () => {
    const w = mk()
    await w.get('[data-testid="preset-saved"]').trigger('click')
    await w.get('[data-testid="saved-other"]').trigger('click')
    expect(w.emitted('load-saved')).toEqual([['other']])
  })

  it('says so when a menu is empty', async () => {
    const w = mk({ starters: [], saved: [] })
    await w.get('[data-testid="preset-starters"]').trigger('click')
    expect(w.text()).toContain('No starting points yet')
  })

  it('emits new, name updates, and shows the dirty note', async () => {
    const w = mk({ dirty: true })
    await w.get('[data-testid="new-btn"]').trigger('click')
    await w.get('[data-testid="name-input"]').setValue('abc')
    expect(w.emitted('new')).toHaveLength(1)
    expect(w.emitted('update:name')![0]).toEqual(['abc'])
    expect(w.find('[data-testid="dirty"]').exists()).toBe(true)
    expect(mk().find('[data-testid="dirty"]').exists()).toBe(false)
  })

  it('shows issues only while invalid, capped with a count', () => {
    expect(mk({ issues: ['x'] }).find('[data-testid="issues"]').exists()).toBe(false)
    const w = mk({ valid: false, issues: ['The Output is not connected', 'b', 'c', 'd', 'e', 'f'] })
    const items = w.findAll('[data-testid="issues"] li')
    expect(items[0].text()).toBe('The Output is not connected')
    expect(items).toHaveLength(5)
    expect(items[4].text()).toBe('and 2 more')
  })

  it('has Undo and Redo buttons that follow their enabled state and emit', async () => {
    const off = mk()
    expect(off.get('[data-testid="undo-btn"]').attributes('disabled')).toBeDefined()
    expect(off.get('[data-testid="redo-btn"]').attributes('disabled')).toBeDefined()
    const w = mk({ canUndo: true, canRedo: true })
    await w.get('[data-testid="undo-btn"]').trigger('click')
    await w.get('[data-testid="redo-btn"]').trigger('click')
    expect(w.emitted('undo')).toHaveLength(1)
    expect(w.emitted('redo')).toHaveLength(1)
  })
})
