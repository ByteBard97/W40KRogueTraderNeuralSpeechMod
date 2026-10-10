import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { cand } from '../../test-utils/speakerCtx'
import CandidateRanker from './CandidateRanker.vue'

const cands = ['c0.wav', 'c1.wav', 'c2.wav'].map((id) => cand(id))
const mk = (over: Record<string, unknown> = {}) => mount(CandidateRanker, { attachTo: document.body, props: { candidates: cands, sourceIds: new Set<string>(), pickId: null, speaker: 'Ruoldo', ...over } })

describe('CandidateRanker', () => {
  it('lists candidates in the order given as a listbox, with rank numbers', () => {
    const w = mk()
    expect(w.find('[role=listbox]').exists()).toBe(true)
    expect(w.findAll('[role=option]').map((r) => r.attributes('data-cand'))).toEqual(['c0', 'c1', 'c2'])
    expect(w.findAll('.rank').map((r) => r.text())).toEqual(['1', '2', '3'])
  })

  it('marks only the explicit pick, not rank 1', () => {
    const w = mk({ pickId: 'c2.wav' })
    expect(w.findAll('[role=option]').map((r) => r.attributes('aria-selected'))).toEqual(['false', 'false', 'true'])
  })

  it('moves with the buttons and emits the full new order', async () => {
    const w = mk()
    await w.find('[aria-label="Move c0 down"]').trigger('click')
    expect(w.emitted('reorder')![0]).toEqual([['c1.wav', 'c0.wav', 'c2.wav']])
    await w.find('[aria-label="Move c2 up"]').trigger('click')
    expect(w.emitted('reorder')![1]).toEqual([['c0.wav', 'c2.wav', 'c1.wav']])
  })

  it('reorders by drag and drop', async () => {
    const w = mk()
    const rows = w.findAll('[draggable=true]')
    await rows[0].trigger('dragstart')
    await rows[2].trigger('drop')
    expect(w.emitted('reorder')![0]).toEqual([['c1.wav', 'c2.wav', 'c0.wav']])
  })

  it('passes verdicts, pick, reject and source ticks up with the candidate id', async () => {
    const w = mk()
    const row = w.findAll('[role=option]')[1]
    await row.find('[aria-label="Fit 4"]').trigger('click')
    await row.findAll('button').find((b) => b.text() === 'Pick')!.trigger('click')
    await row.findAll('button').find((b) => b.text() === 'Reject')!.trigger('click')
    await row.find('input[type=checkbox]').setValue(true)
    expect(w.emitted('verdict')![0]).toEqual(['c1.wav', { fit: 4 }])
    expect(w.emitted('pick')![0]).toEqual(['c1.wav'])
    expect(w.emitted('reject')![0]).toEqual(['c1.wav'])
    expect(w.emitted('source')![0]).toEqual(['c1.wav', true])
  })

  it('shows clone tests under their own candidate only', () => {
    const w = mk({ clones: [{ file: 'k.wav', candidate: 'c1.wav', text: 'Only for c1', scores: null }] })
    const rows = w.findAll('[role=option]')
    expect(rows[0].text()).not.toContain('Only for c1')
    expect(rows[1].text()).toContain('Only for c1')
  })

  it('shows an empty state with no candidates', () => {
    expect(mk({ candidates: [] }).text()).toContain('No candidates')
  })
})
