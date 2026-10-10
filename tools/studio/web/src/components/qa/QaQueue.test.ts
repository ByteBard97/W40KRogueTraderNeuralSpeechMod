import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import QaQueue from './QaQueue.vue'

const clip = (guid: string, over = {}) => ({ guid, speaker: 'Pasqal', text: `line ${guid}`, engine: 'voxcpm2', dur: 87.04, flags: ['slow'], verdict: null, ...over })
const props = (over = {}) => ({ items: [clip('a'), clip('b', { verdict: { verdict: 'good' } })] as never, index: 1, total: 11051, hasNext: true, loading: false, sortLabel: 'suspicious', ...over })

describe('QaQueue', () => {
  it('lists clips with speaker, text, duration, engine and flags, and marks the current one', () => {
    const w = mount(QaQueue, { props: props() })
    const rows = w.findAll('[data-qrow]')
    expect(rows).toHaveLength(2)
    expect(rows[0].text()).toContain('Pasqal · line a')
    expect(rows[0].text()).toContain('87.0 s')
    expect(rows[0].text()).toContain('slow')
    expect(rows[1].attributes('aria-current')).toBe('true')
    expect(rows[0].attributes('aria-current')).toBe('false')
    expect(rows[1].find('[aria-label="Good"]').exists()).toBe(true)
    expect(w.text()).toContain('1–2 of 11,051')
  })

  it('emits select and more, and disables Load more at the end or while loading', async () => {
    const w = mount(QaQueue, { props: props() })
    await w.findAll('[data-qrow]')[0].trigger('click')
    await w.find('[data-more]').trigger('click')
    expect(w.emitted('select')).toEqual([[0]])
    expect(w.emitted('more')).toHaveLength(1)
    expect(w.find('[data-more]').text()).toBe('Load 40 more')
    await w.setProps({ hasNext: false })
    expect(w.find('[data-more]').attributes('disabled')).toBeDefined()
    await w.setProps({ hasNext: true, loading: true })
    expect(w.find('[data-more]').attributes('disabled')).toBeDefined()
  })
})
