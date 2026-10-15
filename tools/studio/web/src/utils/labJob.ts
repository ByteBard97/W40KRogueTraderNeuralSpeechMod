import type { LabJob } from '../api/labTypes'

export const JOB_POLL_MS = 400
export const TERMINAL_STATES = ['done', 'error', 'cancelled'] as const
export const isTerminal = (j: Pick<LabJob, 'state'>) => (TERMINAL_STATES as readonly string[]).includes(j.state)

export interface PollOptions {
  intervalMs?: number
  sleep?: (ms: number) => Promise<void>
  onUpdate?: (job: LabJob) => void
  /** Stop polling (the page left); the last seen job is returned. */
  stopped?: () => boolean
  /** Consecutive failed polls tolerated before giving up. */
  maxFailures?: number
}

const MAX_FAILURES = 3
const defaultSleep = (ms: number) => new Promise<void>((r) => setTimeout(r, ms))

/** Poll `get` until the job is done, errored or cancelled. A failed poll is retried a few times, then rethrown. */
export async function pollJob(get: (id: string) => Promise<LabJob>, first: LabJob, opts: PollOptions = {}): Promise<LabJob> {
  const { intervalMs = JOB_POLL_MS, sleep = defaultSleep, onUpdate, stopped, maxFailures = MAX_FAILURES } = opts
  let job = first
  let failures = 0
  onUpdate?.(job)
  while (!isTerminal(job) && !stopped?.()) {
    await sleep(intervalMs)
    if (stopped?.()) break
    try {
      job = await get(job.id)
      failures = 0
      onUpdate?.(job)
    } catch (e) {
      if (++failures >= maxFailures) throw e
    }
  }
  return job
}
