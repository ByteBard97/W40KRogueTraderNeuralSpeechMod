import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { slot, summaryOf } from '../../test-utils/poolFixtures'

vi.mock('../../api/client', () => ({ api: { poolSpot: vi.fn(), poolSpotRecord: vi.fn(), pools: vi.fn(), poolQueue: vi.fn() } }))
import SpotCheck from './SpotCheck.vue'

const items = [1, 2, 3].map((n) => ({ guid: `u${n}`, text: `Line ${n}.`, entry: null, wav: n === 3 ? null : `data/render/export/${n}.wav` }))
const sample = (over = {}) => ({ slot: 'male_human', size: 10, remaining: 3, items, ...over })

async function make() {
  setActivePinia(createPinia())
  vi.mocked(api.poolSpot).mockResolvedValue(sample())
  vi.mocked(api.pools).mockResolvedValue(summaryOf([slot('male_human', 'Male human')]))
  vi.mocked(api.poolQueue).mockResolvedValue([])
  const w = mount(SpotCheck, { props: { slotId: 'male_human', slotName: 'Male human' } })
  await flushPromises()
  return w
}
const markButtons = (w: Awaited<ReturnType<typeof make>>, n: number) => w.findAll('.sc')[n].findAll('.seg button')

describe('SpotCheck', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows the sampled lines with play buttons and a counter', async () => {
    const w = await make()
    expect(w.text()).toContain('Spot check · Male human')
    expect(w.text()).toContain('0 / 3 marked')
    expect(w.findAll('.sc')).toHaveLength(3)
    expect(w.findAll('button.play')[2].attributes('disabled')).toBeDefined()
  })

  it('keeps Submit disabled until every line is marked, and counts wrongs', async () => {
    const w = await make()
    const submit = () => w.find('[data-submit]').attributes('disabled')
    expect(submit()).toBeDefined()
    await markButtons(w, 0)[0].trigger('click')
    await markButtons(w, 1)[1].trigger('click')
    expect(w.text()).toContain('1 left · 1 wrong so far')
    expect(submit()).toBeDefined()
    await markButtons(w, 2)[0].trigger('click')
    expect(submit()).toBeUndefined()
    expect(w.text()).toContain('1 wrong of 3')
  })

  it('submits right = true and wrong = false, then loads a fresh sample', async () => {
    const w = await make()
    vi.mocked(api.poolSpotRecord).mockResolvedValue({ checked: 3, wrong: 1 })
    await markButtons(w, 0)[0].trigger('click')
    await markButtons(w, 1)[1].trigger('click')
    await markButtons(w, 2)[0].trigger('click')
    await w.find('[data-submit]').trigger('click')
    await flushPromises()
    expect(api.poolSpotRecord).toHaveBeenCalledWith('male_human', { u1: true, u2: false, u3: true })
    expect(api.poolSpot).toHaveBeenCalledTimes(2)
    expect(w.text()).toContain('0 / 3 marked')
  })

  it('is driven by keys through its exposed methods: mark advances, step moves', async () => {
    const w = await make()
    const vm = w.vm as unknown as { mark: (v: 'right' | 'wrong') => void; step: (d: number) => void }
    vm.mark('right')
    vm.mark('wrong')
    await w.vm.$nextTick()
    expect(w.text()).toContain('2 / 3 marked')
    expect(w.findAll('.sc')[2].attributes('aria-current')).toBe('true')
    vm.step(-1)
    await w.vm.$nextTick()
    expect(w.findAll('.sc')[1].attributes('aria-current')).toBe('true')
  })

  it('says when there is nothing left to check', async () => {
    setActivePinia(createPinia())
    vi.mocked(api.poolSpot).mockResolvedValue(sample({ items: [], remaining: 0 }))
    const w = mount(SpotCheck, { props: { slotId: 'male_human', slotName: 'Male human' } })
    await flushPromises()
    expect(w.text()).toContain('Nothing left to check')
  })

  it('shows a load error', async () => {
    setActivePinia(createPinia())
    vi.mocked(api.poolSpot).mockRejectedValue(new Error('no slot'))
    const w = mount(SpotCheck, { props: { slotId: 'x', slotName: 'X' } })
    await flushPromises()
    expect(w.text()).toContain('no slot')
  })
})
