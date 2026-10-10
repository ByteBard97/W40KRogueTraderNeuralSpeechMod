import { mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import QaFilters from './QaFilters.vue'

const facets = { speakers: ['Abelard', 'Cassia'], refs: ['ref_a'], engines: ['voxcpm2'], flags: ['cap_hit', 'slow'] }
const runs = [{ id: 'export', label: 'Merged export', clips: 11051 }]
const base = { runs, run: 'export', facets, filter: { sort: 'suspicious' as const }, fx: '' as const, matching: 11051, inRun: 11051 }
const mountIt = (over = {}) => mount(QaFilters, { props: { ...base, ...over }, attachTo: document.body })

describe('QaFilters', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  it('lists the run, the facet options and a zero active count', () => {
    const w = mountIt()
    expect(w.find('[data-run]').text()).toContain('Merged export (11,051)')
    expect(w.find('[data-speaker]').text()).toContain('Cassia')
    expect(w.find('[data-flag]').text()).toContain('cap_hit')
    expect(w.find('[data-flag]').text()).toContain('Has a flag')
    expect(w.find('.pop-btn').text()).toContain('0 active')
    expect(w.find('.active-filters').exists()).toBe(false)
    w.unmount()
  })

  it('emits the whole filter when a control changes', async () => {
    const w = mountIt({ filter: { sort: 'suspicious', seed: 1 } })
    await w.find('[data-flag] select').setValue('slow')
    await w.find('[data-sort] select').setValue('random')
    expect(w.emitted('change')).toEqual([[{ sort: 'suspicious', seed: 1, flag: 'slow' }], [{ sort: 'random', seed: 1 }]])
    w.unmount()
  })

  it('searches after a pause, or at once on Enter', async () => {
    const w = mountIt()
    const input = w.find('input[type="search"]')
    await input.setValue('emperor')
    expect(w.emitted('change')).toBeUndefined()
    vi.advanceTimersByTime(300)
    expect(w.emitted('change')!.at(-1)![0]).toMatchObject({ q: 'emperor' })
    await input.setValue('throne')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('change')!.at(-1)![0]).toMatchObject({ q: 'throne' })
    w.unmount()
  })

  it('shows a chip per active filter, counts the popover ones, and removes or clears them', async () => {
    const w = mountIt({ filter: { sort: 'slowest', speaker: 'Abelard', verdict: 'bad', q: 'hi' }, matching: 12 })
    expect(w.find('.pop-btn').text()).toContain('2 active')
    const chips = w.findAll('.active-filters .chip').map((c) => c.text())
    expect(chips).toEqual(['Speaker: Abelard ×', 'Verdict: bad ×', 'Text: “hi” ×'])
    expect(w.find('.active-filters').text()).toContain('Showing 12 of 11,051')
    await w.findAll('.active-filters .chip')[0].trigger('click')
    expect(w.emitted('change')!.at(-1)![0]).toMatchObject({ speaker: '', verdict: 'bad', sort: 'slowest' })
    await w.findAll('.active-filters button').at(-1)!.trigger('click')
    expect(w.emitted('change')!.at(-1)![0]).toEqual({ sort: 'slowest', speaker: '', ref: '', engine: '', flag: '', verdict: '', q: '' })
    w.unmount()
  })

  it('follows the filter prop when the store resets it', async () => {
    const w = mountIt({ filter: { speaker: 'Abelard', q: 'x', sort: 'slowest' } })
    expect((w.find('[data-speaker] select').element as HTMLSelectElement).value).toBe('Abelard')
    expect((w.find('input[type="search"]').element as HTMLInputElement).value).toBe('x')
    await w.setProps({ filter: { sort: 'slowest' } })
    expect((w.find('[data-speaker] select').element as HTMLSelectElement).value).toBe('')
    expect((w.find('input[type="search"]').element as HTMLInputElement).value).toBe('')
    w.unmount()
  })

  it('switches run and compressor', async () => {
    const w = mountIt()
    await w.find('[data-run] select').setValue('export')
    expect(w.emitted('update:run')).toEqual([['export']])
    await w.findAll('.seg button')[2].trigger('click')
    expect(w.emitted('update:fx')).toEqual([['strong']])
    w.unmount()
  })
})
