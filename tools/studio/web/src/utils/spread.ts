import type { Line } from '../api/types'

const MIN_CHARS = 50
const MAX_CHARS = 220

export function spreadPick(lines: Line[], n = 6): string[] {
  const groups = new Map<string, Line[]>()
  for (const l of lines) {
    if (l.text.length <= MIN_CHARS || l.text.length >= MAX_CHARS) continue
    const k = l.emotion ?? ''
    groups.set(k, [...(groups.get(k) ?? []), l])
  }
  return [...groups.values()]
    .sort((a, b) => b.length - a.length)
    .slice(0, n)
    .map((g) => g[Math.floor(g.length / 2)].guid)
}
