import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import type { FxPresetInfo } from '../../api/types'
import LabelMap from './LabelMap.vue'

const presets: FxPresetInfo[] = [
  { name: 'Clean', source: 'scenario', dsp: 'c.dsp', notes: '', family: 'Space', version: 'v1' },
  { name: 'Mine', source: 'saved', dsp: 'c.dsp', notes: '' },
]
const base = { draft: { machine: ['Clean', 'Mine'], helmet: [] }, labels: ['machine', 'helmet'], dirty: ['machine'], presets, usage: null }

describe('LabelMap', () => {
  it('renders the real labels it is given, with chains, a no-effect note and the dirty marker', () => {
    const w = mount(LabelMap, { props: base })
    expect(w.findAll('[data-label]').map((r) => r.attributes('data-label'))).toEqual(['machine', 'helmet'])
    expect(w.findAll('.chip')).toHaveLength(2)
    expect(w.text()).toContain('no effect')
    expect(w.find('[data-label="machine"]').classes()).toContain('dirty')
    expect(w.find('[data-label="machine"] [aria-label="edited, not written"]').exists()).toBe(true)
    expect(w.find('[data-label="helmet"] [aria-label="matches file"]').exists()).toBe(true)
  })

  it('emits add, remove and move without owning the draft', async () => {
    const w = mount(LabelMap, { props: base })
    await w.find('[data-label="helmet"] [data-add]').setValue('Clean')
    expect(w.emitted('add')![0]).toEqual(['helmet', 'Clean'])
    await w.findAll('[data-remove]')[0].trigger('click')
    expect(w.emitted('remove')![0]).toEqual(['machine', 0])
    await w.findAll('.chip-name')[0].trigger('keydown', { key: 'ArrowRight', altKey: true })
    expect(w.emitted('move')![0]).toEqual(['machine', 0, 1])
  })

  it('disables presets already in the chain and groups the rest by family', () => {
    const w = mount(LabelMap, { props: base })
    const sel = w.find('[data-label="machine"] [data-add]')
    expect(sel.findAll('optgroup').map((g) => g.attributes('label'))).toEqual(['Space', 'Other'])
    expect(sel.findAll('option').find((o) => o.text() === 'Clean')!.attributes('disabled')).toBeDefined()
  })

  it('moves a dragged chip to the drop position', async () => {
    const w = mount(LabelMap, { props: base })
    const chips = w.findAll('.chip')
    await chips[0].trigger('dragstart')
    await chips[1].trigger('drop')
    expect(w.emitted('move')![0]).toEqual(['machine', 0, 1])
  })

  it('shows speaker counts from usage, or a dash without it', () => {
    const usage = { labels: { machine: { lines: 9, speakers: 3, presets: 2 }, helmet: { lines: 0, speakers: 0, presets: 0 } }, pools_built: false }
    const w = mount(LabelMap, { props: { ...base, usage } })
    expect(w.find('[data-label="machine"] .uses').text()).toBe('3')
    expect(w.text()).toContain('until the Pools routes are built')
    expect(mount(LabelMap, { props: base }).find('.uses.num').text()).toBe('–')
  })
})
