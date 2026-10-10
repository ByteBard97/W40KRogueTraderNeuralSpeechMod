import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import { makeCtx, withCtx } from '../../test-utils/speakerCtx'
import OptionsPanel from './OptionsPanel.vue'

describe('OptionsPanel', () => {
  it('is collapsed with a one-line summary of the options', () => {
    const w = mount(OptionsPanel, withCtx(makeCtx()))
    expect(w.text()).toContain('cfg 2 · 10 steps · new seed per line · style prefix off · retry off · normalise off · continuation off')
    expect(w.find('input[data-cfg]').exists()).toBe(false)
  })

  it('edits the shared options object', async () => {
    const ctx = makeCtx()
    const w = mount(OptionsPanel, withCtx(ctx))
    await w.find('.toggle').trigger('click')
    await w.find('input[data-cfg]').setValue('3.5')
    await w.find('input[data-timesteps]').setValue('12')
    await w.findAll('.checks input')[1].setValue(true)
    await w.find('summary').trigger('click')
    await w.find('input[data-continuation]').setValue(true)
    expect(ctx.options.value).toMatchObject({ cfg: 3.5, timesteps: 12, retry_badcase: true, continuation: true })
    expect(w.text()).toMatch(/echo the reference/i)
  })

  it('seed policy: a typed seed only exists under Fixed, and the summary says so', async () => {
    const ctx = makeCtx()
    const w = mount(OptionsPanel, withCtx(ctx))
    await w.find('.toggle').trigger('click')
    expect(w.find('input[data-seed]').exists()).toBe(false)
    const seg = w.findAll('[aria-label="Seed policy"] button')
    expect(seg.map((b) => b.text())).toEqual(['New seed per line', 'One seed for all', 'Fixed…'])
    await seg[1].trigger('click')
    expect(ctx.seedPolicy.value).toBe('one')
    expect(w.text()).toContain('one seed for all')
    await seg[2].trigger('click')
    await w.find('input[data-seed]').setValue('77')
    expect(ctx.options.value.seed).toBe('77')
    expect(w.text()).toContain('fixed seed 77')
  })
})
