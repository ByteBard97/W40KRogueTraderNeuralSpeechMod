import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { useLabProbe } from './useLabProbe'

const Host = defineComponent({ setup() { const p = useLabProbe('http://x/'); return () => h('span', { id: 'st' }, p.state.value) } })

describe('useLabProbe', () => {
  afterEach(() => vi.useRealTimers())
  it('reports up when the server answers', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({}))
    const w = mount(Host)
    await flushPromises()
    expect(w.text()).toBe('up')
  })
  it('reports down, then up once the server starts (polling)', async () => {
    vi.useFakeTimers()
    const f = vi.fn().mockRejectedValueOnce(new Error('refused')).mockResolvedValue({})
    vi.stubGlobal('fetch', f)
    const w = mount(Host)
    await flushPromises()
    expect(w.text()).toBe('down')
    await vi.advanceTimersByTimeAsync(5100)
    expect(w.text()).toBe('up')
    w.unmount()
  })
})
