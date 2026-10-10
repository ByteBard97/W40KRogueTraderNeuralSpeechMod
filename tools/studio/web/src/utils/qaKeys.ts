/** `tag0`..`tag9`: the tag at that position in QA_TAGS (keys 1-9 then 0). */
export type QaAction = 'next' | 'prev' | 'play' | 'good' | 'bad' | 'clear' | 'nextUnjudged' | 'toggleFx' | `tag${number}`

const KEY_ACTIONS: Record<string, QaAction> = {
  j: 'next',
  k: 'prev',
  ' ': 'play',
  g: 'good',
  b: 'bad',
  u: 'clear',
  n: 'nextUnjudged',
  x: 'toggleFx',
}

/** Pure key-to-action map for Render QA; null for keys the page does not use. */
export function keyAction(key: string): QaAction | null {
  if (/^[0-9]$/.test(key)) return `tag${(Number(key) + 9) % 10}`
  return KEY_ACTIONS[key.length === 1 ? key.toLowerCase() : key] ?? null
}

/** Index into QA_TAGS for a `tagN` action, or null. */
export function tagIndex(action: QaAction): number | null {
  const m = /^tag(\d)$/.exec(action)
  return m ? Number(m[1]) : null
}

export const QA_TAGS = [
  'truncated', 'garbled', 'runaway', 'wrong voice', 'wrong emotion',
  'robotic', 'artifact', 'mispronounced', 'too fast/slow', 'bad pause',
]

/** Keycap for the tag at `i`: 1-9, then 0. */
export const tagKey = (i: number) => String((i + 1) % 10)

/** What each automatic flag means (thresholds live in qa.py). Unknown flags show no explanation. */
export const FLAG_WHY: Record<string, string> = {
  cap_hit: 'hit the 30 s length cap',
  slow: 'below 3.5 chars/s',
  very_long: 'over 60 s',
  too_long: 'longer than the text needs',
  fast: 'above 20 chars/s',
}

export const COMPRESSOR_KEY = 'studio.qa.fx'
