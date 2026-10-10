import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'

vi.mock('../api/client', () => ({ api: { qaRuns: vi.fn(), qaFacets: vi.fn(), qaClips: vi.fn(), qaVerdict: vi.fn() } }))
const audio = { src: '', currentTime: 0, duration: 10, volume: 1, loop: false, playbackRate: 1, ended: false, play: vi.fn().mockResolvedValue(undefined), pause: vi.fn(), addEventListener: vi.fn() }
vi.stubGlobal('Audio', vi.fn(() => audio))

import { useGlobalAudio } from '../composables/globalAudio'
import { useShortcutOverlay } from '../composables/useShortcuts'
import { useToasts } from '../composables/useToasts'
import QaView from './QaView.vue'

const clip = (guid: string, verdict: unknown = null) => ({
  guid, wav: `data/${guid}.wav`, text: `line ${guid}`, context: '', speaker: 'Abelard', engine: 'e', voice_source: '', dur: 2, cps: 10, emotion: '', instruct: '',
  ref_path: '', ref: '', real: [], old: null, heard: '', wer: null, flags: [], verdict,
})
const page = (guids: string[], total = guids.length, offset = 0) => ({
  total, offset, limit: 40, items: guids.map((g) => clip(g)), stats: { good: 0, bad: 0, unjudged: total },
})
const press = (key: string) => document.dispatchEvent(new KeyboardEvent('keydown', { key }))
const text = (w: ReturnType<typeof mount>) => w.find('[data-text]').text()

async function mountView(p: unknown = page(['a', 'b', 'c'])) {
  vi.mocked(api.qaRuns).mockResolvedValue([{ id: 'export', label: 'Merged export', clips: 3 }])
  vi.mocked(api.qaFacets).mockResolvedValue({ speakers: ['Abelard'], refs: [], engines: [], flags: [] })
  vi.mocked(api.qaClips).mockResolvedValue(p as never)
  vi.mocked(api.qaVerdict).mockResolvedValue({})
  const w = mount(QaView, { attachTo: document.body })
  await flushPromises()
  return w
}

describe('QaView', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
    localStorage.clear()
    useToasts().clear()
    const g = useGlobalAudio()
    g.stop()
    g.state.id = null
  })

  it('shows the counts, the current clip and the queue', async () => {
    const w = await mountView()
    expect(w.find('[data-stats]').text()).toContain('3 unjudged')
    expect(text(w)).toBe('line a')
    expect(w.findAll('[data-qrow]')).toHaveLength(3)
    expect(w.text()).toContain('clip 1 of 3')
    w.unmount()
  })

  it('moves the cursor with j and k, and by clicking the queue', async () => {
    const w = await mountView()
    press('j')
    press('j')
    await flushPromises()
    expect(text(w)).toBe('line c')
    press('k')
    await flushPromises()
    expect(text(w)).toBe('line b')
    await w.findAll('[data-qrow]')[0].trigger('click')
    expect(text(w)).toBe('line a')
    w.unmount()
  })

  it('g judges the clip good and moves on, with an undo that restores it', async () => {
    const w = await mountView()
    press('g')
    await flushPromises()
    expect(api.qaVerdict).toHaveBeenCalledWith({ run: 'export', guid: 'a', verdict: 'good', tags: [], note: '' })
    expect(text(w)).toBe('line b')
    expect(w.find('[data-stats]').text()).toContain('1 good')
    expect(w.find('[data-session]').text()).toContain('1 judged')
    const toast = useToasts().toasts.value.at(-1)!
    expect(toast.message).toBe('Marked good')
    toast.action!.run()
    await flushPromises()
    expect(vi.mocked(api.qaVerdict).mock.calls.at(-1)![0]).toMatchObject({ guid: 'a', verdict: null })
    expect(text(w)).toBe('line a')
    expect(w.find('[data-stats]').text()).toContain('3 unjudged')
    w.unmount()
  })

  it('u clears the verdict, and the Good button clears when pressed again', async () => {
    const w = await mountView()
    press('g')
    press('k')
    press('u')
    await flushPromises()
    expect(vi.mocked(api.qaVerdict).mock.calls.at(-1)![0]).toMatchObject({ guid: 'a', verdict: null })
    await w.findAll('.judge .j')[1].trigger('click')
    await flushPromises()
    expect(vi.mocked(api.qaVerdict).mock.calls.at(-1)![0]).toMatchObject({ guid: 'a', verdict: 'bad' })
    w.unmount()
  })

  it('number keys toggle tags, which also marks the clip bad', async () => {
    const w = await mountView()
    press('2')
    await flushPromises()
    expect(api.qaVerdict).toHaveBeenLastCalledWith({ run: 'export', guid: 'a', verdict: 'bad', tags: ['garbled'], note: '' })
    press('2')
    press('0')
    await flushPromises()
    expect(vi.mocked(api.qaVerdict).mock.calls.at(-1)![0]).toMatchObject({ tags: ['bad pause'] })
    w.unmount()
  })

  it('space plays the chosen source, through the compressor after x', async () => {
    const w = await mountView()
    press(' ')
    expect(audio.src).toBe('/file?p=data%2Fa.wav')
    press('x')
    await flushPromises()
    press(' ')
    expect(audio.src).toBe('/fx-file?p=data%2Fa.wav&fx=mild')
    expect(localStorage.getItem('studio.qa.fx')).toBe('mild')
    w.unmount()
  })

  it('remembers the compressor choice', async () => {
    const w = await mountView()
    await w.findAll('.seg button')[2].trigger('click')
    expect(localStorage.getItem('studio.qa.fx')).toBe('strong')
    w.unmount()
    const again = await mountView()
    expect(again.findAll('.seg button')[2].attributes('aria-pressed')).toBe('true')
    again.unmount()
  })

  it('n jumps to the next unjudged clip, loading more of the queue when the loaded ones are judged', async () => {
    const p = page(['a', 'b'], 3)
    p.items[1].verdict = { verdict: 'good', tags: [], note: '' } as never
    const w = await mountView(p)
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page(['c'], 3, 2), offset: 2 } as never)
    press('n')
    await flushPromises()
    expect(vi.mocked(api.qaClips).mock.calls.at(-1)![1]).toMatchObject({ offset: 2 })
    expect(text(w)).toBe('line c')
    w.unmount()
  })

  it('loads more under the queue and appends', async () => {
    const w = await mountView(page(['a'], 3))
    vi.mocked(api.qaClips).mockResolvedValueOnce({ ...page(['b', 'c'], 3, 1), offset: 1 } as never)
    await w.find('[data-more]').trigger('click')
    await flushPromises()
    expect(w.findAll('[data-qrow]')).toHaveLength(3)
    expect(w.find('[data-more]').attributes('disabled')).toBeDefined()
    w.unmount()
  })

  it('reloads from the first page when a filter changes, and shows the chip', async () => {
    const w = await mountView()
    await w.find('[data-flag] select').setValue('any flag')
    await flushPromises()
    expect(vi.mocked(api.qaClips).mock.calls.at(-1)![1]).toMatchObject({ flag: 'any flag', offset: 0 })
    expect(w.find('.active-filters').text()).toContain('Flag: any flag')
    w.unmount()
  })

  it('shows an empty state, and errors', async () => {
    const w = await mountView(page([], 0))
    expect(w.text()).toMatch(/no clips for these filters/i)
    w.unmount()
    vi.mocked(api.qaClips).mockRejectedValue(new Error('boom'))
    const w2 = mount(QaView, { attachTo: document.body })
    await flushPromises()
    expect(w2.find('[data-error]').text()).toContain('boom')
    w2.unmount()
  })

  it('shows the per-reference tally', async () => {
    const p = page(['a'])
    ;(p.stats as Record<string, unknown>).by_ref = { abelard: { good: 2, bad: 1, total: 5 } }
    const w = await mountView(p)
    expect(w.find('[data-ref-tally]').text()).toBe('abelard: 2g/1b/5')
    w.unmount()
  })

  it('feeds the bar prev and next buttons and registers its shortcuts, then lets go on unmount', async () => {
    const w = await mountView()
    const g = useGlobalAudio()
    g.state.transport.next!()
    await flushPromises()
    expect(text(w)).toBe('line b')
    expect(useShortcutOverlay().page.value?.title).toBe('Render QA')
    w.unmount()
    expect(g.state.transport.next).toBeUndefined()
    expect(useShortcutOverlay().page.value).toBeNull()
  })
})
