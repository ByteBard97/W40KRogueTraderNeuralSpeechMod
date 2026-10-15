import { describe, expect, it, vi } from 'vitest'
import type { LabJob, LabJobState } from '../api/labTypes'
import { isTerminal, JOB_POLL_MS, pollJob } from './labJob'

const job = (state: LabJobState, done = 0): LabJob => ({ id: 'j1', state, total: 3, done, take_ids: [], error: null })
const noSleep = vi.fn().mockResolvedValue(undefined)

describe('pollJob', () => {
  it('polls until done and reports every update', async () => {
    const get = vi.fn().mockResolvedValueOnce(job('running', 1)).mockResolvedValueOnce(job('running', 2)).mockResolvedValueOnce(job('done', 3))
    const seen: number[] = []
    const out = await pollJob(get, job('queued'), { sleep: noSleep, onUpdate: (j) => seen.push(j.done) })
    expect(out.state).toBe('done')
    expect(seen).toEqual([0, 1, 2, 3])
    expect(get).toHaveBeenCalledTimes(3)
    expect(noSleep).toHaveBeenCalledWith(JOB_POLL_MS)
  })
  it('does not poll a job that is already finished', async () => {
    const get = vi.fn()
    expect((await pollJob(get, job('error'), { sleep: noSleep })).state).toBe('error')
    expect(get).not.toHaveBeenCalled()
  })
  it('stops on cancelled', async () => {
    const get = vi.fn().mockResolvedValue(job('cancelled', 1))
    expect((await pollJob(get, job('running'), { sleep: noSleep })).state).toBe('cancelled')
  })
  it('retries a failed poll, then gives up after three in a row', async () => {
    const ok = vi.fn().mockRejectedValueOnce(new Error('x')).mockResolvedValueOnce(job('done', 3))
    expect((await pollJob(ok, job('running'), { sleep: noSleep })).state).toBe('done')
    const bad = vi.fn().mockRejectedValue(new Error('down'))
    await expect(pollJob(bad, job('running'), { sleep: noSleep })).rejects.toThrow('down')
    expect(bad).toHaveBeenCalledTimes(3)
  })
  it('stops when told the page left', async () => {
    const get = vi.fn()
    let gone = false
    const out = await pollJob(get, job('running'), { sleep: async () => { gone = true }, stopped: () => gone })
    expect(out.state).toBe('running')
    expect(get).not.toHaveBeenCalled()
  })
  it('knows the terminal states', () => {
    expect(['queued', 'running'].map((s) => isTerminal({ state: s as LabJobState }))).toEqual([false, false])
    expect(['done', 'error', 'cancelled'].every((s) => isTerminal({ state: s as LabJobState }))).toBe(true)
  })
})
