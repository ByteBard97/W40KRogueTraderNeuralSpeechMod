import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QaFilters from './QaFilters.vue'

const facets = { speakers: ['Abelard', 'Cassia'], refs: ['ref_a'], engines: ['voxcpm2'], flags: ['cap_hit', 'slow'] }

describe('QaFilters', () => {
  it('lists the facet options', () => {
    const w = mount(QaFilters, { props: { facets } })
    expect(w.find('[data-speaker]').text()).toContain('Cassia')
    expect(w.find('[data-flag]').text()).toContain('cap_hit')
    expect(w.find('[data-engine]').text()).toContain('voxcpm2')
    expect(w.find('[data-ref]').text()).toContain('ref_a')
  })

  it('emits the whole filter when a control changes', async () => {
    const w = mount(QaFilters, { props: { facets } })
    await w.find('[data-flag]').setValue('slow')
    await w.find('[data-sort]').setValue('random')
    await w.find('[data-q]').setValue('emperor')
    await w.find('[data-q]').trigger('change')
    const last = w.emitted('change')!.at(-1)![0]
    expect(last).toMatchObject({ flag: 'slow', sort: 'random', q: 'emperor', speaker: '' })
  })
})
