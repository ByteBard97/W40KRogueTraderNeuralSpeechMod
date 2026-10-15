import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import TransportBar from './TransportBar.vue'

vi.mock('../../api/client', () => ({ api: { labSpeakers: vi.fn(), labLines: vi.fn() } }))

const line = (guid: string, text: string, wav: string) => ({ guid, cue: 'c', order: 0, text, chars: text.length, instruct: null, ref: { wav: 'data/ref.wav' }, current: { wav, seconds: 1, peak_db: -3, crest_db: 10, clip_runs: 0, flag: 'ok' } })
const refSpeakers = [{ speaker: 'Abelard', clips: 40 }]

beforeEach(() => {
  vi.mocked(api.labSpeakers).mockResolvedValue([{ speaker: 'Abelard', slug: 'abelard', lines: 2, chars: 30 }, { speaker: 'Cassia', slug: 'cassia', lines: 1, chars: 9 }])
  vi.mocked(api.labLines).mockResolvedValue({ speaker: 'Abelard', ref: null, lines: [line('g1', 'Hello {n}there{/n}', 'data/a.wav'), line('g2', 'Second', 'data/b.wav')] } as never)
})

async function mounted(props: Record<string, unknown> = {}) {
  const w = mount(TransportBar, { props: { playing: false, refSpeakers, ...props } })
  await flushPromises()
  return w
}

describe('TransportBar', () => {
  it('lists speakers, then lines for the chosen speaker', async () => {
    const w = await mounted()
    expect(w.findAll('[data-test="speaker"] option').map((o) => o.text())).toEqual(['choose', 'Abelard (2)', 'Cassia (1)'])
    await w.get('[data-test="speaker"]').setValue('Abelard')
    await flushPromises()
    expect(api.labLines).toHaveBeenCalledWith('Abelard')
    expect(w.findAll('[data-test="line"] option').map((o) => o.text())).toEqual(['choose', 'Hello there', 'Second'])
    expect(w.emitted('reference')![0]).toEqual(['Abelard'])
  })

  it('emits load-clip with a file url when a line is chosen', async () => {
    const w = await mounted()
    await w.get('[data-test="speaker"]').setValue('Abelard')
    await flushPromises()
    await w.get('[data-test="line"]').setValue('g2')
    expect(w.emitted('load-clip')![0]).toEqual([`/file?p=${encodeURIComponent('data/b.wav')}`])
  })

  it('emits bypass, gap and reference', async () => {
    const w = await mounted()
    await w.get('[data-test="bypass"]').setValue(true)
    await w.get('[data-test="gap"]').setValue('1.5')
    await w.get('[data-test="reference"]').setValue('Abelard')
    expect(w.emitted('bypass')![0]).toEqual([true])
    expect(w.emitted('gap')![0]).toEqual([1.5])
    expect(w.emitted('reference')![0]).toEqual(['Abelard'])
  })

  it('play button label and event follow the playing prop', async () => {
    const w = await mounted()
    expect(w.get('[data-test="play"]').text()).toBe('Play loop')
    await w.get('[data-test="play"]').trigger('click')
    expect(w.emitted('play')).toHaveLength(1)
    await w.setProps({ playing: true })
    expect(w.get('[data-test="play"]').text()).toBe('Stop')
    await w.get('[data-test="play"]').trigger('click')
    expect(w.emitted('stop')).toHaveLength(1)
  })
})
