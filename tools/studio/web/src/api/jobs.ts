import type { LiveTake, Take } from './types'

/** Shapes of the server job queue (`/api/jobs`, `/api/speakers/{slug}/clone|design/jobs`). Not yet in API-CHANGES.md; read from `studio_server/jobs.py`. */
export type JobState = 'queued' | 'running' | 'done' | 'failed' | 'cancelled'
export type JobKind = 'clone' | 'design'

export interface JobItem {
  n: number
  state: JobState
  seed: number
  cfg: number
  timesteps: number
  text: string | null
  elapsed_s: number | null
  take: string | null
  /** A finished clone item carries the take; a finished design item carries the live take. */
  result: Take | LiveTake | null
  error: string | null
  fx_error: string | null
}

export interface JobCurrent {
  n: number
  text: string | null
  seed: number
  cfg: number
  timesteps: number
  elapsed_s: number | null
  expected_s: number | null
}

export interface JobView {
  id: string
  kind: JobKind
  slug: string
  label: string
  state: JobState
  total: number
  done: number
  /** 1-based number of the item in progress (0 before the first starts). */
  index: number
  items: JobItem[]
  takes: string[]
  fx: string[]
  error: string | null
  cancel_requested: boolean
  elapsed_s: number
  expected_s: number | null
  current: JobCurrent | null
}

export const JOB_ACTIVE: JobState[] = ['queued', 'running']
export const isActive = (j: JobView) => JOB_ACTIVE.includes(j.state)
