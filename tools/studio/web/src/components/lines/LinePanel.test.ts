import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'

vi.mock('../../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play: vi.fn(), playing: null }) }))

import LinePanel from './LinePanel.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

const mk = (n: number) => ({ guid: `g${n}`, text: `line number ${n} `.repeat(6), emotion: n % 2 ? 'calm' : 'sad', intensity: 0.2, pace: 'normal', instruct: null, baseline: n === 0 ? null : `data/r/g${n}.wav` })

function mountWith(count: number) {
  const ctx = { lines: ref(Array.from({ length: count }, (_, i) => mk(i))), selectedLines: ref(new Set<string>()) }
  return { ctx, w: mount(LinePanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } }) }
}

describe('LinePanel', () => {
  it('ticks a line into the selection', async () => {
    const { ctx, w } = mountWith(4)
    await w.findAll('input[type=checkbox]')[1].setValue(true)
    expect([...ctx.selectedLines.value]).toEqual(['g1'])
  })

  it('filters by emotion chip and by search text', async () => {
    const { w } = mountWith(6)
    await w.find('[data-emo="sad"]').trigger('click')
    expect(w.findAll('.line')).toHaveLength(3)
    await w.find('input[type=search]').setValue('number 2')
    expect(w.findAll('.line')).toHaveLength(1)
  })

  it('caps rendering and shows more on request', async () => {
    const { w } = mountWith(450)
    expect(w.findAll('.line')).toHaveLength(200)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.line')).toHaveLength(400)
  })

  it('"spread" selects up to 6 lines and "clear" empties the selection', async () => {
    const { ctx, w } = mountWith(30)
    await w.find('[data-spread]').trigger('click')
    expect(ctx.selectedLines.value.size).toBeGreaterThan(0)
    expect(ctx.selectedLines.value.size).toBeLessThanOrEqual(6)
    await w.find('[data-clear]').trigger('click')
    expect(ctx.selectedLines.value.size).toBe(0)
  })

  it('disables the bank play button when there is no bank clip and shows an empty state', () => {
    const { w } = mountWith(2)
    expect(w.findAll('.play')[0].attributes('disabled')).toBeDefined()
    const empty = mount(LinePanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: { lines: ref([]), selectedLines: ref(new Set()) } } } })
    expect(empty.text()).toContain('No lines for this speaker')
  })
})
