import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import { makeCtx, withCtx } from '../../test-utils/speakerCtx'
import RealClipList from './RealClipList.vue'

const clips = [
  { id: 'E1', wav: 'data/v/E1.wav', duration: 5, text: 'Hello.', curated_rank: 1, noise_db: -60 },
  { id: 'E2', wav: 'data/v/E2.wav', duration: 3, text: 'Bye.', curated_rank: null, noise_db: null },
]

function mountWith(selected: string[], list = clips) {
  const ctx = makeCtx({ selectedSources: ref(new Set(selected)) })
  return { ctx, w: mount(RealClipList, { props: { clips: list }, ...withCtx(ctx) }) }
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

  it('shows the curated badge, duration and noise, and an empty message', () => {
    const { w } = mountWith([])
    expect(w.text()).toContain('curated #1')
    expect(w.text()).toContain('uncurated')
    expect(w.text()).toContain('5.0 s')
    expect(w.text()).toContain('noise -60 dB')
    expect(mountWith([], []).w.text()).toContain('No real clips')
  })
})
