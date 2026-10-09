import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import RoutingSummary from './RoutingSummary.vue'

const summary = { threshold: 0.8, built: 'now', total: 6717, destinations: { narrator: 138, speaker_bank: 1911, speaker_nobank: 2947, slot: 1863 }, slots: [], queue_lines: 556, queue_entries: 92 }

describe('RoutingSummary', () => {
  it('shows each destination with its count and the queue size', () => {
    const t = mount(RoutingSummary, { props: { summary } }).text()
    for (const n of ['6717', '138', '1911', '2947', '1863', '92']) expect(t).toContain(n)
    expect(t).toMatch(/real voice bank/i)
    expect(t).toMatch(/named NPC/i)
  })
})
