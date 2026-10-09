import { beforeEach, describe, expect, it, vi } from 'vitest'

const audio = { src: '', play: vi.fn().mockResolvedValue(undefined), pause: vi.fn(), addEventListener: vi.fn() }
vi.stubGlobal('Audio', vi.fn(() => audio))

import { useAudioPlayer } from './useAudioPlayer'

describe('useAudioPlayer', () => {
  beforeEach(() => {
    audio.play.mockClear()
    audio.pause.mockClear()
    useAudioPlayer().stop()
  })

  it('plays a path through /file and tracks it', () => {
    const p = useAudioPlayer()
    p.play('data/a.wav')
    expect(audio.src).toContain('/file?p=data%2Fa.wav')
    expect(audio.play).toHaveBeenCalled()
    expect(p.playing.value).toBe('data/a.wav')
  })

  it('toggles off when the same path is played twice and switches when another is played', () => {
    const p = useAudioPlayer()
    p.play('data/a.wav')
    p.play('data/a.wav')
    expect(p.playing.value).toBeNull()
    p.play('data/a.wav')
    p.play('data/b.wav')
    expect(p.playing.value).toBe('data/b.wav')
  })
})
