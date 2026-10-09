import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({ api: { poolSpot: vi.fn(), poolSpotRecord: vi.fn() } }))

import SpotCheck from './SpotCheck.vue'

describe('SpotCheck', () => {
  beforeEach(() => vi.clearAllMocks())

  it('loads a sample, records ok/wrong per line and reports the result', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 'male_human', size: 2, remaining: 5, items: [{ guid: 'u1', text: 'One.', entry: null }, { guid: 'u2', text: 'Two.', entry: null }] })
    vi.mocked(api.poolSpotRecord).mockResolvedValue({ checked: 2, wrong: 1 })
    const w = mount(SpotCheck, { props: { slotId: 'male_human' } })
    await flushPromises()
    expect(w.text()).toContain('One.')
    await w.findAll('[data-ok]')[0].trigger('click')
    await w.findAll('[data-wrong]')[1].trigger('click')
    await w.find('[data-submit]').trigger('click')
    await flushPromises()
    expect(api.poolSpotRecord).toHaveBeenCalledWith('male_human', { u1: true, u2: false })
    expect(w.text()).toContain('1 wrong')
    expect(w.emitted('recorded')).toHaveLength(1)
  })

  it('does not submit until every line has a verdict', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 's', size: 1, remaining: 1, items: [{ guid: 'u1', text: 'One.', entry: null }] })
    const w = mount(SpotCheck, { props: { slotId: 's' } })
    await flushPromises()
    expect(w.find('[data-submit]').attributes('disabled')).toBeDefined()
  })

  it('shows an empty state when the slot has nothing left to check', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 's', size: 10, remaining: 0, items: [] })
    const w = mount(SpotCheck, { props: { slotId: 's' } })
    await flushPromises()
    expect(w.text()).toMatch(/nothing left/i)
  })

  it('pluralizes the submit button', async () => {
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 's', size: 1, remaining: 1, items: [{ guid: 'u1', text: 'One.', entry: null }] })
    const one = mount(SpotCheck, { props: { slotId: 's' } })
    await flushPromises()
    expect(one.find('[data-submit]').text()).toBe('Submit 1 check')
    vi.mocked(api.poolSpot).mockResolvedValue({ slot: 's', size: 2, remaining: 2, items: [{ guid: 'u1', text: 'One.', entry: null }, { guid: 'u2', text: 'Two.', entry: null }] })
    const two = mount(SpotCheck, { props: { slotId: 's' } })
    await flushPromises()
    expect(two.find('[data-submit]').text()).toBe('Submit 2 checks')
  })
})
