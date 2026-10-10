import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeCtx, withCtx } from '../../test-utils/speakerCtx'

const api = vi.hoisted(() => ({ fxLibrary: vi.fn() }))
vi.mock('../../api/client', async (orig) => ({ ...(await orig<typeof import('../../api/client')>()), api }))
import FxPanel from './FxPanel.vue'

const lib = [
  { name: 'Clean', source: 'scenario', dsp: '', notes: '', family: 'Clean', version: 'v1' },
  { name: 'v2 Machine: servitor', source: 'scenario', dsp: '', notes: '', family: 'Machine', version: 'v2' },
  { name: 'Cavernous: vast hall', source: 'scenario', dsp: '', notes: '', family: 'Cavernous', version: 'v1' },
]
const pick = async (w: ReturnType<typeof mount>, name: string) => {
  const sel = w.find('select')
  ;(sel.element as HTMLSelectElement).value = name
  await sel.trigger('change')
}

describe('FxPanel', () => {
  beforeEach(() => api.fxLibrary.mockResolvedValue(lib))

  it('adds presets to the chain in order from a grouped select, numbered, and resets the select', async () => {
    const ctx = makeCtx()
    const w = mount(FxPanel, withCtx(ctx))
    await flushPromises()
    expect(w.findAll('optgroup').map((g) => g.attributes('label'))).toEqual(['Cavernous', 'Clean', 'Machine'])
    await pick(w, 'v2 Machine: servitor')
    await pick(w, 'Clean')
    expect(ctx.fxChosen.value).toEqual(['v2 Machine: servitor', 'Clean'])
    expect(w.findAll('.chip').map((c) => c.text())).toEqual(['1v2 Machine: servitorv2', '2Clean'])
    expect((w.find('select').element as HTMLSelectElement).value).toBe('')
    expect(w.text()).toContain('Runs in this order on the raw clone')
  })

  it('removes a preset with its × chip and offers it again', async () => {
    const ctx = makeCtx({ fxChosen: ref(['Clean']) })
    const w = mount(FxPanel, withCtx(ctx))
    await flushPromises()
    expect(w.findAll('option').some((o) => o.text() === 'Clean')).toBe(false)
    await w.find('[data-fx="Clean"]').trigger('click')
    expect(ctx.fxChosen.value).toEqual([])
    expect(w.text()).toContain('No FX · takes stay raw')
  })

  it('falls back to the plain preset names when the library is empty (older server)', async () => {
    api.fxLibrary.mockResolvedValue([])
    const w = mount(FxPanel, withCtx(makeCtx()))
    await flushPromises()
    expect(w.findAll('option').map((o) => o.text())).toContain('Servitor')
  })

  it('says so when there are no presets, and links to the FX page', async () => {
    api.fxLibrary.mockResolvedValue([])
    const w = mount(FxPanel, withCtx(makeCtx({ fxAvailable: ref<string[]>([]) })))
    await flushPromises()
    expect(w.find('select').attributes('disabled')).toBeDefined()
    expect(w.text()).toContain('Open in FX Lab')
  })
})
import { ref } from 'vue'
