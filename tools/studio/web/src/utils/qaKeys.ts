export type QaAction = 'next' | 'prev' | 'play' | 'good' | 'bad' | 'clear' | 'nextUnjudged' | 'toggleFx'

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
  return KEY_ACTIONS[key.length === 1 ? key.toLowerCase() : key] ?? null
}

export const QA_TAGS = [
  'truncated', 'garbled', 'runaway', 'wrong voice', 'wrong emotion',
  'robotic', 'artifact', 'mispronounced', 'too fast/slow', 'bad pause',
]
