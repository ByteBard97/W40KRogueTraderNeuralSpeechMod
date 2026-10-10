import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import AttentionTiles from './AttentionTiles.vue'

const base = { queueEntries: 61, queueLines: 249, threshold: 0.8, checked: 1, slotTotal: 8, overrides: 0, hasNextSlot: true }

describe('AttentionTiles', () => {
  it('shows the review, spot-check and override numbers', () => {
    const w = mount(AttentionTiles, { props: base })
    expect(w.text()).toContain('61')
    expect(w.text()).toContain('249 lines below 0.8 confidence')
    expect(w.text()).toContain('1 / 8')
  })

  it('emits review and next-slot', async () => {
    const w = mount(AttentionTiles, { props: base })
    await w.find('[data-tile-review] button').trigger('click')
    await w.find('[data-tile-slots] button').trigger('click')
    expect(w.emitted('review')).toHaveLength(1)
    expect(w.emitted('nextSlot')).toHaveLength(1)
  })

  it('is calm when nothing is left', () => {
    const w = mount(AttentionTiles, { props: { ...base, queueEntries: 0, queueLines: 0, checked: 8, hasNextSlot: false } })
    expect(w.find('[data-tile-review]').classes()).not.toContain('hot')
    expect(w.find('[data-tile-review] button').exists()).toBe(false)
    expect(w.find('[data-tile-slots] button').exists()).toBe(false)
  })
})
