import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { qaRuns: vi.fn(), qaFacets: vi.fn(), qaClips: vi.fn(), qaVerdict: vi.fn() } }))
const play = vi.fn()
vi.mock('../composables/useAudioPlayer', () => ({ useAudioPlayer: () => ({ play, playing: null }) }))

import QaView from './QaView.vue'

const clip = (guid: string, verdict: unknown = null) => ({
  guid, wav: `data/${guid}.wav`, text: `line ${guid}`, context: '', speaker: 'Abelard', engine: 'e', voice_source: '', dur: 2, cps: 10, emotion: '', instruct: '',
  ref_path: '', ref: '', real: [], old: null, heard: '', wer: null, flags: [], verdict,
})
const page = (guids: string[], total = guids.length, offset = 0) => ({
  total, offset, limit: 40, items: guids.map((g) => clip(g)), stats: { good: 0, bad: 0, unjudged: total },
})
const press = (key: string) => document.dispatchEvent(new KeyboardEvent('keydown', { key }))

async function mountView(p = page(['a', 'b', 'c'])) {
  vi.mocked(api.qaRuns).mockResolvedValue([{ id: 'export', label: 'Merged export', clips: 3 }])
  vi.mocked(api.qaFacets).mockResolvedValue({ speakers: ['Abelard'], refs: [], engines: [], flags: [] })
  vi.mocked(api.qaClips).mockResolvedValue(p as never)
  vi.mocked(api.qaVerdict).mockResolvedValue({})
  const w = mount(QaView, { attachTo: document.body })
  await flushPromises()
  return w
}

describe('QaView', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.clearAllMocks() })

  it('shows the stats line and the clips', async () => {
    const w = await mountView()
    expect(w.find('[data-stats]').text()).toContain('3 unjudged')
    expect(w.find('[data-stats]').text()).toContain('showing 1-3 of 3')
    expect(w.findAll('.row')).toHaveLength(3)
    w.unmount()
  })

  it('moves the selection with j and k', async () => {
    const w = await mountView()
    press('j')
    press('j')
    await flushPromises()
    expect(w.findAll('.row')[2].classes()).toContain('selected')
    press('k')
    await flushPromises()
    expect(w.findAll('.row')[1].classes()).toContain('selected')
    w.unmount()
  })

  it('g judges the selected clip good and moves on', async () => {
    const w = await mountView()
    press('g')
    await flushPromises()
    expect(api.qaVerdict).toHaveBeenCalledWith({ run: 'export', guid: 'a', verdict: 'good', tags: [], note: '' })
    expect(w.findAll('.row')[1].classes()).toContain('selected')
    expect(w.find('[data-stats]').text()).toContain('1 good')
    w.unmount()
  })

  it('u clears the verdict', async () => {
    const w = await mountView()
    press('g')
    press('k')
    press('u')
    await flushPromises()
    expect(vi.mocked(api.qaVerdict).mock.calls.at(-1)![0]).toMatchObject({ guid: 'a', verdict: null })
    w.unmount()
  })

  it('space plays the selected clip, through the compressor after x', async () => {
    const w = await mountView()
    press(' ')
    expect(play).toHaveBeenLastCalledWith('data/a.wav')
    press('x')
    await flushPromises()
    press(' ')
    expect(play).toHaveBeenLastCalledWith('/fx-file?p=data%2Fa.wav&fx=mild', '/fx-file?p=data%2Fa.wav&fx=mild')
    w.unmount()
  })

  it('n jumps to the next unjudged clip', async () => {
    const p = page(['a', 'b', 'c'])
    p.items[1].verdict = { verdict: 'good', tags: [], note: '' } as never
    const w = await mountView(p)
    press('n')
    await flushPromises()
    expect(w.findAll('.row')[2].classes()).toContain('selected')
    w.unmount()
  })

  it('pages forward and back', async () => {
    const w = await mountView(page(['a'], 100))
    expect(w.find('[data-prev]').attributes('disabled')).toBeDefined()
    await w.find('[data-next]').trigger('click')
    await flushPromises()
    expect(vi.mocked(api.qaClips).mock.calls.at(-1)![1]).toMatchObject({ offset: 40, limit: 40 })
    w.unmount()
  })

  it('reloads from the first page when a filter changes', async () => {
    const w = await mountView()
    await w.find('[data-flag]').setValue('any flag')
    await flushPromises()
    expect(vi.mocked(api.qaClips).mock.calls.at(-1)![1]).toMatchObject({ flag: 'any flag', offset: 0 })
    w.unmount()
  })

  it('shows an empty state and errors', async () => {
    const w = await mountView(page([], 0))
    expect(w.text()).toMatch(/no clips for these filters/i)
    w.unmount()
    vi.mocked(api.qaClips).mockRejectedValue(new Error('boom'))
    const w2 = mount(QaView, { attachTo: document.body })
    await flushPromises()
    expect(w2.text()).toContain('boom')
    w2.unmount()
  })

  it('shows the per-reference tally in the stats line', async () => {
    const p = page(['a'])
    ;(p.stats as Record<string, unknown>).by_ref = { abelard: { good: 2, bad: 1, total: 5 } }
    const w = await mountView(p)
    expect(w.find('[data-ref-tally]').text()).toBe('abelard: 2g/1b/5')
    w.unmount()
  })

  it('remembers the compressor choice in localStorage', async () => {
    localStorage.clear()
    const w = await mountView()
    await w.find('[data-fx]').setValue('strong')
    expect(localStorage.getItem('studio.qa.fx')).toBe('strong')
    w.unmount()
    const again = await mountView()
    expect((again.find('[data-fx]').element as HTMLSelectElement).value).toBe('strong')
    again.unmount()
    localStorage.clear()
  })

  it('disables paging while a page is loading', async () => {
    const w = await mountView(page(['a'], 90))
    let done!: (v: never) => void
    vi.mocked(api.qaClips).mockImplementationOnce(() => new Promise<never>((r) => { done = r }))
    await w.find('[data-next]').trigger('click')
    expect(w.find('[data-next]').attributes('disabled')).toBeDefined()
    done(page(['b'], 90, 40) as never)
    await flushPromises()
    w.unmount()
  })
})
