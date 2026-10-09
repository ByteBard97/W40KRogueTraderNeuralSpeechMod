import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

const play = vi.hoisted(() => vi.fn())
vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play, playing: null }) }))

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

  it('shows p_us, the top label with its probability, and unscored when there are no scores', () => {
    const unscored = { ...cands[0], id: 'c8.wav', scores: null }
    const w = mount(CandidateRanker, { props: { candidates: [cands[1], unscored], order: [] } })
    const rows = w.findAll('.cand')
    expect(rows[0].text()).toContain('p_us 0.20')
    expect(rows[0].text()).toContain('england 0.80')
    expect(rows[0].text()).not.toContain('unscored')
    expect(rows[1].text()).toContain('unscored')
  })

  it('lists clone tests under their own candidate only, with text and p_us, and plays them', async () => {
    const clones = [
      { file: 'data/vd/clones/m/c1_L0.wav', candidate: 'c1.wav', text: 'Real line one.', scores: { p_us: 0.75, top: 'england', p_top: 0.5 } },
      { file: 'data/vd/clones/m/c1_L1.wav', candidate: 'c1.wav', text: 'Real line two.', scores: null },
    ]
    const w = mount(CandidateRanker, { props: { candidates: cands, order: [], clones } })
    const rows = w.findAll('.cand')
    expect(rows[0].findAll('[data-clone]')).toHaveLength(0)
    const mine = rows[1].findAll('[data-clone]')
    expect(mine).toHaveLength(2)
    expect(mine[0].text()).toContain('p_us 0.75')
    expect(mine[0].text()).toContain('Real line one.')
    expect(mine[1].text()).not.toContain('p_us')
    await mine[0].find('button').trigger('click')
    expect(play).toHaveBeenCalledWith('data/vd/clones/m/c1_L0.wav')
  })
})
