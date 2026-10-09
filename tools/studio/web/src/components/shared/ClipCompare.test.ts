import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'

const play = vi.fn()
vi.mock('../../composables/useAudioPlayer', () => ({
  useAudioPlayer: () => ({ play, playing: 'data/b.wav' }),
}))

import ClipCompare from './ClipCompare.vue'

const clips = [
  { key: 'bank', label: 'bank', path: 'data/a.wav' },
  { key: 'raw', label: 'raw clone', path: 'data/b.wav' },
  { key: 'fx', label: 'fx', path: null },
]

describe('ClipCompare', () => {
  it('renders a labelled button per clip and plays on click', async () => {
    const w = mount(ClipCompare, { props: { clips } })
    const btns = w.findAll('button')
    expect(btns.map((b) => b.text())).toEqual(expect.arrayContaining(['bank', 'raw clone', 'fx']))
    await btns[0].trigger('click')
    expect(play).toHaveBeenCalledWith('data/a.wav')
  })

  it('disables clips with no path and marks the playing one', () => {
    const w = mount(ClipCompare, { props: { clips } })
    const btns = w.findAll('button')
    expect(btns[2].attributes('disabled')).toBeDefined()
    expect(btns[1].classes()).toContain('is-playing')
  })
})
