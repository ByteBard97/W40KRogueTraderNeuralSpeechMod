import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { JobItem, JobState, JobView } from '../api/jobs'

const api = vi.hoisted(() => ({ jobsActive: vi.fn(), job: vi.fn(), jobSubmit: vi.fn(), jobCancel: vi.fn() }))
vi.mock('../api/client', async (orig) => ({ ...(await orig<typeof import('../api/client')>()), api }))

import { ApiRequestError } from '../api/client'
import { useLiveTakesStore } from './liveTakes'
import { isMissingRoute, useWorkbenchJobsStore } from './workbenchJobs'

const item = (n: number, state: JobState, result: unknown = null): JobItem => ({ n, state, seed: 1, cfg: 2, timesteps: 10, text: 't', elapsed_s: 1, take: null, result: result as JobItem['result'], error: null, fx_error: null })
const job = (over: Partial<JobView> = {}) => ({ id: 'j1', kind: 'clone', slug: 'ruoldo', label: 'Generating', state: 'running', total: 2, done: 0, index: 1, items: [], takes: [], fx: [], error: null, cancel_requested: false, elapsed_s: 0, expected_s: null, current: null, ...over }) as JobView

describe('workbench jobs store', () => {
  beforeEach(() => { setActivePinia(createPinia()); vi.useFakeTimers(); vi.clearAllMocks() })
  afterEach(() => vi.useRealTimers())

  it('hands each finished clone take to the page once', async () => {
    const t = { id: 't1' }
    api.jobsActive.mockResolvedValue([job({ items: [item(0, 'done', t), item(1, 'running')] })])
    const s = useWorkbenchJobsStore()
    const got = vi.fn()
    await s.attach('ruoldo', got)
    await s.poll()
    expect(got).toHaveBeenCalledTimes(1)
    expect(got).toHaveBeenCalledWith(t)
    expect(s.activeFor('ruoldo', 'clone')).toHaveLength(1)
    s.detach('ruoldo')
  })

  it('puts a finished design take in the live takes and picks up the last result after the job leaves the active list', async () => {
    const live = { file: 'live_tmp/a.wav', seed: 1, cfg: 2, timesteps: 10, seconds: 1, description: 'd', text: 't' }
    api.jobSubmit.mockResolvedValue(job({ id: 'j2', kind: 'design', total: 1, state: 'queued', items: [item(0, 'queued')] }))
    api.jobsActive.mockResolvedValueOnce([job({ id: 'j2', kind: 'design', items: [item(0, 'running')] })]).mockResolvedValue([])
    api.job.mockResolvedValue(job({ id: 'j2', kind: 'design', state: 'done', done: 1, items: [item(0, 'done', live)] }))
    const s = useWorkbenchJobsStore()
    await s.attach('ruoldo', vi.fn())
    await s.submit('ruoldo', 'design', [{ description: 'd' }])
    await s.poll()                      // job gone from the active list: final state is fetched by id
    expect(useLiveTakesStore().forSlug('ruoldo')).toEqual([live])
    expect(s.activeFor('ruoldo')).toEqual([])
    await s.poll()
    expect(useLiveTakesStore().forSlug('ruoldo')).toHaveLength(1)
    s.detach('ruoldo')
  })

  it('records why a job failed', async () => {
    api.jobsActive.mockResolvedValue([])
    api.jobSubmit.mockResolvedValue(job({ state: 'queued' }))
    api.job.mockResolvedValue(job({ state: 'failed', error: 'the model is down' }))
    const s = useWorkbenchJobsStore()
    await s.attach('ruoldo', vi.fn())
    await s.submit('ruoldo', 'clone', [{}])
    await s.poll()
    expect(s.problem.ruoldo).toBe('the model is down')
    s.detach('ruoldo')
  })

  it('cancels through the api and recognises a server without a queue', async () => {
    api.jobCancel.mockResolvedValue(job())
    api.jobsActive.mockResolvedValue([])
    await useWorkbenchJobsStore().cancel('ruoldo', 'j1')
    expect(api.jobCancel).toHaveBeenCalledWith('j1')
    expect(isMissingRoute(new ApiRequestError(404, 'no route'))).toBe(true)
    expect(isMissingRoute(new ApiRequestError(500, 'boom'))).toBe(false)
  })
})
