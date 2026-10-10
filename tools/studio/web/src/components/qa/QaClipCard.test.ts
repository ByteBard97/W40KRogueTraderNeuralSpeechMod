import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const audio = { src: '', currentTime: 0, duration: 10, volume: 1, loop: false, playbackRate: 1, ended: false, play: vi.fn().mockResolvedValue(undefined), pause: vi.fn(), addEventListener: vi.fn() }
vi.stubGlobal('Audio', vi.fn(() => audio))

import { useGlobalAudio } from '../../composables/globalAudio'
import QaClipCard from './QaClipCard.vue'

const clip = (over = {}) => ({
  guid: 'g1', wav: 'data/render/export/wav/g1.wav', text: 'For the Emperor.', context: 'Narration around it.', speaker: 'Abelard', engine: 'voxcpm2', voice_source: 'clone',
  dur: 2.5, cps: 6.4, emotion: 'stern', instruct: '', ref_path: 'data/voices/abelard.wav', ref: 'abelard',
  real: [{ label: 'Real: Pasqal', path: 'data/render/r/real/a.wav', text: 'Said by Pasqal.', full_line: false }],
  old: null, heard: 'for the emperor', wer: 0.1, flags: ['slow', 'mystery'], verdict: null, ...over,
})
const mountCard = (over = {}, fx: '' | 'mild' = '') => mount(QaClipCard, { props: { clip: clip(over) as never, position: 2, total: 11051, fx }, attachTo: document.body })

beforeEach(() => { const g = useGlobalAudio(); g.stop(); g.state.id = null; audio.play.mockClear() })

describe('QaClipCard', () => {
  it('shows meta, text, the sent-as box, flag reasons and the ASR box', () => {
    const w = mountCard()
    const t = w.text()
    for (const s of ['Abelard', 'voxcpm2', 'abelard', '2.5 s', '6.4 chars/s', 'stern', 'clip 2 of 11,051', 'For the Emperor.', 'Sent to the model as', 'Narration around it.', 'below 3.5 chars/s', 'mystery', 'heard', 'word error rate']) expect(t).toContain(s)
    w.unmount()
  })

  it('omits optional boxes when the clip has nothing for them', () => {
    const w = mountCard({ context: '', heard: '', flags: [], wer: null })
    expect(w.find('[data-context]').exists()).toBe(false)
    expect(w.find('[data-heard]').exists()).toBe(false)
    expect(w.find('.flagrow').exists()).toBe(false)
    w.unmount()
  })

  it('offers clip, reference, earlier render and real line, disabling what is missing', () => {
    const w = mountCard()
    const slots = w.findAll('.slot')
    expect(slots.map((s) => s.find('b').text())).toEqual(['Clip', 'Clone reference', 'Earlier render', 'Real: Pasqal'])
    expect(slots.map((s) => s.find('.k').text())).toEqual(['A', 'S', 'D', 'F'])
    expect(slots[2].attributes('disabled')).toBeDefined()
    expect(slots[2].text()).toContain('no clip')
    w.unmount()
  })

  it('shows a disabled Real line slot when the line is not voiced', () => {
    const w = mountCard({ real: [] })
    expect(w.findAll('.slot')[3].attributes('disabled')).toBeDefined()
    expect(w.findAll('.slot')[3].text()).toContain('Real line')
    w.unmount()
  })

  it('A S D F switch sources and Space plays the chosen one, through the compressor for the clip', async () => {
    const w = mountCard({}, 'mild')
    const g = useGlobalAudio()
    ;(w.vm as unknown as { playSelected: () => void }).playSelected()
    expect(audio.src).toContain('/fx-file')
    expect(g.nowPlaying.value.title).toBe('Abelard · Clip')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 's' }))
    await w.vm.$nextTick()
    expect(w.findAll('.slot')[1].attributes('aria-pressed')).toBe('true')
    expect(audio.src).toContain('voices%2Fabelard.wav')
    expect(audio.src).not.toContain('fx-file')
    w.unmount()
  })

  it('falls back to the clip when a key picks a missing source', async () => {
    const w = mountCard()
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'd' }))
    await w.vm.$nextTick()
    expect(w.findAll('.slot')[0].attributes('aria-pressed')).toBe('true')
    w.unmount()
  })

  it('emits good, bad and a clear when the active one is clicked again', async () => {
    const w = mountCard()
    const [good, bad] = w.findAll('.judge .j')
    await good.trigger('click')
    await bad.trigger('click')
    expect(w.emitted('verdict')).toEqual([['good'], ['bad']])
    const judged = mountCard({ verdict: { verdict: 'bad', tags: [], note: '' } })
    await judged.findAll('.judge .j')[1].trigger('click')
    expect(judged.emitted('verdict')![0]).toEqual([null])
    expect(judged.find('[data-saved]').text()).toContain('Saved · bad')
    w.unmount()
    judged.unmount()
  })

  it('shows ten numbered tags and toggles them', async () => {
    const w = mountCard({ verdict: { verdict: 'bad', tags: ['garbled'], note: '' } })
    const tags = w.findAll('[data-tag]')
    expect(tags).toHaveLength(10)
    expect(tags.map((t) => t.find('kbd').text()).join('')).toBe('1234567890')
    expect(tags[1].attributes('aria-pressed')).toBe('true')
    await tags[1].trigger('click')
    await tags[5].trigger('click')
    expect(w.emitted('tags')).toEqual([[[]], [['garbled', 'robotic']]])
    w.unmount()
  })

  it('saves the note on Enter or change, only when it differs', async () => {
    const w = mountCard({ verdict: { verdict: 'bad', tags: [], note: 'old' } })
    const input = w.find('[data-note]')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('note')).toBeUndefined()
    await input.setValue('too fast')
    await input.trigger('keydown', { key: 'Enter' })
    expect(w.emitted('note')).toEqual([['too fast']])
    w.unmount()
  })

  it('clear is disabled without a verdict and next unjudged emits', async () => {
    const w = mountCard()
    expect(w.find('[data-clear]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-saved]').text()).toBe('Unjudged')
    await w.find('[data-next-unjudged]').trigger('click')
    expect(w.emitted('nextUnjudged')).toHaveLength(1)
    w.unmount()
  })
})
