import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it } from 'vitest'
import OptionsPanel from './OptionsPanel.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'
import { DEFAULT_OPTIONS } from '../../composables/useSpeakerState'

describe('OptionsPanel', () => {
  it('edits the shared options object', async () => {
    const ctx = { options: ref({ ...DEFAULT_OPTIONS }) }
    const w = mount(OptionsPanel, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.find('input[data-cfg]').setValue('3.5')
    await w.find('input[data-seed]').setValue('77')
    await w.find('input[data-continuation]').setValue(true)
    expect(ctx.options.value).toMatchObject({ cfg: 3.5, seed: '77', continuation: true })
    expect(w.text()).toMatch(/echo the reference/i)
  })
})
