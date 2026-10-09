import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import StarRating from './StarRating.vue'

describe('StarRating', () => {
  it('emits the clicked star and clears when the current star is clicked again', async () => {
    const w = mount(StarRating, { props: { modelValue: 2 } })
    const stars = w.findAll('button')
    expect(stars).toHaveLength(5)
    await stars[3].trigger('click')
    expect(w.emitted('update:modelValue')![0]).toEqual([4])
    await stars[1].trigger('click')
    expect(w.emitted('update:modelValue')![1]).toEqual([0])
  })
})
