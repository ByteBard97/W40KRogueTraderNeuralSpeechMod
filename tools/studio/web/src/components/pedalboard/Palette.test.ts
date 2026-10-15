import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { realCatalog } from '../../test-utils/pedalboardCatalog'
import Palette from './Palette.vue'

const mk = () => mount(Palette, { props: { blocks: realCatalog.blocks } })

describe('Palette', () => {
  it('groups by category in the plan order and leaves out Input and Output', () => {
    const w = mk()
    const names = w.findAll('.group-head').map((h) => h.text().replace(/[+-]\s*/, '').replace(/\d+$/, '').trim())
    expect(names).toEqual(['Tone', 'Pitch & voice', 'Metal', 'Modulation', 'Space', 'Stereo', 'Routing'])
    expect(w.find('[data-testid="palette-input"]').exists()).toBe(false)
    expect(w.find('[data-testid="palette-output"]').exists()).toBe(false)
  })

  it('lists Mix pedals under Routing', () => {
    const w = mk()
    const routing = w.get('[data-testid="palette-group-Routing"]')
    expect(routing.find('[data-testid="palette-mix2"]').exists()).toBe(true)
    expect(routing.find('[data-testid="palette-mix4"]').exists()).toBe(true)
  })

  it('shows the name and keeps the description for hover and focus', () => {
    const item = mk().get('[data-testid="palette-metal"]')
    expect(item.text()).toContain('Metal bank')
    expect(item.attributes('title')).toBe(realCatalog.blocks.find((b) => b.id === 'metal')!.description)
  })

  it('emits add on double click and on Enter', async () => {
    const w = mk()
    await w.get('[data-testid="palette-metal"]').trigger('dblclick')
    await w.get('[data-testid="palette-echo"]').trigger('keydown', { key: 'Enter' })
    expect(w.emitted('add')).toEqual([['metal'], ['echo']])
  })

  it('collapses a section', async () => {
    const w = mk()
    await w.get('[data-testid="palette-group-Tone"] .group-head').trigger('click')
    expect(w.get('[data-testid="palette-group-Tone"] .items').attributes('style')).toContain('display: none')
    expect(w.get('[data-testid="palette-group-Tone"] .group-head').attributes('aria-expanded')).toBe('false')
    expect(w.get('[data-testid="palette-group-Metal"] .items').attributes('style') ?? '').not.toContain('display: none')
  })

  it('items are draggable', () => {
    expect(mk().get('[data-testid="palette-metal"]').attributes('draggable')).toBe('true')
  })
})
