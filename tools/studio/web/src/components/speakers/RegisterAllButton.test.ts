import { flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import RegisterAllButton from './RegisterAllButton.vue'

vi.mock('../../api/client', () => ({ api: { speakers: vi.fn(), registerAll: vi.fn() } }))

describe('RegisterAllButton', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.mocked(api.speakers).mockResolvedValue([])
    vi.mocked(api.registerAll).mockReset()
  })

  it('does nothing when the confirm is declined', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const w = mount(RegisterAllButton)
    await w.find('button').trigger('click')
    expect(api.registerAll).not.toHaveBeenCalled()
  })

  it('registers after confirming and summarises registered and skipped speakers', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.registerAll).mockResolvedValue({ registered: ['A', 'B'], skipped: [{ name: 'C', reason: 'no pick' }] })
    const w = mount(RegisterAllButton)
    await w.find('button').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('Registered 2')
    expect(w.text()).toContain('C: no pick')
  })

  it('shows the failure', async () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    vi.mocked(api.registerAll).mockRejectedValue(new Error('disk full'))
    const w = mount(RegisterAllButton)
    await w.find('button').trigger('click')
    await flushPromises()
    expect(w.text()).toContain('disk full')
  })
})
