import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { designState, makeCtx, withCtx } from '../../test-utils/speakerCtx'
import { useSpeakersStore } from '../../stores/speakers'

const push = vi.hoisted(() => vi.fn())
vi.mock('vue-router', () => ({ useRouter: () => ({ push }) }))
import ProfileBar from './ProfileBar.vue'

const summary = (slug: string, has_pick = false) => ({ slug, name: slug, origin: 'designed', line_count: 1, status: 'source', has_pick })
function mk(detailOver: Record<string, unknown> = {}) {
  const ctx = makeCtx()
  Object.assign(ctx.detail.value as object, detailOver)
  const store = useSpeakersStore()
  store.list = [summary('a'), summary('ruoldo'), summary('z', true)] as never
  return { ctx, w: mount(ProfileBar, { props: { slug: 'ruoldo' }, ...withCtx(ctx) }) }
}
const btn = (w: ReturnType<typeof mk>['w'], t: string) => w.findAll('button').find((b) => b.text().startsWith(t))!

describe('ProfileBar', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('shows the speaker, origin, line count, position and picked count', () => {
    const { w } = mk()
    expect(w.text()).toContain('Governor Ruoldo')
    expect(w.text()).toContain('designed')
    expect(w.text()).toContain('2 lines')
    expect(w.text()).toContain('Speaker 2 / 3')
    expect(w.text()).toContain('1 picked')
  })

  it('links to the previous and next speaker and shows the keys', () => {
    const { w } = mk()
    expect(w.text()).toContain('Prev')
    expect(w.text()).toContain('Next')
    expect(w.find('[data-prev]').attributes('aria-disabled')).toBe('false')
  })

  it('Save profile and Set active call the context; Set active needs a saved profile; saved time is shown', async () => {
    const none = mk()
    await btn(none.w, 'Save profile').trigger('click')
    expect(none.ctx.saveProfile).toHaveBeenCalled()
    expect(btn(none.w, 'Set active').attributes('disabled')).toBeDefined()
    expect(none.w.text()).toContain('No profile saved')
    const saved = mk({ profile: { saved: new Date().toISOString() } })
    await btn(saved.w, 'Set active').trigger('click')
    expect(saved.ctx.setActive).toHaveBeenCalled()
    expect(saved.w.text()).toContain('Saved · just now')
  })

  it('Register names the pick, is disabled without one, and is absent for a real voice', async () => {
    const none = mk()
    expect(none.w.find('[data-register]').attributes('disabled')).toBeDefined()
    expect(none.w.find('[data-register]').text()).toContain('Register pick')
    const picked = mk({ design: designState({ pick: 'c1.wav' }) })
    expect(picked.w.find('[data-register]').text()).toContain('Register c1')
    await picked.w.find('[data-register]').trigger('click')
    expect(picked.ctx.registerPick).toHaveBeenCalled()
    expect(mk({ design: null }).w.find('[data-register]').exists()).toBe(false)
  })
})
