import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import MatchFilters from './MatchFilters.vue'

describe('MatchFilters', () => {
  it('emits the whole filter whenever one control changes', async () => {
    const w = mount(MatchFilters)
    await w.find('[data-group]').setValue('flagged')
    await w.find('[data-speaker]').setValue('hein')
    await w.find('[data-speaker]').trigger('change')
    const last = w.emitted('change')!.at(-1)![0]
    expect(last).toEqual({ group: 'flagged', speaker: 'hein', state: '', q: '' })
  })
})
