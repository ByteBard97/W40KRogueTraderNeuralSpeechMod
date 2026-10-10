import { defineStore } from 'pinia'
import { ref } from 'vue'
import { api, ApiRequestError } from '../api/client'
import { isActive, type JobKind, type JobView } from '../api/jobs'
import type { LiveTake, Take } from '../api/types'
import { useLiveTakesStore } from './liveTakes'

const POLL_MS = 1000
const MISSING_ROUTE = [404, 405]

/** True when the server has no job queue (an older build); callers then fall back to the synchronous routes. */
export const isMissingRoute = (e: unknown) => e instanceof ApiRequestError && MISSING_ROUTE.includes(e.status)

/**
 * Generation jobs of the speaker pages. A job runs on the server whether or not the page is open; this store polls
 * `/api/jobs` once a second while a speaker page is watching, hands finished clone takes to that page's `onTake` and
 * finished design takes to the live-takes store, and keeps track of jobs that finish while the page was elsewhere.
 */
export const useWorkbenchJobsStore = defineStore('workbenchJobs', () => {
  const live = useLiveTakesStore()
  const active = ref<Record<string, JobView[]>>({})
  const problem = ref<Record<string, string>>({})
  const tracked = new Map<string, string>()          // job id -> slug, until its final state has been applied
  const applied = new Set<string>()                  // "<job>:<item>" already handed over
  const watchers = new Map<string, (t: Take) => void>()
  let timer: ReturnType<typeof setInterval> | null = null

  const activeFor = (slug: string, kind?: JobKind) => (active.value[slug] ?? []).filter((j) => !kind || j.kind === kind)

  function apply(job: JobView) {
    for (const it of job.items) {
      const key = `${job.id}:${it.n}`
      if (it.state === 'done' && it.result && !applied.has(key)) {
        if (job.kind === 'design') live.add(job.slug, it.result as LiveTake)
        else if (watchers.has(job.slug)) watchers.get(job.slug)?.(it.result as Take)
        else continue
        applied.add(key)
      }
      if (it.fx_error) problem.value[job.slug] = `FX failed on a take: ${it.fx_error}`
    }
    if (job.state === 'failed' && job.error) problem.value[job.slug] = job.error
  }

  async function pollSlug(slug: string) {
    const listed = await api.jobsActive(slug)
    const ids = new Set(listed.map((j) => j.id))
    for (const j of listed) {
      tracked.set(j.id, slug)
      apply(j)
    }
    for (const [id, s] of [...tracked]) {
      if (s !== slug || ids.has(id)) continue
      try {
        apply(await api.job(id))
        tracked.delete(id)
      } catch {
        tracked.delete(id)
      }
    }
    active.value[slug] = listed.filter(isActive)
  }

  async function poll() {
    for (const slug of watchers.keys()) {
      try {
        await pollSlug(slug)
      } catch {
        /* a failed poll is retried on the next tick */
      }
    }
    if (![...watchers.keys()].some((s) => (active.value[s] ?? []).length || [...tracked.values()].includes(s))) stopTimer()
  }

  function ensureTimer() {
    if (!timer) timer = setInterval(poll, POLL_MS)
  }
  function stopTimer() {
    if (timer) clearInterval(timer)
    timer = null
  }

  /** Start watching `slug`: resumes jobs still running from before, applies results that landed while the page was away. */
  async function attach(slug: string, onTake: (t: Take) => void) {
    watchers.set(slug, onTake)
    try {
      await pollSlug(slug)
    } catch {
      return
    }
    if ((active.value[slug] ?? []).length) ensureTimer()
  }
  function detach(slug: string) {
    watchers.delete(slug)
    if (!watchers.size) stopTimer()
  }

  async function submit(slug: string, kind: JobKind, items: object[], opts: { fx?: string[]; label?: string } = {}): Promise<JobView> {
    delete problem.value[slug]
    const job = await api.jobSubmit(slug, kind, { items, ...opts })
    tracked.set(job.id, slug)
    active.value[slug] = [...activeFor(slug), job]
    ensureTimer()
    return job
  }

  async function cancel(slug: string, id: string) {
    await api.jobCancel(id)
    await pollSlug(slug).catch(() => undefined)
  }

  return { active, problem, activeFor, attach, detach, submit, cancel, poll }
})
