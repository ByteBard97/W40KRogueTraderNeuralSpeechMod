import { mount } from '@vue/test-utils'
import { describe, expect, it } from 'vitest'
import FxLibrary from './FxLibrary.vue'
import { fxRenderUrl } from './previewUrl'

const mk = (name: string, family?: string, version?: string) => ({ name, source: 'scenario' as const, dsp: 'c.dsp', notes: '', family, version })
const presets = [mk('Machine: servitor', 'Machine', 'v1'), mk('v2 Machine: x', 'Machine', 'v2'), mk('Clean', 'Space'), mk('Legacy')]

describe('FxLibrary', () => {
  it('groups by family with counts and version tags, defaulting version to v1', () => {
    const w = mount(FxLibrary, { props: { presets } })
    expect(w.findAll('.fam').map((f) => f.text())).toEqual(['Machine 2', 'Space 1', 'Other 1'])
    expect(w.findAll('[data-preset]')[1].text()).toContain('v2')
    expect(w.findAll('[data-preset]')[2].text()).toContain('v1')
  })

  it('filters by search text', async () => {
    const w = mount(FxLibrary, { props: { presets } })
    await w.find('input').setValue('servitor')
    expect(w.findAll('[data-preset]')).toHaveLength(1)
    await w.find('input').setValue('zzz')
    expect(w.text()).toContain('No preset matches')
  })

  it('shows an empty state', () => {
    expect(mount(FxLibrary, { props: { presets: [] } }).text()).toContain('No presets found')
  })

  it('builds the /fx-render URL for a chain', () => {
    expect(fxRenderUrl(['a b', 'c'])).toBe('/fx-render?presets=a+b%7Cc')
    expect(fxRenderUrl(['a'], 'data/x.wav')).toContain('p=data%2Fx.wav')
  })
})
