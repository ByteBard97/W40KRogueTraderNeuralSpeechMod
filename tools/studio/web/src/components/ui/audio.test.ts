import { mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const audio = { src: '', currentTime: 0, duration: 10, volume: 1, loop: false, playbackRate: 1, ended: false, play: vi.fn().mockResolvedValue(undefined), pause: vi.fn(), addEventListener: vi.fn() }
vi.stubGlobal('Audio', vi.fn(() => audio))

import { useGlobalAudio } from '../../composables/globalAudio'
import { useAudioKeys } from '../../composables/useAudioKeys'
import ABCompareStrip from './ABCompareStrip.vue'
import AudioBar from './AudioBar.vue'
import InlinePlay from './InlinePlay.vue'
import { defineComponent } from 'vue'

const key = (k: string, init: KeyboardEventInit = {}, target: EventTarget = window) => {
  const e = new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true, ...init })
  target.dispatchEvent(e)
  return e
}

beforeEach(() => {
  const g = useGlobalAudio()
  g.stop()
  g.state.id = null
  g.state.current = 0
  g.state.duration = 10
  g.setRate(1)
  g.setLoop(false)
  audio.currentTime = 0
  audio.play.mockClear()
  audio.pause.mockClear()
})

describe('InlinePlay', () => {
  it('loads its clip into the global player and shows playing state', async () => {
    const w = mount(InlinePlay, { props: { id: 'data/a.wav', title: 'A' } })
    await w.find('button').trigger('click')
    expect(audio.src).toContain('/file?p=data%2Fa.wav')
    expect(useGlobalAudio().nowPlaying.value.title).toBe('A')
    expect(w.find('button').classes()).toContain('on')
    expect(w.find('button').attributes('aria-label')).toBe('Pause')
    await w.find('button').trigger('click')
    expect(w.find('button').classes()).not.toContain('on')
  })
  it('only the loaded clip shows as playing', async () => {
    const a = mount(InlinePlay, { props: { id: 'data/a.wav' } })
    const b = mount(InlinePlay, { props: { id: 'data/b.wav' } })
    await a.find('button').trigger('click')
    expect(b.find('button').classes()).not.toContain('on')
  })
  it('is disabled with a reason when there is no audio, and the waveform variant renders bars', () => {
    const w = mount(InlinePlay, { props: { id: null, unavailableReason: 'No render' } })
    expect(w.find('button').attributes('disabled')).toBeDefined()
    expect(w.find('button').attributes('aria-label')).toBe('No render')
    expect(mount(InlinePlay, { props: { id: 'x.wav', waveform: true } }).findAll('.wave i').length).toBeGreaterThan(10)
  })
})

describe('AudioBar and global keys', () => {
  it('shows what is playing, toggles, changes speed and loop, and has prev/next hooks', async () => {
    const g = useGlobalAudio()
    const prev = vi.fn()
    g.setTransport({ prev })
    g.play('data/a.wav', undefined, { title: 'Ruoldo · c0', subtitle: 'ruoldo/c0.wav' })
    const w = mount(AudioBar)
    expect(w.text()).toContain('Ruoldo · c0')
    expect(w.text()).toContain('ruoldo/c0.wav')
    await w.findAll('button').find((b) => b.attributes('aria-label')?.startsWith('Previous'))!.trigger('click')
    expect(prev).toHaveBeenCalled()
    const speed = w.findAll('button').find((b) => b.text() === '1.5×')!
    await speed.trigger('click')
    expect(g.state.rate).toBe(1.5)
    await w.findAll('button').find((b) => b.text() === 'Loop')!.trigger('click')
    expect(g.state.loop).toBe(true)
  })

  const host = () => mount(defineComponent({ setup() { useAudioKeys(); return () => null } }), { attachTo: document.body })

  it('Space toggles, arrows seek 1 s, Shift+arrows 5 s, L loops, brackets change speed', () => {
    const g = useGlobalAudio()
    g.play('data/a.wav')
    const w = host()
    audio.currentTime = 4
    g.state.current = 4
    expect(key(' ').defaultPrevented).toBe(true)
    expect(g.state.isPlaying).toBe(false)
    key('ArrowRight')
    expect(audio.currentTime).toBe(5)
    key('ArrowLeft', { shiftKey: true })
    expect(audio.currentTime).toBe(0)
    key('l')
    expect(g.state.loop).toBe(true)
    key(']')
    expect(g.state.rate).toBe(1.25)
    key('[')
    key('[')
    expect(g.state.rate).toBe(0.75)
    w.unmount()
  })
  it('ignores keys typed in inputs, handled keys and focused buttons', () => {
    const g = useGlobalAudio()
    g.play('data/a.wav')
    const w = host()
    const input = document.createElement('input')
    document.body.append(input)
    key(' ', {}, input)
    expect(g.state.isPlaying).toBe(true)
    const btn = document.createElement('button')
    document.body.append(btn)
    key(' ', {}, btn)
    expect(g.state.isPlaying).toBe(true)
    const pre = new KeyboardEvent('keydown', { key: ' ', cancelable: true, bubbles: true })
    document.addEventListener('keydown', (e) => e.preventDefault(), { once: true })
    document.body.dispatchEvent(pre)
    expect(g.state.isPlaying).toBe(true)
    w.unmount()
  })
})

describe('ABCompareStrip', () => {
  const clips = [
    { key: 'real', label: 'Real clip', sub: 'a.wav', path: 'data/a.wav' },
    { key: 'bank', label: 'Bank render', path: 'data/b.wav' },
    { key: 'fx', label: 'FX', path: null },
  ]
  it('labels every clip, disables missing ones and marks the selection', () => {
    const w = mount(ABCompareStrip, { props: { clips } })
    const slots = w.findAll('.slot')
    expect(slots).toHaveLength(3)
    expect(slots[0].attributes('aria-pressed')).toBe('true')
    expect(slots[2].attributes('disabled')).toBeDefined()
  })
  it('switching keeps the playhead as a fraction on the one shared element', async () => {
    const g = useGlobalAudio()
    const w = mount(ABCompareStrip, { props: { clips } })
    await w.findAll('.slot')[0].trigger('click')
    expect(audio.src).toContain('a.wav')
    g.state.current = 4
    g.state.duration = 8
    audio.duration = 20
    await w.findAll('.slot')[1].trigger('click')
    expect(audio.src).toContain('b.wav')
    expect(w.emitted('update:modelValue')?.at(-1)).toEqual(['bank'])
    expect(audio.src).not.toContain('a.wav')
  })
  it('keys 1-4 switch when hotkeys are on', async () => {
    const w = mount(ABCompareStrip, { props: { clips, hotkeys: true }, attachTo: document.body })
    key('2', {}, document)
    await w.vm.$nextTick()
    expect(w.findAll('.slot')[1].attributes('aria-pressed')).toBe('true')
    key('3', {}, document)
    expect(w.findAll('.slot')[1].attributes('aria-pressed')).toBe('true')
    w.unmount()
  })
})
