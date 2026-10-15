import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { effectScope } from 'vue'
import { api } from '../api/client'
import type { LabJob, LabJobState } from '../api/labTypes'
import { lineFixture, optionsFixture, recipeFixture } from '../test-utils/labFixtures'

vi.mock('../api/client', () => ({
  api: { labOptions: vi.fn(), labSpeakers: vi.fn(), labRecipes: vi.fn(), labLines: vi.fn(), labPrepare: vi.fn(), labTakes: vi.fn(), labRender: vi.fn(), labJob: vi.fn(), labJobCancel: vi.fn() },
}))
vi.mock('../utils/labJob', async (orig) => {
  const m = await orig<typeof import('../utils/labJob')>()
  return { ...m, pollJob: (get: never, first: never, opts: object) => m.pollJob(get, first, { ...opts, sleep: async () => undefined }) }
})

import { useLabStore } from '../stores/lab'
import { useLabRender } from './useLabRender'

const job = (state: LabJobState, done: number): LabJob => ({ id: 'j', state, total: 4, done, take_ids: [], error: state === 'error' ? 'backend down' : null })

async function setup() {
  setActivePinia(createPinia())
  vi.mocked(api.labOptions).mockResolvedValue(optionsFixture())
  vi.mocked(api.labSpeakers).mockResolvedValue([{ speaker: 'Vladaym Tocara the Liege', slug: 'v', lines: 2, chars: 5 }])
  vi.mocked(api.labRecipes).mockResolvedValue([recipeFixture()])
  vi.mocked(api.labLines).mockResolvedValue({ speaker: 'Vladaym Tocara the Liege', ref: { wav: 'data/ref.wav' }, lines: [lineFixture('a', 0, 14), lineFixture('b', 1, 9)] })
  vi.mocked(api.labPrepare).mockResolvedValue({ stages: [], pieces: [], recipe: recipeFixture() })
  vi.mocked(api.labTakes).mockResolvedValue([])
  const lab = useLabStore()
  await lab.init()
  const scope = effectScope()
  const r = scope.run(() => useLabRender())!
  return { lab, r }
}

describe('useLabRender', () => {
  beforeEach(() => vi.clearAllMocks())

  it('renders the selected line with N seeds, tracks progress and refreshes takes', async () => {
    const { r } = await setup()
    vi.mocked(api.labRender).mockResolvedValue(job('queued', 0))
    vi.mocked(api.labJob).mockResolvedValueOnce(job('running', 2)).mockResolvedValueOnce(job('done', 4))
    r.setSeedCount(2)
    const seen: number[] = []
    const p = r.renderSelected()
    await p
    const body = vi.mocked(api.labRender).mock.calls[0][0]
    expect(body).toMatchObject({ speaker: 'Vladaym Tocara the Liege', items: [{ guid: 'a' }], ref: { wav: 'data/ref.wav' } })
    expect(body.seeds).toHaveLength(2)
    expect(r.job.value?.state).toBe('done')
    expect(r.running.value).toBe(false)
    expect(r.percent.value).toBe(100)
    expect(api.labTakes).toHaveBeenCalledTimes(2)
    seen.push(r.job.value!.done)
    expect(seen).toEqual([4])
  })

  it('renders every checked line in one job', async () => {
    const { lab, r } = await setup()
    lab.toggleCheck('a')
    lab.toggleCheck('b')
    vi.mocked(api.labRender).mockResolvedValue(job('done', 4))
    await r.renderChecked()
    expect(vi.mocked(api.labRender).mock.calls[0][0].items).toEqual([{ guid: 'a' }, { guid: 'b' }])
  })

  it('does nothing with nothing checked', async () => {
    const { r } = await setup()
    await r.renderChecked()
    expect(api.labRender).not.toHaveBeenCalled()
  })

  it('reports a job error', async () => {
    const { r } = await setup()
    vi.mocked(api.labRender).mockResolvedValue(job('error', 1))
    await r.renderSelected()
    expect(r.error.value).toBe('backend down')
  })

  it('reports a request failure and clears the job', async () => {
    const { r } = await setup()
    vi.mocked(api.labRender).mockRejectedValue(new Error('model is down'))
    await r.renderSelected()
    expect(r.error.value).toBe('model is down')
    expect(r.job.value).toBeNull()
  })

  it('cancels a running job', async () => {
    const { r } = await setup()
    r.job.value = job('running', 1)
    vi.mocked(api.labJobCancel).mockResolvedValue(job('cancelled', 1))
    await r.cancel()
    expect(api.labJobCancel).toHaveBeenCalledWith('j')
    expect(r.job.value?.state).toBe('cancelled')
  })
})
