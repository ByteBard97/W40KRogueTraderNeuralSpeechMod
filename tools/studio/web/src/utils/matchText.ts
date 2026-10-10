import type { MatchRowData } from '../api/types'

const upFirst = (s: string) => s.charAt(0).toUpperCase() + s.slice(1)
const ensureStop = (s: string) => (/[.!?]$/.test(s) ? s : `${s}.`)

export const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? '' : 's'}`
export const entryName = (r: MatchRowData) => r.name ?? r.label ?? r.entry

/** Why the match was flagged, from the warning and the homonyms; empty for a clean match. */
export function whyFlagged(r: MatchRowData): string {
  const parts: string[] = []
  if (r.warning) parts.push(ensureStop(upFirst(r.warning)))
  if (r.ambiguous_with?.length) {
    parts.push(`Also matches ${r.ambiguous_with.join(', ')}.${r.has_bank ? ` Accepting uses the ${r.speaker} bank.` : ''}`)
  }
  return parts.join(' ')
}

export const decisionLabel = (r: MatchRowData) =>
  r.decision === 'accept' ? 'Accepted' : r.decision === 'reject' ? 'Rejected' : r.suggest ? `suggest ${r.suggest}` : ''
