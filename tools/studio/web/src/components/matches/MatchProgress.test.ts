import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MatchProgress from './MatchProgress.vue'

describe('MatchProgress', () => {
  it('shows reviewed over total with the accepted and rejected split', () => {
    const w = mount(MatchProgress, { props: { counts: { flagged: 1, bank: 1, nobank: 1, undecided: 0, total: 200, accepted: 20, rejected: 10, reviewed: 30 } } })
    expect(w.text()).toContain('30 / 200')
    expect(w.text()).toContain('accepted 20')
    expect(w.text()).toContain('rejected 10')
    expect(w.find('.g').attributes('style')).toContain('width: 10%')
    expect(w.find('.b').attributes('style')).toContain('width: 5%')
  })
  it('renders nothing against a server without the new counts', () => {
    expect(mount(MatchProgress, { props: { counts: { flagged: 1, bank: 1, nobank: 1, undecided: 0 } } }).find('.progress').exists()).toBe(false)
    expect(mount(MatchProgress, { props: { counts: null } }).find('.progress').exists()).toBe(false)
  })
})

describe('MatchProgress saved line', () => {
  it('swaps the hint for the Saved indicator and the pools note', () => {
    const counts = { flagged: 1, bank: 1, nobank: 1, undecided: 0, total: 10, accepted: 1, rejected: 0, reviewed: 1 }
    const w = mount(MatchProgress, { props: { counts, saved: true, note: 'Pools update in a moment' } })
    expect(w.text()).toContain('Saved · Pools update in a moment')
    expect(w.text()).not.toContain('saved as you go')
  })
})
