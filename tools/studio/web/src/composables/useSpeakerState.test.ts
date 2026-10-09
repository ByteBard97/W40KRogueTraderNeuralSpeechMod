import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api } from '../api/client'
import { useSpeakerState } from './useSpeakerState'

vi.mock('../api/client', () => ({
  api: { speaker: vi.fn(), lines: vi.fn(), takes: vi.fn(), fxPresets: vi.fn(), saveProfile: vi.fn(), setActive: vi.fn(), register: vi.fn() },
}))

const opts = { cfg: 2, timesteps: 10, seed: '', use_instruct: false, retry_badcase: false, normalize: false, continuation: false }
const realDetail = {
  summary: { slug: 'pasqal', name: 'Pasqal', origin: 'real', line_count: 2, status: 'source' },
  clips: [{ id: 'E1', wav: 'data/v/E1.wav', duration: 5, text: 'Hello.', curated_rank: 1, noise_db: -60 }],
  design: null, profile: null,
}
const designDetail = {
  summary: { slug: 'muaran', name: 'Muaran', origin: 'designed', line_count: 1, status: 'source' },
  clips: [],
  design: { description: 'd', text: 'Sample.', order: ['c1.wav'], pick: 'c1.wav',
    candidates: [{ id: 'c1.wav', file: 'data/vd/c1.wav', scores: null, verdict: {}, gen: null }, { id: 'c0.wav', file: 'data/vd/c0.wav', scores: null, verdict: {}, gen: null }] },
  profile: null,
}

function setup(detail: unknown) {
  vi.mocked(api.speaker).mockResolvedValue(detail as never)
  vi.mocked(api.lines).mockResolvedValue([{ guid: 'g1' }] as never)
  vi.mocked(api.takes).mockResolvedValue([])
  vi.mocked(api.fxPresets).mockResolvedValue(['Clean'])
}

describe('useSpeakerState', () => {
  beforeEach(() => vi.clearAllMocks())

  it('builds sources from real clips and defaults to the first', async () => {
    setup(realDetail)
    const s = useSpeakerState('pasqal')
    await s.load()
    expect(s.sources.value.map((x) => x.key)).toEqual(['real:E1'])
    expect(s.chosenSources.value.map((x) => x.key)).toEqual(['real:E1'])
    expect(s.lines.value).toHaveLength(1)
    expect(s.fxAvailable.value).toEqual(['Clean'])
  })

  it('uses design candidates as sources with the design sample text, ranked order first', async () => {
    setup(designDetail)
    const s = useSpeakerState('muaran')
    await s.load()
    expect(s.sources.value.map((x) => [x.key, x.text])).toEqual([['cand:c1.wav', 'Sample.'], ['cand:c0.wav', 'Sample.']])
    expect(s.chosenSources.value.map((x) => x.key)).toEqual(['cand:c1.wav'])    // the pick is preselected
  })

  it('has no sources and no selection for an empty speaker', async () => {
    setup({ ...realDetail, clips: [] })
    const s = useSpeakerState('pasqal')
    await s.load()
    expect(s.sources.value).toEqual([])
    expect(s.chosenSources.value).toEqual([])
  })

  it('applies a saved profile to options, fx, lines and the chosen source', async () => {
    setup({ ...realDetail, profile: { source: { wav: 'data/v/E1.wav', text: 'Hello.', origin: 'real' }, options: { ...opts, cfg: 3.5 }, fx: ['Clean'], test_lines: ['g1'] } })
    const s = useSpeakerState('pasqal')
    await s.load()
    expect(s.options.value.cfg).toBe(3.5)
    expect(s.fxChosen.value).toEqual(['Clean'])
    expect([...s.selectedLines.value]).toEqual(['g1'])
    expect(s.chosenSources.value.map((x) => x.wav)).toEqual(['data/v/E1.wav'])
  })

  it('supplied clips are added as selectable sources, deduplicated', async () => {
    setup({ ...realDetail, clips: [] })
    const s = useSpeakerState('pasqal')
    await s.load()
    s.addSupplied('data/x/clean.wav', 'text')
    s.addSupplied('data/x/clean.wav', 'text')
    expect(s.sources.value.map((x) => x.key)).toEqual(['sup:data/x/clean.wav'])
  })

  it('saveProfile uses the first chosen source and reports success; refuses with none chosen', async () => {
    setup(realDetail)
    vi.mocked(api.saveProfile).mockResolvedValue({} as never)
    const s = useSpeakerState('pasqal')
    await s.load()
    await s.saveProfile()
    expect(vi.mocked(api.saveProfile).mock.calls[0][1]).toMatchObject({ source: { wav: 'data/v/E1.wav', origin: 'real' } })
    expect(s.notice.value).toMatch(/saved/i)
    s.selectedSources.value = new Set()
    await s.saveProfile()
    expect(s.notice.value).toMatch(/choose a source/i)
  })

  it('upsertTake puts new takes first and replaces existing ones', async () => {
    setup(realDetail)
    const s = useSpeakerState('pasqal')
    await s.load()
    s.upsertTake({ id: 't1', rating: 0 } as never)
    s.upsertTake({ id: 't2', rating: 0 } as never)
    s.upsertTake({ id: 't1', rating: 5 } as never)
    expect(s.takes.value.map((t) => [t.id, t.rating])).toEqual([['t2', 0], ['t1', 5]])
  })

  it('registerPick calls the api, reloads, and reports errors in the notice', async () => {
    setup(designDetail)
    vi.mocked(api.register).mockResolvedValue({ registered: ['Muaran'] })
    const s = useSpeakerState('muaran')
    await s.load()
    await s.registerPick()
    expect(api.register).toHaveBeenCalledWith('muaran')
    expect(s.notice.value).toContain('Registered Muaran')
    expect(api.speaker).toHaveBeenCalledTimes(2)
    vi.mocked(api.register).mockRejectedValue(new Error("'Muaran' has no pick yet"))
    await s.registerPick()
    expect(s.notice.value).toContain('no pick yet')
  })

  it('records load errors', async () => {
    vi.mocked(api.speaker).mockRejectedValue(new Error('no speaker'))
    const s = useSpeakerState('x')
    await s.load()
    expect(s.error.value).toBe('no speaker')
  })
})
