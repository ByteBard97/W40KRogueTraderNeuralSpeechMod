import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import LabelMap from './LabelMap.vue'

const presets = ['Clean', 'Mine', 'Third']

describe('LabelMap', () => {
  it('shows all six labels with their chains', () => {
    const w = mount(LabelMap, { props: { labels: { machine: ['Clean', 'Mine'] }, presets } })
    expect(w.findAll('.label')).toHaveLength(6)
    expect(w.text()).toContain('vox_channel')
    expect(w.findAll('.chain')).toHaveLength(2)
  })

  it('adds, reorders and removes presets, then saves the ordered lists', async () => {
    const w = mount(LabelMap, { props: { labels: { machine: ['Clean'] }, presets } })
    await w.find('[data-add]').setValue('Mine')
    await w.findAll('.chain')[1].find('[data-up]').trigger('click')
    expect(w.findAll('.chain').map((c) => c.text().split(' ')[0])).toEqual(['Mine', 'Clean'])
    await w.findAll('.chain')[0].find('[data-remove]').trigger('click')
    await w.find('[data-save]').trigger('click')
    const saved = w.emitted('save')![0][0] as Record<string, string[]>
    expect(saved.machine).toEqual(['Clean'])
    expect(Object.keys(saved)).toHaveLength(6)
  })

  it('does not add the same preset twice to one label', async () => {
    const w = mount(LabelMap, { props: { labels: { machine: ['Clean'] }, presets } })
    await w.find('[data-add]').setValue('Clean')
    expect(w.findAll('.chain')).toHaveLength(1)
  })
})
