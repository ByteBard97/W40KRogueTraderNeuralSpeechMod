import type { Bg3Voice, LabelDef, LabelValue } from '../api/types'

export type GenderFilter = 'all' | 'male' | 'female'
export type VoiceSort = 'lines' | 'name'
/** Label key -> the values to keep. A voice passes a label when it has any of them; labels combine with "and". */
export type LabelFilters = Record<string, string[]>

export const DO_NOT_USE = 'do not use'
/** The in-between steps of class and pitch, and the two levels each sits between. */
const BETWEEN: Record<string, string[]> = { 'low-middle': ['low', 'middle'], 'middle-high': ['middle', 'high'] }

/** A voice passes a label filter when any of its values is wanted; an in-between step also passes for either level next to it. */
const has = (v: LabelValue | undefined, wanted: string[]) => {
  const values = v === undefined ? [] : Array.isArray(v) ? v : [v]
  return values.some((x) => wanted.includes(x) || (BETWEEN[x] ?? []).some((n) => wanted.includes(n)))
}

/** Fully labelled: every required label is set, or the voice is marked "do not use" and needs nothing more. */
export function labelsComplete(mine: Record<string, LabelValue | undefined>, schema: LabelDef[]): boolean {
  return mine.reserve === DO_NOT_USE || schema.filter((d) => d.required).every((d) => mine[d.key] !== undefined && mine[d.key] !== '')
}

/** BG3 voices matching the search text, gender and label filters, in the chosen order. Ties in line count fall back to the name. */
export function filterVoices(voices: Bg3Voice[], query: string, gender: GenderFilter, sort: VoiceSort, labels: LabelFilters = {}): Bg3Voice[] {
  const t = query.trim().toLowerCase()
  const byName = (a: Bg3Voice, b: Bg3Voice) => a.name.localeCompare(b.name, 'en', { sensitivity: 'base' })
  const active = Object.entries(labels).filter(([, vals]) => vals.length)
  return voices
    .filter((v) => (!t || [v.name ?? '', ...(v.aliases ?? [])].some((n) => n.toLowerCase().includes(t))) && (gender === 'all' || v.gender === gender))
    .filter((v) => active.every(([key, vals]) => has(v.labels?.[key], vals)))
    .sort((a, b) => (sort === 'name' ? byName(a, b) : b.lines - a.lines || byName(a, b)))
}

/** How many of the five required labels the owner has set on this voice. */
export function requiredDone(v: Bg3Voice, schema: LabelDef[]): number {
  return schema.filter((d) => d.required && v.mine?.[d.key] !== undefined && v.mine[d.key] !== '').length
}

/** One-line summary of a voice's labels for a list row, e.g. "female · youth · low class · high pitch". */
export function labelSummary(v: Bg3Voice): string {
  const l = v.labels ?? {}
  const parts: string[] = []
  const add = (k: string, suffix = '') => { const x = l[k]; if (x) parts.push(`${Array.isArray(x) ? x.join('/') : x}${suffix}`) }
  add('gender'); add('age'); add('class', ' class'); add('pitch', ' pitch'); add('processing')
  return parts.join(' · ')
}

const AGE_FROM_CHARACTER: Record<string, string> = { young: 'youth', old: 'old', adult: 'adult', child: 'child' }

/** Label filters that match a Rogue Trader character: gender and age carry over (the character's words mapped to the label words). */
export function filtersForCharacter(c: { gender?: string | null; age?: string | null }): LabelFilters {
  const out: LabelFilters = {}
  if (c.gender === 'male' || c.gender === 'female') out.gender = [c.gender]
  const age = c.age ? AGE_FROM_CHARACTER[c.age] : undefined
  if (age) out.age = [age]
  return out
}
