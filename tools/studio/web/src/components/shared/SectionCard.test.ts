import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import SectionCard from './SectionCard.vue'

describe('SectionCard', () => {
  it('shows content, collapses on header click, and can start collapsed', async () => {
    const w = mount(SectionCard, { props: { title: 'Source' }, slots: { default: '<p class="body">hi</p>' } })
    expect(w.find('.body').exists()).toBe(true)
    await w.find('.head').trigger('click')
    expect(w.find('.body').exists()).toBe(false)
    const c = mount(SectionCard, { props: { title: 'X', collapsedByDefault: true }, slots: { default: '<p class="body">hi</p>' } })
    expect(c.find('.body').exists()).toBe(false)
  })
})
