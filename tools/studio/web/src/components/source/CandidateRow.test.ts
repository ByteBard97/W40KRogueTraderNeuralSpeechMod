import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { cand } from '../../test-utils/speakerCtx'
import CandidateRow from './CandidateRow.vue'

const mk = (over: Record<string, unknown> = {}, c = cand('c2.wav')) =>
  mount(CandidateRow, { props: { cand: c, rank: 1, picked: false, isSource: false, clones: [], speaker: 'Ruoldo', first: false, last: false, canRenderTests: false, ...over } })
const key = (w: ReturnType<typeof mk>, k: string, extra: Record<string, unknown> = {}) => w.find('.cand').trigger('keydown', { key: k, code: /^\d$/.test(k) ? `Digit${k}` : `Key${k.toUpperCase()}`, ...extra })

describe('CandidateRow', () => {
  it('shows the short id, scores, the seed, and flags a missing seed', () => {
    const w = mk()
    expect(w.text()).toContain('c2')
    expect(w.text()).toContain('p_us 0.10')
    expect(w.text()).toContain('england 0.80')
    expect(w.text()).toContain('seed 7')
    const none = mk({}, cand('c3.wav', { gen: null, scores: null }))
    expect(none.text()).toContain('no seed')
    expect(none.text()).toContain('unscored')
  })

  it('Pick is its own button and says Picked once picked; Undo reject on a rejected row', async () => {
    const w = mk()
    await w.findAll('button').find((b) => b.text() === 'Pick')!.trigger('click')
    expect(w.emitted('pick')).toHaveLength(1)
    const picked = mk({ picked: true })
    expect(picked.text()).toContain('Picked')
    expect(picked.attributes('aria-selected')).toBe('true')
    const rej = mk({}, cand('c2.wav', { verdict: { reject: true } }))
    expect(rej.text()).toContain('Undo reject')
    expect(rej.classes()).toContain('rej')
  })

  it('sends accent, accent score and fit from the controls', async () => {
    const w = mk()
    await w.findAll('[aria-label="Accent of c2"] button')[0].trigger('click')
    await w.find('[aria-label="Accent score 4"]').trigger('click')
    await w.find('[aria-label="Fit 5"]').trigger('click')
    expect(w.emitted('verdict')).toEqual([[{ accent: 'british' }], [{ accent_score: 4 }], [{ fit: 5 }]])
  })

  it('focused row keys: B/A/O accent, digits fit, Shift+digits accent score, P pick, R reject, Alt+arrows move', async () => {
    const w = mk()
    await key(w, 'a')
    await key(w, '3')
    await key(w, '2', { shiftKey: true })
    await key(w, 'p')
    await key(w, 'r')
    await key(w, 'ArrowUp', { altKey: true })
    await key(w, 'ArrowDown', { altKey: true })
    expect(w.emitted('verdict')).toEqual([[{ accent: 'american' }], [{ fit: 3 }], [{ accent_score: 2 }]])
    expect(w.emitted('pick')).toHaveLength(1)
    expect(w.emitted('reject')).toHaveLength(1)
    expect(w.emitted('move')).toEqual([[-1], [1]])
  })

  it('leaves keys alone while typing in a field', async () => {
    const w = mk()
    await w.find('input').trigger('keydown', { key: 'p', code: 'KeyP' })
    expect(w.emitted('pick')).toBeUndefined()
  })

  it('ticks a clone source, lists clone tests and disables Render 2 clone tests with a reason', async () => {
    const w = mk({ clones: [{ file: 'data/vd/k.wav', candidate: 'c2.wav', text: 'She almost ripped off my finger', scores: { p_us: 0.03 } }] })
    await w.find('input[type=checkbox]').setValue(true)
    expect(w.emitted('source')![0]).toEqual([true])
    expect(w.text()).toContain('She almost ripped off my finger')
    const none = mk()
    const btn = none.findAll('button').find((b) => b.text().includes('Render 2 clone tests'))!
    expect(btn.attributes('disabled')).toBeDefined()
    expect(btn.attributes('title')).toMatch(/server route/)
  })

  it('disables move buttons at the ends of the list', () => {
    const w = mk({ first: true })
    expect(w.find('[aria-label="Move c2 up"]').attributes('disabled')).toBeDefined()
    expect(w.find('[aria-label="Move c2 down"]').attributes('disabled')).toBeUndefined()
  })
})
