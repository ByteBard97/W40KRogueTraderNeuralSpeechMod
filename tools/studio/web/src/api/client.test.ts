import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiRequestError, api } from './client'

function mockFetch(status: number, body: unknown) {
  const f = vi.fn().mockResolvedValue({ ok: status < 400, status, json: async () => body })
  vi.stubGlobal('fetch', f)
  return f
}

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('GETs JSON', async () => {
    const f = mockFetch(200, [{ slug: 'pasqal' }])
    expect(await api.speakers()).toEqual([{ slug: 'pasqal' }])
    expect(f).toHaveBeenCalledWith('/api/speakers', undefined)
  })

  it('POSTs JSON bodies', async () => {
    const f = mockFetch(200, { cand: 'c2.wav' })
    await api.designKeep('muaran', { file: 'live_tmp/t.wav', seed: 1, cfg: 2, timesteps: 10 })
    const [url, init] = f.mock.calls[0]
    expect(url).toBe('/api/speakers/muaran/design/keep')
    expect(init.method).toBe('POST')
    expect(JSON.parse(init.body)).toMatchObject({ seed: 1 })
  })

  it('throws ApiRequestError with the server message', async () => {
    mockFetch(503, { error: 'model backend is not running' })
    await expect(api.designGenerate('muaran', {})).rejects.toMatchObject({
      status: 503,
      message: 'model backend is not running',
    })
    await expect(api.designGenerate('muaran', {})).rejects.toBeInstanceOf(ApiRequestError)
  })
  it('calls the pool endpoints', async () => {
    const f = mockFetch(200, {})
    await api.pools()
    await api.poolRoutes({ to: 'slot', slot: 'male_human', limit: 50 })
    await api.poolOverride({ entry: 'C|a', to: 'slot', slot: 'male_human' })
    expect(f.mock.calls[0][0]).toBe('/api/pools')
    expect(f.mock.calls[1][0]).toBe('/api/pools/routes?to=slot&slot=male_human&limit=50')
    expect(f.mock.calls[2][0]).toBe('/api/pools/routes')
    expect(JSON.parse(f.mock.calls[2][1].body)).toMatchObject({ entry: 'C|a' })
  })
})
