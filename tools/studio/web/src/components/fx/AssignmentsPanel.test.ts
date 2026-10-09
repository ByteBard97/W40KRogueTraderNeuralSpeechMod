import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AssignmentsPanel from './AssignmentsPanel.vue'

const preview = { lines: 12, speakers: 2, unmapped_labels: { ethereal: 4 }, sample: [{ guid: 'abcdef123456', presets: ['Clean', 'Mine'] }] }

describe('AssignmentsPanel', () => {
  it('offers only Preview until there is a preview, then Write', async () => {
    const w = mount(AssignmentsPanel, { props: { preview: null, written: null } })
    expect(w.find('[data-write]').exists()).toBe(false)
    await w.find('[data-preview]').trigger('click')
    expect(w.emitted('preview')).toHaveLength(1)
    await w.setProps({ preview })
    expect(w.text()).toContain('12 lines and 2 speakers')
    expect(w.text()).toContain('“ethereal”')
    expect(w.text()).toContain('Clean + Mine')
    await w.find('[data-write]').trigger('click')
    expect(w.emitted('write')).toHaveLength(1)
  })

  it('reports what was written', () => {
    const w = mount(AssignmentsPanel, { props: { preview, written: { path: 'data/fx_lab/assignments.json', lines: 12, speakers: 2 } } })
    expect(w.text()).toContain('Wrote data/fx_lab/assignments.json')
  })
})
