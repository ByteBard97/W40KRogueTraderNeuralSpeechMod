import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import MatchFilters from './MatchFilters.vue'

const counts = { flagged: 25, bank: 118, nobank: 134, undecided: 0, total: 277 }
const mk = () => mount(MatchFilters, { props: { modelValue: { group: 'flagged', state: 'unreviewed', speaker: '', q: '' }, counts } })

describe('MatchFilters', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('shows the group counts, with All as the total', () => {
    const t = mk().find('[aria-label=Group]').text()
    for (const s of ['Flagged 25', 'Has bank 118', 'No bank 134', 'All 277']) expect(t).toContain(s)
  })
  it('emits the whole filter when the group or decision changes', async () => {
    const w = mk()
    await w.findAll('[aria-label=Group] button')[3].trigger('click')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toEqual({ group: '', state: 'unreviewed', speaker: '', q: '' })
    await w.find('select').setValue('reject')
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toMatchObject({ state: 'reject', group: 'flagged' })
  })
  it('waits for a pause in typing before emitting the speaker', async () => {
    const w = mk()
    await w.find('input[aria-label="Proposed speaker"]').setValue('hein')
    expect(w.emitted('update:modelValue')).toBeUndefined()
    vi.advanceTimersByTime(300)
    expect(w.emitted('update:modelValue')!.at(-1)![0]).toMatchObject({ speaker: 'hein' })
  })
  it('lists the decision choices including Not reviewed', () => {
    expect(mk().find('select').text()).toContain('Not reviewed')
  })
})
