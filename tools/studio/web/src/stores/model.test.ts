import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useModelStore } from './model'

vi.mock('../api/client', () => ({ api: { health: vi.fn() } }))

describe('model store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('is ready only in the ready state and explains why not', async () => {
    const m = useModelStore()
    vi.mocked(api.health).mockResolvedValue({ state: 'ready' })
    await m.refresh()
    expect(m.ready).toBe(true)
    vi.mocked(api.health).mockResolvedValue({ state: 'busy' })
    await m.refresh()
    expect(m.ready).toBe(false)
    expect(m.reason).toMatch(/busy/i)
  })

  it('treats a failed health call as down', async () => {
    const m = useModelStore()
    vi.mocked(api.health).mockRejectedValue(new Error('net'))
    await m.refresh()
    expect(m.state).toBe('down')
    expect(m.reason).toMatch(/live_backend/)
  })
})

describe('model store busy elapsed', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })
  it('counts seconds while busy and resets when ready; retry refreshes', async () => {
    const m = useModelStore()
    vi.mocked(api.health).mockResolvedValue({ state: 'busy' })
    await m.retry()
    vi.advanceTimersByTime(3000)
    expect(m.busyElapsed).toBe(3)
    vi.mocked(api.health).mockResolvedValue({ state: 'ready' })
    await m.refresh()
    expect(m.busyElapsed).toBe(0)
    vi.useRealTimers()
  })
})
