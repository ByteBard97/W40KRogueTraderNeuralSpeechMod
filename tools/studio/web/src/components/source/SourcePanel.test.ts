import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { designState, makeCtx, withCtx } from '../../test-utils/speakerCtx'

vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api: { jobsActive: vi.fn(async () => []) } }))
import SourcePanel from './SourcePanel.vue'

const clip = { id: 'E1', wav: 'data/v/E1.wav', duration: 5, text: 'Hello.', curated_rank: 1, noise_db: null }
function mk(origin: 'real' | 'designed', clips: unknown[], design: unknown) {
  const ctx = makeCtx()
  Object.assign(ctx.detail.value as object, { summary: { slug: 'x', name: 'X', origin }, clips, design })
  return mount(SourcePanel, withCtx(ctx))
}

describe('SourcePanel', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('designed speaker: Designed tab first, summary counts candidates, scored and pick', () => {
    const w = mk('designed', [], designState({ pick: 'c1.wav' }))
    expect(w.text()).toContain('Source · designed voice')
    expect(w.text()).toContain('3 candidates · 0 / 3 scored · picked c1')
    expect(w.findAll('[aria-label="Source type"] button').map((b) => b.text())).toEqual(['Designed', 'Supplied wav'])
    expect(w.find('[role=listbox]').exists()).toBe(true)
  })

  it('real speaker: catalogue clips and supplied only, no designed tab', async () => {
    const w = mk('real', [clip], null)
    expect(w.text()).toContain('Source · real voice')
    expect(w.findAll('[aria-label="Source type"] button').map((b) => b.text())).toEqual(['Catalogue clips', 'Supplied wav'])
    expect(w.text()).toContain('curated #1')
    await w.findAll('[aria-label="Source type"] button')[1].trigger('click')
    expect(w.find('input[data-wav]').exists()).toBe(true)
  })

  it('designed speaker with catalogue clips offers all three tabs', () => {
    expect(mk('designed', [clip], designState()).findAll('[aria-label="Source type"] button')).toHaveLength(3)
  })
})
