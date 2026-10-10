import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { usePoolsStore } from '../../stores/pools'
import { slot, summaryOf } from '../../test-utils/poolFixtures'

vi.mock('../../api/client', () => ({ api: { poolRoutes: vi.fn(), poolOverride: vi.fn(), pools: vi.fn(), poolQueue: vi.fn() } }))
import RoutesTable from './RoutesTable.vue'

const rows = [
  { guid: 'g1', text: 'Lord Captain, report.', to: 'slot', slot: 'male_human', entry: 'C|1', confidence: 0.62, reasons: [], source: 'auto', entry_name: 'Vox Master', entry_label: 'x', wav: 'data/render/export/g1.wav' },
  { guid: 'g2', text: 'I wish you luck.', to: 'speaker', speaker: 'Achilleas', has_bank: false, entry: null, confidence: 0.93, reasons: [], source: 'override', entry_name: null, entry_label: null, wav: null },
  { guid: 'g3', text: 'Idira line.', to: 'speaker', speaker: 'Idira', has_bank: true, entry: null, confidence: null, reasons: [], source: 'auto', wav: null },
  { guid: 'g4', text: 'You detect hesitation.', to: 'narrator', entry: null, confidence: 1, reasons: [], source: 'auto' },
]

async function make() {
  setActivePinia(createPinia())
  vi.mocked(api.poolRoutes).mockResolvedValue({ total: 120, offset: 0, limit: 50, items: rows as never })
  const pools = usePoolsStore()
  pools.summary = summaryOf([slot('male_human', 'Male human'), slot('female_human', 'Female human')])
  const w = mount(RoutesTable)
  await flushPromises()
  return { w, pools }
}

describe('RoutesTable', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows roster entry, destination wording, confidence and the range', async () => {
    const { w } = await make()
    const tr = w.findAll('[data-route]')
    expect(tr).toHaveLength(4)
    expect(tr[0].text()).toContain('Vox Master')
    expect(tr[0].text()).toContain('Slot · Male human')
    expect(tr[0].text()).toContain('0.62')
    expect(tr[1].text()).toContain('Named · Achilleas')
    expect(tr[1].text()).toContain('override')
    expect(tr[2].text()).toContain('Speaker · Idira (bank)')
    expect(tr[2].text()).toContain('—')
    expect(tr[3].text()).toContain('Narrator')
    expect(w.text()).toContain('1–4 of 120')
  })

  it('plays only lines that have a render', async () => {
    const { w } = await make()
    const plays = w.findAll('[data-route] button.play')
    expect(plays[0].attributes('disabled')).toBeUndefined()
    expect(plays[1].attributes('disabled')).toBeDefined()
  })

  it('moves one line from the override select and resets the select', async () => {
    const { w } = await make()
    vi.mocked(api.poolOverride).mockResolvedValue({ changed: 1 })
    vi.mocked(api.pools).mockResolvedValue(summaryOf([slot('male_human', 'Male human'), slot('female_human', 'Female human')]))
    vi.mocked(api.poolQueue).mockResolvedValue([])
    const sel = w.findAll('[data-move-line]')[0]
    await sel.setValue('slot:female_human')
    expect(api.poolOverride).toHaveBeenCalledWith({ guids: ['g1'], to: 'slot', slot: 'female_human' })
    expect((sel.element as HTMLSelectElement).value).toBe('')
    expect(sel.findAll('option').map((o) => o.text())).toEqual(['—', 'Male human', 'Female human', 'Narrator'])
  })

  it('filters by confidence and shows a removable chip', async () => {
    const { w } = await make()
    const conf = w.findAll('select').find((s) => s.findAll('option').some((o) => o.text() === 'Below 0.8'))!
    await conf.setValue('low')
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls.at(-1)![0]).toMatchObject({ conf_lt: 0.8 })
    expect(w.find('.active-filters').text()).toContain('Below 0.8')
    await w.find('.active-filters .chip').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls.at(-1)![0].conf_lt).toBeUndefined()
  })

  it('pages with Previous / Next 50', async () => {
    const { w } = await make()
    expect(w.find('[data-prev]').attributes('disabled')).toBeDefined()
    await w.find('[data-next]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.poolRoutes).mock.calls.at(-1)![0]).toMatchObject({ offset: 50, limit: 50 })
  })

  it('shows an empty state and an error', async () => {
    const { w } = await make()
    vi.mocked(api.poolRoutes).mockResolvedValue({ total: 0, offset: 0, limit: 50, items: [] })
    await w.find('[data-next]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('No lines match these filters.')
    vi.mocked(api.poolRoutes).mockRejectedValue(new Error('boom'))
    await w.find('[data-prev]').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('boom')
  })

  it('reloads when the pools change (after an accept or merge)', async () => {
    const { w, pools } = await make()
    vi.mocked(api.poolRoutes).mockClear()
    pools.revision += 1
    await flushPromises()
    expect(api.poolRoutes).toHaveBeenCalledTimes(1)
    expect(w.exists()).toBe(true)
  })
})
