import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { slot, summaryOf } from '../../test-utils/poolFixtures'
import RoutingSummary from './RoutingSummary.vue'

describe('RoutingSummary', () => {
  const summary = summaryOf([slot('a', 'A'), slot('b', 'B')])

  it('shows the four destinations with counts and the slot count', () => {
    const w = mount(RoutingSummary, { props: { summary } })
    const t = w.text()
    expect(t).toContain('Known speaker with a voice bank')
    expect(t).toContain('Named NPC without a bank')
    expect(t).toContain('Narrator')
    expect(t).toContain('anonymous characters, 2 slots')
    expect(w.find('[role="group"]').attributes('aria-label')).toContain('45 Shared slot voice')
  })

  it('sizes segments by share and drops empty ones', () => {
    const w = mount(RoutingSummary, { props: { summary: { ...summary, destinations: { narrator: 0, speaker_bank: 50, speaker_nobank: 50, slot: 0 } } } })
    const segs = w.findAll('.bar .seg')
    expect(segs.map((s) => s.attributes('style'))).toEqual(expect.arrayContaining([expect.stringContaining('width: 50%')]))
    expect(segs.filter((s) => s.attributes('style')?.includes('display: none'))).toHaveLength(2)
  })

  it('emits the destination when a segment or legend row is clicked', async () => {
    const w = mount(RoutingSummary, { props: { summary } })
    await w.findAll('.bar .seg')[1].trigger('click')
    await w.findAll('.legend .item')[3].trigger('click')
    expect(w.emitted('filter')).toEqual([['nobank'], ['slot']])
  })
})
