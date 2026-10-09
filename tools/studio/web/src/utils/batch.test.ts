import { describe, expect, it, vi } from 'vitest'
import type { CloneRequest, Line, ModelOptions, SourceClip, Take } from '../api/types'
import { runBatch } from './batch'

const OPTS: ModelOptions = { cfg: 2, timesteps: 10, seed: '', use_instruct: false, retry_badcase: false, normalize: false, continuation: false }
const line = (guid: string): Line => ({ guid, text: `text ${guid}`, emotion: null, intensity: null, pace: null, instruct: null, baseline: null })
const src = (key: string): SourceClip => ({ key, label: key, wav: `data/${key}.wav`, text: key, origin: 'real' })
const take = (n: number): Take => ({ id: `t${n}` } as Take)

describe('runBatch', () => {
  it('shares one seed per line across sources and calls every combination', async () => {
    const seen: [string, string, string][] = []
    const generate = vi.fn(async (r) => { seen.push([r.guid, r.reference.wav, r.options.seed]); return take(seen.length) })
    const onTake = vi.fn()
    const res = await runBatch({ lines: [line('a'), line('b')], sources: [src('x'), src('y')], options: OPTS, generate, onTake })
    expect(res).toEqual({ done: 4, total: 4, error: null })
    expect(onTake).toHaveBeenCalledTimes(4)
    const seeds = (g: string) => new Set(seen.filter((s) => s[0] === g).map((s) => s[2]))
    expect(seeds('a').size).toBe(1)
    expect(seeds('b').size).toBe(1)
  })

  it('keeps a typed seed for every line', async () => {
    const generate = vi.fn(async (_r: CloneRequest) => take(1))
    await runBatch({ lines: [line('a'), line('b')], sources: [src('x')], options: { ...OPTS, seed: '7' }, generate, onTake: vi.fn() })
    expect(generate.mock.calls.every((c) => c[0].options.seed === '7')).toBe(true)
  })

  it('stops at the first error, reports it, and keeps earlier takes', async () => {
    let n = 0
    const generate = vi.fn(async () => { if (++n === 3) throw new Error('model backend is not running'); return take(n) })
    const onTake = vi.fn()
    const res = await runBatch({ lines: [line('a'), line('b')], sources: [src('x'), src('y')], options: OPTS, generate, onTake })
    expect(res).toEqual({ done: 2, total: 4, error: 'model backend is not running' })
    expect(onTake).toHaveBeenCalledTimes(2)
  })

  it('honours shouldStop between takes', async () => {
    let stop = false
    const generate = vi.fn(async () => { stop = true; return take(1) })
    const res = await runBatch({ lines: [line('a'), line('b')], sources: [src('x')], options: OPTS, generate, onTake: vi.fn(), shouldStop: () => stop })
    expect(res.done).toBe(1)
  })

  it('waits for an async onTake before moving on or reporting done', async () => {
    const log: string[] = []
    const generate = vi.fn(async () => take(1))
    const onTake = vi.fn(async () => { await Promise.resolve(); log.push('onTake finished') })
    await runBatch({ lines: [line('a')], sources: [src('x')], options: OPTS, generate, onTake })
    log.push('batch returned')
    expect(log).toEqual(['onTake finished', 'batch returned'])
  })

  it('does nothing for empty input', async () => {
    expect(await runBatch({ lines: [], sources: [src('x')], options: OPTS, generate: vi.fn(), onTake: vi.fn() })).toEqual({ done: 0, total: 0, error: null })
  })
})
