import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { api } from '../api/client'
import SpeakersView from './SpeakersView.vue'

vi.mock('../api/client', () => ({ api: { speakers: vi.fn(), registerAll: vi.fn(), pools: vi.fn() } }))

const sp = (name: string, status: string, origin = 'real', extra: Record<string, unknown> = {}) => ({ slug: name.toLowerCase(), name, origin, line_count: 3, status, has_pick: false, ...extra })
const router = () => createRouter({ history: createMemoryHistory(), routes: [{ path: '/speakers', component: { template: '<i />' } }, { path: '/speakers/:slug', component: { template: '<i />' } }] })

async function mountView() {
  const r = router()
  await r.push('/speakers')
  const w = mount(SpeakersView, { global: { plugins: [r] }, attachTo: document.body })
  await flushPromises()
  return { w, r }
}
const key = (k: string) => document.dispatchEvent(new KeyboardEvent('keydown', { key: k, bubbles: true, cancelable: true }))

const LIST = [
  sp('Pasqal', 'source'),
  sp('Muaran', 'needs_voice', 'designed', { kind: 'named', ranked: 2, candidates: 6 }),
  sp('Calligos', 'source', 'designed', { kind: 'named', has_pick: true, pick: 'c2.wav', ranked: 6, candidates: 6, sample: 'data/x/c2.wav' }),
  sp('pool_male', 'needs_voice', 'designed', { kind: 'slot', line_count: 0 }),
]

describe('SpeakersView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.speakers).mockResolvedValue(LIST as never)
    vi.mocked(api.pools).mockResolvedValue({ slots: [{ speaker_key: 'pool_male', lines: 6717 }] } as never)
    vi.mocked(api.registerAll).mockReset()
    document.body.innerHTML = ''
  })

  it('groups speakers, shows the hero summary, status text and slot lines from Pools', async () => {
    const { w } = await mountView()
    expect(w.text()).toContain('Needs a voice')
    expect(w.text()).toContain('Has a source')
    expect(w.text()).toContain('No saved profiles yet')
    expect(w.text()).toContain('4 speakers · 2 need a voice · 2 have a source · 1 picked, 0 registered')
    expect(w.find('[data-slug="muaran"]').text()).toContain('2 / 6 ranked')
    expect(w.find('[data-slug="calligos"]').text()).toContain('picked c2')
    expect(w.find('[data-slug="pasqal"]').text()).toContain('source set')
    expect(w.find('[data-slug="pool_male"]').text()).toContain('6,717')
    expect(w.text()).toContain('used by 6,717 unnamed lines')
    w.unmount()
  })

  it('still renders when Pools is unavailable', async () => {
    vi.mocked(api.pools).mockRejectedValue(new Error('404'))
    const { w } = await mountView()
    expect(w.find('[data-slug="pool_male"]').exists()).toBe(true)
    expect(w.text()).toContain('used by unnamed lines')
    w.unmount()
  })

  it('filters by text and by done state, with counts on the control', async () => {
    const { w } = await mountView()
    const seg = w.find('[aria-label="Show"]')
    expect(seg.text()).toContain('Done 1')
    expect(seg.text()).toContain('Unfinished 3')
    await seg.findAll('button')[2].trigger('click')
    expect(w.findAll('[data-slug]').map((e) => e.attributes('data-slug'))).toEqual(['calligos'])
    await seg.findAll('button')[0].trigger('click')
    await w.find('input').setValue('zzz')
    expect(w.text()).toContain('No speakers match')
    w.unmount()
  })

  it('moves with J and K, opens with Enter, and continues with N', async () => {
    const { w, r } = await mountView()
    key('j')
    await flushPromises()
    const first = w.find('[aria-current="true"]').attributes('data-slug')
    expect(first).toBe('muaran')
    key('j')
    await flushPromises()
    expect(w.find('[aria-current="true"]').attributes('data-slug')).toBe('pool_male')
    key('k')
    key('Enter')
    await flushPromises()
    expect(r.currentRoute.value.path).toBe('/speakers/muaran')
    w.unmount()
  })

  it('N goes to the speaker the Continue button names', async () => {
    const { w, r } = await mountView()
    expect(w.find('[data-continue]').text()).toContain('Continue: Muaran')
    key('n')
    await flushPromises()
    expect(r.currentRoute.value.path).toBe('/speakers/muaran')
    w.unmount()
  })

  it('confirms before registering, then summarises what was registered and skipped', async () => {
    vi.mocked(api.registerAll).mockResolvedValue({
      registered: [{ name: 'Calligos', cand: 'c2.wav' }],
      skipped: [{ name: 'Muaran', reason: 'no_pick', detail: 'designed, no pick yet' }, { name: 'Pasqal', reason: 'real', detail: 'real voice, nothing to register' }],
    })
    const { w } = await mountView()
    await w.find('[data-register-all]').trigger('click')
    expect(w.text()).toContain('Register 1 pick as active voices')
    expect(w.text()).toContain('skipped (3)')
    expect(api.registerAll).not.toHaveBeenCalled()
    key('Enter')
    await flushPromises()
    expect(api.registerAll).toHaveBeenCalledTimes(1)
    const res = w.find('[data-register-result]')
    expect(res.text()).toContain('Registered 1')
    expect(res.text()).toContain('Calligos → c2')
    expect(res.text()).toContain('designed, no pick yet (1)')
    expect(res.text()).toContain('real voice, nothing to register (1)')
    w.unmount()
  })

  it('Escape cancels the confirm without registering, and J is ignored while it is open', async () => {
    const { w } = await mountView()
    await w.find('[data-register-all]').trigger('click')
    key('j')
    expect(w.find('[aria-current="true"]').exists()).toBe(false)
    key('Escape')
    await flushPromises()
    expect(w.text()).not.toContain('as active voices')
    expect(api.registerAll).not.toHaveBeenCalled()
    w.unmount()
  })

  it('reports a failed registration and failed speakers by name', async () => {
    vi.mocked(api.registerAll).mockRejectedValue(new Error('disk full'))
    const { w } = await mountView()
    await w.find('[data-register-all]').trigger('click')
    key('Enter')
    await flushPromises()
    expect(w.text()).toContain('disk full')
    vi.mocked(api.registerAll).mockResolvedValue({ registered: [], skipped: [{ name: 'Calligos', reason: 'error', detail: 'no clip' }] })
    await w.findAll('button').find((b) => b.text() === 'Dismiss')?.trigger('click')
    await w.find('[data-register-all]').trigger('click')
    key('Enter')
    await flushPromises()
    expect(w.text()).toContain('Calligos: no clip')
    w.unmount()
  })

  it('disables Register all when nothing is picked', async () => {
    vi.mocked(api.speakers).mockResolvedValue([sp('Pasqal', 'source')] as never)
    const { w } = await mountView()
    expect(w.find('[data-register-all]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-continue]').attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('shows an empty state and an error with retry', async () => {
    vi.mocked(api.speakers).mockResolvedValue([])
    const a = await mountView()
    expect(a.w.text()).toContain('No speakers yet')
    a.w.unmount()
    vi.mocked(api.speakers).mockRejectedValue(new Error('server down'))
    const b = await mountView()
    expect(b.w.text()).toContain('server down')
    expect(b.w.text()).toContain('Retry')
    b.w.unmount()
  })
})
