import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import FxPanel from './FxPanel.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

describe('FxPanel', () => {
  it('toggles presets in selection order', async () => {
    const ctx = { fxAvailable: ref(['Clean', 'Servitor']), fxChosen: ref<string[]>([]) }
    const w = mount(FxPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.find('[data-fx="Servitor"]').trigger('click')
    await w.find('[data-fx="Clean"]').trigger('click')
    expect(ctx.fxChosen.value).toEqual(['Servitor', 'Clean'])
    expect(w.text()).toContain('1. Servitor')
    await w.find('[data-fx="Servitor"]').trigger('click')
    expect(ctx.fxChosen.value).toEqual(['Clean'])
  })

  it('shows an empty state with no presets', () => {
    const ctx = { fxAvailable: ref<string[]>([]), fxChosen: ref<string[]>([]) }
    const w = mount(FxPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    expect(w.text()).toContain('No FX presets found')
  })
})
