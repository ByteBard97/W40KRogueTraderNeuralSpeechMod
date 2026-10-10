import type { SpeakerSummary } from '../api/types'
import type { DotStatus } from '../components/ui/StatusDot.vue'

export type Stage = 'registered' | 'picked' | 'progress' | 'idle'
export type ShowFilter = 'all' | 'todo' | 'done'
export type RowKind = 'named' | 'slot' | 'real'

export interface SpeakerRow {
  speaker: SpeakerSummary
  kind: RowKind
  stage: Stage
  dot: DotStatus
  /** Status text shown at the end of the row. */
  text: string
  /** Whether the text is progress (brass) rather than idle (grey). */
  active: boolean
  lines: number
}

const EXT = /\.[a-z0-9]+$/i

/** Kind from the server when it sends one, else a guess from origin and the pool_ prefix. */
export function kindOf(s: SpeakerSummary): RowKind {
  if (s.kind) return s.kind
  if (s.origin === 'real') return 'real'
  return s.name.startsWith('pool_') ? 'slot' : 'named'
}

export function stageOf(s: SpeakerSummary): Stage {
  if (s.registered) return 'registered'
  if (s.has_pick) return 'picked'
  if ((s.ranked ?? 0) > 0) return 'progress'
  return 'idle'
}

const DOT: Record<Stage, DotStatus> = { registered: 'done', picked: 'picked', progress: 'progress', idle: 'idle' }

export function pickLabel(s: SpeakerSummary): string {
  return s.pick ? s.pick.replace(EXT, '') : ''
}

/** `slotLines` maps a slot's speaker key to the lines Pools routes to it; the speaker list counts 0 for slots. */
export function toRow(s: SpeakerSummary, slotLines: Record<string, number> = {}): SpeakerRow {
  const kind = kindOf(s)
  const stage = stageOf(s)
  const lines = kind === 'slot' && s.name in slotLines ? slotLines[s.name] : s.line_count
  let text: string
  if (stage === 'registered') text = `registered ${pickLabel(s)}`.trim()
  else if (stage === 'picked') text = `picked ${pickLabel(s)}`.trim()
  else if (stage === 'progress') text = `${s.ranked} / ${s.candidates ?? '?'} ranked`
  else if (s.status === 'profile') text = 'profile saved'
  else if (kind === 'real') text = lines === 0 ? 'no lines' : 'source set'
  else text = 'not started'
  return { speaker: s, kind, stage, dot: DOT[stage], text, active: stage !== 'idle', lines }
}

export const isDone = (r: SpeakerRow) => r.stage === 'registered' || r.stage === 'picked'

export function matchesFilter(r: SpeakerRow, q: string, show: ShowFilter): boolean {
  const query = q.trim().toLowerCase()
  if (query && !r.speaker.name.toLowerCase().includes(query)) return false
  if (show === 'done') return isDone(r)
  if (show === 'todo') return !isDone(r)
  return true
}

export interface Counts {
  total: number
  needVoice: number
  haveSource: number
  picked: number
  registered: number
  progress: number
  idle: number
  done: number
}

export function countRows(rows: SpeakerRow[]): Counts {
  const n = (st: Stage) => rows.filter((r) => r.stage === st).length
  const registered = n('registered')
  const picked = n('picked')
  return {
    total: rows.length,
    needVoice: rows.filter((r) => r.speaker.status === 'needs_voice').length,
    haveSource: rows.filter((r) => r.speaker.status === 'source').length,
    picked,
    registered,
    progress: n('progress'),
    idle: n('idle'),
    done: registered + picked,
  }
}

/** Where Continue / N goes: the first speaker with ranking under way, else the first designed speaker not started. Named speakers come before slots. */
export function continueTarget(rows: SpeakerRow[]): SpeakerRow | null {
  const open = rows.filter((r) => r.kind !== 'real' && !isDone(r))
  const rank = (r: SpeakerRow) => (r.stage === 'progress' ? 0 : r.kind === 'named' ? 1 : 2)
  return open.length ? open.reduce((a, b) => (rank(b) < rank(a) ? b : a)) : null
}
