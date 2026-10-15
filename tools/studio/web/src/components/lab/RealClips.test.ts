import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'

vi.mock('../../api/client', () => ({ api: { labRealClips: vi.fn() } }))
vi.stubGlobal('Audio', vi.fn(() => ({ addEventListener: vi.fn(), play: vi.fn().mockResolvedValue(undefined), pause: vi.fn() })))
import RealClips from './RealClips.vue'

describe('RealClips', () => {
  beforeEach(() => vi.clearAllMocks())
  it('searches for the word and lists the clips', async () => {
    vi.mocked(api.labRealClips).mockResolvedValue([{ speaker: 'Cassia', wav: 'data/c.wav', seconds: 2.2, text: 'von Valancius.' }])
    const w = mount(RealClips, { props: { word: 'von Valancius' } })
    expect((w.find('[data-real-q]').element as HTMLInputElement).value).toBe('von Valancius')
    await w.find('form').trigger('submit')
    await flushPromises()
    expect(api.labRealClips).toHaveBeenCalledWith('von Valancius', 12)
    expect(w.findAll('[data-real-clip]')).toHaveLength(1)
    expect(w.text()).toContain('Cassia')
  })
  it('follows the word until the user edits the query', async () => {
    const w = mount(RealClips, { props: { word: 'a' } })
    await w.setProps({ word: 'ab' })
    expect((w.find('[data-real-q]').element as HTMLInputElement).value).toBe('ab')
    await w.find('[data-real-q]').setValue('zz')
    await w.setProps({ word: 'abc' })
    expect((w.find('[data-real-q]').element as HTMLInputElement).value).toBe('zz')
  })
})
