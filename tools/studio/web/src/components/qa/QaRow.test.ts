import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import QaRow from './QaRow.vue'

const clip = (over = {}) => ({
  guid: 'g1', wav: 'data/render/export/wav/g1.wav', text: 'For the Emperor.', context: '', speaker: 'Abelard', engine: 'voxcpm2', voice_source: 'clone',
  dur: 2.5, cps: 6.4, emotion: 'stern', instruct: '', ref_path: 'data/voices/abelard.wav', ref: 'abelard', real: ['data/render/r/real/a.wav'], old: 'data/render/export/wav/g1.wav',
  heard: 'for the emperor', wer: 0.1, flags: ['slow'], verdict: null, ...over,
})
const mountRow = (over = {}, fx: 'mild' | null = null) => mount(QaRow, { props: { clip: clip(over) as never, selected: false, fx } })

describe('QaRow', () => {
  it('shows meta, text, flags and heard text', () => {
    const t = mountRow().text()
    for (const s of ['Abelard', 'voxcpm2', 'ref abelard', '2.5 s', '6.4 chars/s', 'For the Emperor.', 'slow', 'heard: for the emperor', 'WER 0.1']) expect(t).toContain(s)
  })

  it('offers clip, reference, earlier render and real VO to play', () => {
    const labels = mountRow().findAll('.clip').map((b) => b.text())
    expect(labels).toEqual(['clip', 'reference', 'earlier render', 'game VO 1'])
  })

  it('points clip and earlier render at the compressor when it is on, not the reference', () => {
    expect(mountRow({}, 'mild').text()).toContain('clip (mild)')
  })

  it('emits good and bad, and clears when the same verdict is clicked again', async () => {
    const w = mountRow()
    await w.find('[data-good]').trigger('click')
    await w.find('[data-bad]').trigger('click')
    expect(w.emitted('verdict')).toEqual([['good'], ['bad']])
    const judged = mountRow({ verdict: { verdict: 'bad', tags: [], note: '' } })
    await judged.find('[data-bad]').trigger('click')
    expect(judged.emitted('verdict')![0]).toEqual([null])
  })

  it('hides tags and note until the clip is judged', () => {
    expect(mountRow().find('[data-note]').exists()).toBe(false)
    expect(mountRow({ verdict: { verdict: 'good', tags: [], note: '' } }).find('[data-note]').exists()).toBe(true)
  })

  it('toggles tags and emits the note', async () => {
    const w = mountRow({ verdict: { verdict: 'bad', tags: ['garbled'], note: 'x' } })
    const tags = w.findAll('[data-tag]')
    const garbled = tags.find((b) => b.text() === 'garbled')!
    expect(garbled.classes()).toContain('on')
    await garbled.trigger('click')
    await tags.find((b) => b.text() === 'robotic')!.trigger('click')
    expect(w.emitted('tags')).toEqual([[[]], [['garbled', 'robotic']]])
    await w.find('[data-note]').setValue('too fast')
    await w.find('[data-note]').trigger('change')
    expect(w.emitted('note')![0]).toEqual(['too fast'])
  })

  it('emits select when the row is clicked', async () => {
    const w = mountRow()
    await w.trigger('click')
    expect(w.emitted('select')).toHaveLength(1)
  })
})
