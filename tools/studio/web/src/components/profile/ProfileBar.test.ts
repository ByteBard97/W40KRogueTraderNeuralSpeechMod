import { mount } from '@vue/test-utils'
import { ref } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import ProfileBar from './ProfileBar.vue'
import { SPEAKER_CTX_KEY } from '../../composables/useSpeakerContext'

describe('ProfileBar', () => {
  it('calls saveProfile and setActive and shows the notice', async () => {
    const ctx = { saveProfile: vi.fn(), setActive: vi.fn(), notice: ref('saved'), detail: ref({ profile: { saved: 'today' } }) }
    const w = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    const [save, active] = w.findAll('button')
    await save.trigger('click')
    await active.trigger('click')
    expect(ctx.saveProfile).toHaveBeenCalled()
    expect(ctx.setActive).toHaveBeenCalled()
    expect(w.text()).toContain('saved')
  })

  it('shows Register pick only for designed speakers and disables it without a pick', async () => {
    const mk = (design: unknown) => ({ saveProfile: vi.fn(), setActive: vi.fn(), registerPick: vi.fn(), notice: ref(''), detail: ref({ profile: null, design }) })
    const none = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: mk(null) } } })
    expect(none.find('[data-register]').exists()).toBe(false)
    const noPick = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: mk({ pick: null }) } } })
    expect(noPick.find('[data-register]').attributes('disabled')).toBeDefined()
    const ctx = mk({ pick: 'c1.wav' })
    const w = mount(ProfileBar, { global: { provide: { [SPEAKER_CTX_KEY as symbol]: ctx } } })
    await w.find('[data-register]').trigger('click')
    expect(ctx.registerPick).toHaveBeenCalled()
  })
})
