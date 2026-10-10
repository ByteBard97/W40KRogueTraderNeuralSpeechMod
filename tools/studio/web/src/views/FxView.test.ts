import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createMemoryHistory, createRouter } from 'vue-router'
import { api } from '../api/client'
import { useToasts } from '../composables/useToasts'

vi.mock('../composables/useFxBridge', () => ({
  FX_LAB_PORT: 8908,
  fxLabUrl: () => 'http://127.0.0.1:8908/',
  useFxBridge: () => ({ sendClip: vi.fn() }),
}))
vi.mock('../api/client', () => ({
  api: { fxLibrary: vi.fn(), fxLabels: vi.fn(), fxSaveLabels: vi.fn(), fxPreview: vi.fn(), fxWrite: vi.fn(), fxUsage: vi.fn(), fxDiff: vi.fn(), fxBackups: vi.fn(), fxRestore: vi.fn() },
}))

import FxView from './FxView.vue'

async function mountAt(url: string) {
  const router = createRouter({ history: createMemoryHistory(), routes: [{ path: '/fx', component: FxView }] })
  router.push(url)
  await router.isReady()
  const w = mount(FxView, { global: { plugins: [router] }, attachTo: document.body })
  await flushPromises()
  return w
}

describe('FxView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    useToasts().clear()
    vi.mocked(api.fxLibrary).mockResolvedValue([{ name: 'Clean', source: 'scenario', dsp: 'c', notes: '', family: 'Space', version: 'v1' }, { name: 'Mine', source: 'saved', dsp: 'c', notes: '' }])
    vi.mocked(api.fxLabels).mockResolvedValue({ machine: ['Clean'], helmet: [] })
    vi.mocked(api.fxUsage).mockRejectedValue(new Error('404'))
    vi.mocked(api.fxBackups).mockResolvedValue([])
    vi.mocked(api.fxPreview).mockResolvedValue({ lines: 1, speakers: 0, unmapped_labels: {}, sample: [] })
    vi.mocked(api.fxDiff).mockResolvedValue({ rows: [], changed: 0, unmapped_labels: {}, file_mtime: null })
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new Error('refused')))
  })

  it('shows the library, the real labels, and the lab offline state', async () => {
    const w = await mountAt('/fx')
    expect(w.text()).toContain('2 presets · 2 labels')
    expect(w.findAll('[data-preset]')).toHaveLength(2)
    expect(w.findAll('[data-label]').map((r) => r.attributes('data-label'))).toEqual(['machine', 'helmet'])
    expect(w.text()).toContain('Map matches the file on disk')
    expect(w.text()).toContain('The FX Lab runs as its own server')
    expect(w.find('[data-write]').attributes('disabled')).toBeDefined()
  })

  it('an edit flags the map, enables Write, and Discard puts it back', async () => {
    const w = await mountAt('/fx')
    await w.find('[data-label="helmet"] [data-add]').setValue('Mine')
    expect(w.text()).toContain('1 unsaved change')
    expect(w.find('[data-write]').attributes('disabled')).toBeUndefined()
    await w.find('[data-discard]').trigger('click')
    expect(w.text()).toContain('Map matches the file on disk')
  })

  it('Ctrl+S asks, Write saves labels then assignments, and the toast offers undo through the backup', async () => {
    vi.mocked(api.fxSaveLabels).mockResolvedValue({ machine: ['Clean'], helmet: ['Mine'] })
    vi.mocked(api.fxWrite).mockResolvedValue({ path: 'data/fx_lab/assignments.json', lines: 4, speakers: 1, backup: 'assignments.t.bak.json' })
    vi.mocked(api.fxRestore).mockResolvedValue({ restored: 'assignments.t.bak.json', kind: 'assignments', path: 'p', backup: null })
    const w = await mountAt('/fx')
    await w.find('[data-label="helmet"] [data-add]').setValue('Mine')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 's', ctrlKey: true }))
    await flushPromises()
    expect(w.find('.inline-confirm').text()).toContain('timestamped')
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter' }))
    await flushPromises()
    await flushPromises()
    expect(api.fxSaveLabels).toHaveBeenCalledWith({ machine: ['Clean'], helmet: ['Mine'] })
    expect(api.fxWrite).toHaveBeenCalled()
    const t = useToasts().toasts.value[0]
    expect(t.message).toContain('assignments.t.bak.json')
    t.action!.run()
    await flushPromises()
    expect(api.fxRestore).toHaveBeenCalledWith('assignments.t.bak.json')
    w.unmount()
  })

  it('Escape cancels the confirm without writing', async () => {
    const w = await mountAt('/fx')
    await w.find('[data-label="helmet"] [data-add]').setValue('Mine')
    await w.find('[data-write]').trigger('click')
    expect(w.find('.inline-confirm').exists()).toBe(true)
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape' }))
    await flushPromises()
    expect(w.find('.inline-confirm').exists()).toBe(false)
    expect(api.fxWrite).not.toHaveBeenCalled()
    w.unmount()
  })

  it('shows a server error from loading', async () => {
    vi.mocked(api.fxLibrary).mockRejectedValue(new Error('boom'))
    const w = await mountAt('/fx')
    expect(w.text()).toContain('boom')
  })
})
