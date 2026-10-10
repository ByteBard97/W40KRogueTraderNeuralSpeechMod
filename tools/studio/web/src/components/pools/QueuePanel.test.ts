import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { entryOf, slot, summaryOf } from '../../test-utils/poolFixtures'
import { usePoolsStore } from '../../stores/pools'

vi.mock('../../api/client', () => ({ api: { pools: vi.fn(), poolQueue: vi.fn(), poolOverride: vi.fn(), poolCreateSlot: vi.fn() } }))
import QueuePanel from './QueuePanel.vue'

const slots = [slot('male_human', 'Male human'), slot('female_human', 'Female human')]
async function mountWith(entries = [entryOf('a'), entryOf('b', { entry: null })]) {
  setActivePinia(createPinia())
  vi.mocked(api.pools).mockResolvedValue(summaryOf(slots))
  vi.mocked(api.poolQueue).mockResolvedValue(entries)
  vi.mocked(api.poolOverride).mockResolvedValue({ changed: 3 })
  const pools = usePoolsStore()
  await pools.load()
  return { w: mount(QueuePanel), pools }
}

describe('QueuePanel', () => {
  beforeEach(() => vi.clearAllMocks())

  it('shows name, lines, flags, guess, playable samples and evidence', async () => {
    const { w } = await mountWith()
    const card = w.findAll('article')[0]
    expect(card.text()).toContain('Name a')
    expect(card.text()).toContain('3 lines')
    expect(card.text()).toContain('gender low confidence')
    expect(card.text()).toContain('guess: male · human · unknown role')
    expect(card.text()).toContain('First line.')
    expect(card.find('button.play').attributes('disabled')).toBeUndefined()
    expect(card.text()).toContain('Evidence (1)')
    expect(w.text()).toContain('1 of 2')
  })

  it('disables play when the line has no render, and falls back to plain sample strings', async () => {
    const old = entryOf('a', { sample_items: undefined, samples: ['Old style.'] })
    const { w } = await mountWith([old])
    expect(w.text()).toContain('Old style.')
    expect(w.find('button.play').attributes('disabled')).toBeDefined()
  })

  it('Accept sends the entry', async () => {
    const { w } = await mountWith()
    await w.find('[data-accept]').trigger('click')
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a' })
  })

  it('Move sends the chosen slot', async () => {
    const { w } = await mountWith()
    await w.find('select').setValue('slot:female_human')
    await w.find('[data-move]').trigger('click')
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a', to: 'slot', slot: 'female_human' })
  })

  it('offers a game voice and Narrator as targets', async () => {
    const { w } = await mountWith([entryOf('a', { to: 'speaker', slot: null, speaker: 'Idira' })])
    const labels = w.findAll('option').map((o) => o.text())
    expect(labels).toEqual(['Male human', 'Female human', 'Idira (game voice)', 'Narrator', 'New designed voice…'])
  })

  it('"New designed voice" opens the form, then creates the slot and moves the entry', async () => {
    const { w } = await mountWith()
    vi.mocked(api.poolCreateSlot).mockResolvedValue(slot('custom_boss', 'Boss', { custom: true }))
    await w.find('select').setValue('__new__')
    const form = w.find('form')
    expect(form.exists()).toBe(true)
    await form.find('[data-nv-name]').setValue('Boss')
    await form.trigger('submit')
    await flushPromises()
    expect(api.poolCreateSlot).toHaveBeenCalledWith({ name: 'Boss', gender: 'male', species: 'human' })
    expect(api.poolOverride).toHaveBeenCalledWith({ entry: 'C|a', to: 'slot', slot: 'custom_boss' })
  })

  it('the new voice form sends a description when one is typed', async () => {
    const { w } = await mountWith()
    vi.mocked(api.poolCreateSlot).mockResolvedValue(slot('custom_vox', 'Vox', { custom: true }))
    await w.find('select').setValue('__new__')
    const form = w.find('form')
    await form.find('[data-nv-name]').setValue('Vox')
    await form.find('[data-nv-description]').setValue('Female cyborg, modulated vox-caster voice')
    await form.trigger('submit')
    await flushPromises()
    expect(api.poolCreateSlot).toHaveBeenCalledWith({ name: 'Vox', gender: 'male', species: 'human', description: 'Female cyborg, modulated vox-caster voice' })
  })

  it('cannot accept or move a group without a roster entry', async () => {
    const { w } = await mountWith([entryOf('b', { entry: null })])
    expect(w.find('[data-accept]').attributes('disabled')).toBeDefined()
    expect(w.find('[data-move]').attributes('disabled')).toBeDefined()
  })

  it('Skip sends the entry to the end', async () => {
    const { w, pools } = await mountWith()
    await w.findAll('[data-skip]')[0].trigger('click')
    expect(pools.ordered.map((e) => e.key)).toEqual(['b', 'a'])
  })

  it('shows an empty state when nothing needs review', async () => {
    const { w } = await mountWith([])
    expect(w.text()).toMatch(/nothing needs review/i)
  })

  it('pages long queues', async () => {
    const many = Array.from({ length: 8 }, (_, i) => entryOf(`e${i}`))
    const { w } = await mountWith(many)
    expect(w.findAll('article')).toHaveLength(5)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('article')).toHaveLength(8)
  })

  it('marks only the current card with key hints', async () => {
    const { w } = await mountWith()
    expect(w.findAll('article')[0].find('.hint').exists()).toBe(true)
    expect(w.findAll('article')[1].find('.hint').exists()).toBe(false)
  })
})
