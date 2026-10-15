import type { LabCurrent, LabFlag, LabLine, LabMetrics, LabPronunciation, LabRecipe, LabRef, LabRenderBody, LabRenderItem } from '../api/labTypes'

export const MAX_SEEDS = 6
export const MIN_SEEDS = 1
/** Below this crest factor (dB) a take sounds compressed; mirrors CREST_BAD_DB in lab_audio.py. */
export const CREST_BAD_DB = 11
/** A model peak above this went past full scale before the 16-bit write. */
export const FULL_SCALE = 1
const SEED_RANGE = 2 ** 31
export const CARRIER_PLACEHOLDER = '{w}'
export const DEFAULT_CARRIER = `He said ${CARRIER_PLACEHOLDER} and left.`

export type LineSort = 'order' | 'worst'
export type LineFilter = 'all' | 'flagged'
export type FlagTone = 'bad' | 'warn' | 'ok' | 'none'

/** Deep copy of a recipe (they are plain JSON). */
export const cloneRecipe = (r: LabRecipe): LabRecipe => JSON.parse(JSON.stringify(r)) as LabRecipe

export const isFlagged = (c: LabCurrent | null) => !!c && (c.flag === 'overdriven' || c.flag === 'clipped')

/** Colour class for a crest/flag pair: red overdriven, amber clipped, otherwise ok (or none without a measurement). */
export function flagTone(m: Pick<LabMetrics, 'flag' | 'crest_db'> | null | undefined): FlagTone {
  if (!m) return 'none'
  const flag: LabFlag = m.flag
  if (flag === 'overdriven' || (m.crest_db !== null && m.crest_db < CREST_BAD_DB)) return 'bad'
  if (flag === 'clipped') return 'warn'
  return m.crest_db === null ? 'none' : 'ok'
}

/** Lines in the chosen order. "worst" puts the lowest crest first and lines without a render last. Never mutates. */
export function sortLines(lines: LabLine[], sort: LineSort): LabLine[] {
  const byOrder = (a: LabLine, b: LabLine) => a.order - b.order
  if (sort === 'order') return [...lines].sort(byOrder)
  const crest = (l: LabLine) => l.current?.crest_db ?? Number.POSITIVE_INFINITY
  return [...lines].sort((a, b) => crest(a) - crest(b) || byOrder(a, b))
}

/** Typing two hyphens finds an em-dash (and an en-dash counts as one), so nobody needs the key for it. */
export const foldDashes = (s: string) => s.replace(/[–—]/g, '—')
export const typedDashes = (s: string) => s.replace(/--+/g, '—')

export function filterLines(lines: LabLine[], filter: LineFilter, query: string): LabLine[] {
  const q = typedDashes(foldDashes(query.trim().toLowerCase()))
  return lines.filter((l) => (filter === 'all' || isFlagged(l.current)) && (!q || foldDashes(l.text.toLowerCase()).includes(q)))
}

/** Seeds for N renders of one item: the typed seed and the ones after it, or N random whole numbers. */
export function seedsFor(recipe: LabRecipe, count: number, rng: () => number = Math.random): number[] {
  const n = Math.min(MAX_SEEDS, Math.max(MIN_SEEDS, Math.floor(count) || MIN_SEEDS))
  const typed = String(recipe.seed ?? '').trim()
  if (typed && /^\d+$/.test(typed)) return Array.from({ length: n }, (_, i) => Number(typed) + i)
  return Array.from({ length: n }, () => Math.floor(rng() * SEED_RANGE))
}

/** Recipe as sent: pronunciation rows with no word are dropped, blank numeric fields become null. */
export function cleanRecipe(r: LabRecipe): LabRecipe {
  const c = cloneRecipe(r)
  c.pronunciation = c.pronunciation.filter((p: LabPronunciation) => p.word.trim() !== '')
  return c
}

export function buildRenderBody(opts: { speaker: string; items: LabRenderItem[]; recipe: LabRecipe; seedCount: number; ref?: LabRef | null; rng?: () => number }): LabRenderBody {
  const recipe = cleanRecipe(opts.recipe)
  const body: LabRenderBody = { speaker: opts.speaker, items: opts.items, recipe, seeds: seedsFor(recipe, opts.seedCount, opts.rng) }
  if (opts.ref) body.ref = opts.ref
  return body
}

/** One line of the recipe for a take card: "cfg 3 · 10 steps · whole · em-dash keep". */
export function recipeSummary(r: LabRecipe): string {
  const dash = r.punctuation?.em_dash ?? 'keep'
  const dashText = dash === 'pause' ? `em-dash pause ${r.pause_ms}ms` : `em-dash ${dash}`
  const joins = [r.level_match && 'level match', r.trim_silence && 'trim', r.onset_soften_db < 0 && `soften ${r.onset_soften_db}dB`].filter(Boolean)
  return [`cfg ${r.cfg}`, `${r.timesteps} steps`, r.split?.mode ?? 'whole', dashText, ...joins].join(' · ')
}

export const carrierSentence = (template: string, word: string) => template.split(CARRIER_PLACEHOLDER).join(word)

/** Base recipe with exactly one pronunciation override, for the word test. */
export function variantRecipe(base: LabRecipe, word: string, variant: { mode: LabPronunciation['mode']; value: string }): LabRecipe {
  const r = cloneRecipe(base)
  r.pronunciation = variant.value.trim() ? [{ word, mode: variant.mode, value: variant.value }] : []
  return r
}

export const variantLabel = (v: { mode: string; value: string }) => (v.value.trim() ? `${v.mode}: ${v.value}` : 'no override')

export const modelExceeded = (peak: number) => peak > FULL_SCALE
