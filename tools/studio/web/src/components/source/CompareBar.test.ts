import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it } from 'vitest'
import { useGlobalAudio } from '../../composables/globalAudio'
import { cand } from '../../test-utils/speakerCtx'
import CompareBar from './CompareBar.vue'

const cands = ['c2.wav', 'c1.wav', 'c0.wav'].map((id) => cand(id))
const clones = [
  { file: 'data/k/c2_a.wav', candidate: 'c2.wav', text: 'She almost ripped off my finger', scores: null },
  { file: 'data/k/c2_b.wav', candidate: 'c2.wav', text: 'I am a bit tipsy', scores: null },
]
const mk = () => mount(CompareBar, { attachTo: document.body, props: { candidates: cands, clones, speaker: 'Ruoldo' } })

describe('CompareBar', () => {
  beforeEach(() => useGlobalAudio().stop())

  it('lists a slot per candidate with its key and top score, and lines for the design sample and clone tests', () => {
    const w = mk()
    expect(w.findAll('.slot')).toHaveLength(3)
    expect(w.findAll('.slot')[0].text()).toContain('c2')
    expect(w.findAll('.slot')[0].text()).toContain('england 0.80')
    expect(w.text()).toContain('Design sample')
    expect(w.text()).toContain('Test 1')
    expect(w.text()).toContain('Test 2')
    w.unmount()
  })

  it('plays the candidate in the global player, switches with number keys, and keeps typing fields alone', async () => {
    const audio = useGlobalAudio()
    const w = mk()
    await w.findAll('.slot')[0].trigger('click')
    expect(audio.state.id).toBe('data/vd/c2.wav')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: '2', bubbles: true }))
    expect(audio.state.id).toBe('data/vd/c1.wav')
    const input = document.createElement('input')
    document.body.appendChild(input)
    input.dispatchEvent(new KeyboardEvent('keydown', { key: '3', bubbles: true }))
    expect(audio.state.id).toBe('data/vd/c1.wav')
    input.remove()
    w.unmount()
  })

  it('a handled key (a focused row used the digit) does not also switch the candidate', () => {
    const audio = useGlobalAudio()
    const w = mk()
    const ev = new KeyboardEvent('keydown', { key: '3', bubbles: true, cancelable: true })
    ev.preventDefault()
    document.dispatchEvent(ev)
    expect(audio.state.id).not.toBe('data/vd/c0.wav')
    w.unmount()
  })

  it('on a test line a candidate without a clone test is disabled', async () => {
    const w = mk()
    await w.findAll('.seg button')[1].trigger('click')
    const slots = w.findAll('.slot')
    expect(slots[0].attributes('disabled')).toBeUndefined()
    expect(slots[1].attributes('disabled')).toBeDefined()
    expect(slots[1].text()).toContain('no clip')
    w.unmount()
  })
})
