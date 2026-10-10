import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../../api/client'
import { useModelStore } from '../../stores/model'
import ModelPill from '../ui/ModelPill.vue'

vi.mock('../../api/client', () => ({ api: { health: vi.fn().mockResolvedValue({ state: 'ready' }) } }))

describe('ModelPill', () => {
  beforeEach(() => setActivePinia(createPinia()))
  it('shows ready, busy with elapsed, and down with reason and Retry', async () => {
    const m = useModelStore()
    const w = mount(ModelPill)
    m.state = 'ready'
    await w.vm.$nextTick()
    expect(w.text()).toContain('Model ready')
    m.state = 'busy'
    m.busyElapsed = 7
    await w.vm.$nextTick()
    expect(w.text()).toContain('Model busy')
    expect(w.text()).toContain('0:07')
    m.state = 'down'
    await w.vm.$nextTick()
    expect(w.text()).toContain('Model down')
    expect(w.text()).toMatch(/live_backend/)
    vi.mocked(api.health).mockClear()
    await w.find('button').trigger('click')
    expect(api.health).toHaveBeenCalled()
    w.unmount()
  })
})
