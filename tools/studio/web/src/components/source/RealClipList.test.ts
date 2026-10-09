import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import RealClipList from './RealClipList.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const clips = [
  { id: 'E1', wav: 'data/v/E1.wav', duration: 5, text: 'Hello.', curated_rank: 1, noise_db: -60 },
  { id: 'E2', wav: 'data/v/E2.wav', duration: 3, text: 'Bye.', curated_rank: null, noise_db: null },
]

function mountWith(selected: string[]) {
  const ctx = { selectedSources: ref(new Set(selected)) }
  return { ctx, w: mount(RealClipList, { props: { clips }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('RealClipList', () => {
  it('ticks and unticks sources through the context', async () => {
    const { ctx, w } = mountWith(['real:E1'])
    const boxes = w.findAll('input[type=checkbox]')
    expect((boxes[0].element as HTMLInputElement).checked).toBe(true)
    await boxes[1].setValue(true)
    expect([...ctx.selectedSources.value].sort()).toEqual(['real:E1', 'real:E2'])
    await boxes[0].setValue(false)
    expect([...ctx.selectedSources.value]).toEqual(['real:E2'])
  })

  it('shows the curated badge and an empty message', () => {
    const { w } = mountWith([])
    expect(w.text()).toContain('curated #1')
    const empty = mount(RealClipList, { props: { clips: [] }, global: { provide: { [SPEAKER_CTX_KEY as symbol]: { selectedSources: ref(new Set()) } } } })
    expect(empty.text()).toContain('No real clips')
  })
})
