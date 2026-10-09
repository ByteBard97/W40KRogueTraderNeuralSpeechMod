import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import CandidateRanker from './CandidateRanker.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const cands = ['c0.wav', 'c1.wav', 'c2.wav'].map((id, i) => ({
  id, file: `data/vd/${id}`, scores: { p_us: 0.1 * (i + 1), top: 'england', p_top: 0.8 }, verdict: {}, gen: null,
}))

describe('CandidateRanker', () => {
  it('shows rank numbers in the given order', () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: ['c1.wav'] } })
    const rows = w.findAll('.cand')
    expect(rows).toHaveLength(3)
    expect(rows[0].text()).toContain('c1')            // ranked ones first
  })

  it('moves a candidate down with the button and emits the full new order', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    await w.findAll('.cand')[0].find('[data-move="down"]').trigger('click')
    expect(w.emitted('reorder')![0]).toEqual([['c1.wav', 'c0.wav', 'c2.wav']])
  })

  it('moves up with the button and does nothing at the edges', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    await w.findAll('.cand')[2].find('[data-move="up"]').trigger('click')
    expect(w.emitted('reorder')![0]).toEqual([['c0.wav', 'c2.wav', 'c1.wav']])
    await w.findAll('.cand')[0].find('[data-move="up"]').trigger('click')
    expect(w.emitted('reorder')).toHaveLength(1)
  })

  it('reorders by drag and drop', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    const rows = w.findAll('.cand')
    await rows[0].trigger('dragstart')
    await rows[2].trigger('drop')
    expect(w.emitted('reorder')![0]).toEqual([['c1.wav', 'c2.wav', 'c0.wav']])
  })

  it('emits verdicts for accent, fit and reject', async () => {
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    const row = w.findAll('.cand')[0]
    await row.find('[data-accent="british"]').trigger('click')
    await row.find('[data-reject]').trigger('click')
    expect(w.emitted('verdict')![0]).toEqual([{ cand: 'c0.wav', accent: 'british' }])
    expect(w.emitted('verdict')![1]).toEqual([{ cand: 'c0.wav', reject: true }])
  })

  it('shows an empty state with no candidates', () => {
    const w = mount(CandidateRanker, { props: { candidates: [], order: [] } })
    expect(w.text()).toContain('No candidates')
  })

  it('ticks a candidate as a clone source through the speaker context, and hides the box without one', async () => {
    const ctx = { selectedSources: ref(new Set<string>()) }
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [] }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.findAll('input[data-source]')[1].setValue(true)
    expect([...ctx.selectedSources.value]).toEqual(['cand:c1.wav'])
    await w.findAll('input[data-source]')[1].setValue(false)
    expect(ctx.selectedSources.value.size).toBe(0)
    const bare = mount(CandidateRanker, { props: { candidates: cands, order: [] } })
    expect(bare.find('input[data-source]').exists()).toBe(false)
  })

  it('marks candidates that have no recorded seed', () => {
    const withSeed = { ...cands[0], id: 'c9.wav', gen: { seed: 7 } }
    const w = mount(CandidateRanker, { props: { candidates: [cands[0], withSeed], order: [] } })
    const rows = w.findAll('.cand')
    expect(rows[0].find('[data-no-seed]').exists()).toBe(true)
    expect(rows[1].find('[data-no-seed]').exists()).toBe(false)
    expect(rows[1].text()).toContain('seed 7')
  })
})
