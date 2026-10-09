import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QueuePanel from './QueuePanel.vue'

const entries = [{ key: 'C|q', entry: 'C|q', conversation: 'C', label: 'Q', name: null, attr: { gender: 'unknown', species: 'human', age: 'unknown' },
  reasons: ['gender unknown'], lines: 4, samples: ['Hello there.'], to: 'slot', slot: 'male_human', speaker: null, evidence: ['said something'] }]
const slots = [{ id: 'male_human', name: 'Male human' }, { id: 'female_human', name: 'Female human' }]

describe('QueuePanel', () => {
  it('shows the entry, why it is queued, its lines and a sample', () => {
    const t = mount(QueuePanel, { props: { entries: entries as never, slots: slots as never } }).text()
    expect(t).toContain('gender unknown')
    expect(t).toContain('4 lines')
    expect(t).toContain('Hello there.')
  })

  it('accepts an entry', async () => {
    const w = mount(QueuePanel, { props: { entries: entries as never, slots: slots as never } })
    await w.find('[data-accept]').trigger('click')
    expect(w.emitted('accept')![0]).toEqual(['C|q'])
  })

  it('moves an entry to another slot or the narrator', async () => {
    const w = mount(QueuePanel, { props: { entries: entries as never, slots: slots as never } })
    await w.find('select').setValue('slot:female_human')
    await w.find('[data-move]').trigger('click')
    expect(w.emitted('move')![0]).toEqual(['C|q', { to: 'slot', slot: 'female_human' }])
    await w.find('select').setValue('narrator')
    await w.find('[data-move]').trigger('click')
    expect(w.emitted('move')![1]).toEqual(['C|q', { to: 'narrator' }])
  })

  it('shows an empty state when nothing needs review', () => {
    expect(mount(QueuePanel, { props: { entries: [], slots: [] } }).text()).toMatch(/nothing needs review/i)
  })

  it('shows a first page of entries and reveals the rest on request', async () => {
    const many = Array.from({ length: 40 }, (_, i) => ({ ...entries[0], key: `C|e${i}`, entry: `C|e${i}` }))
    const w = mount(QueuePanel, { props: { entries: many as never, slots: slots as never } })
    expect(w.findAll('.entry')).toHaveLength(15)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.entry')).toHaveLength(30)
    await w.find('[data-more]').trigger('click')
    expect(w.findAll('.entry')).toHaveLength(40)
    expect(w.find('[data-more]').exists()).toBe(false)
  })

  it('shows and moves a speaker-routed entry as that speaker, not the narrator', async () => {
    const e = [{ ...entries[0], to: 'speaker', slot: null, speaker: 'Abelard' }]
    const w = mount(QueuePanel, { props: { entries: e as never, slots: slots as never } })
    expect((w.find('select').element as HTMLSelectElement).value).toBe('speaker:Abelard')
    await w.find('[data-move]').trigger('click')
    expect(w.emitted('move')![0]).toEqual(['C|q', { to: 'speaker', speaker: 'Abelard' }])
  })
})
