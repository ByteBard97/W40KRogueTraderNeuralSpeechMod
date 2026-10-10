const SECONDS_PER_MINUTE = 60
const MS_PER_S = 1000
const TENTH = 10

/** 7 -> "0:07"; 61 -> "1:01". */
export function formatClock(totalS: number): string {
  const s = Math.max(0, Math.floor(totalS))
  return `${Math.floor(s / SECONDS_PER_MINUTE)}:${String(s % SECONDS_PER_MINUTE).padStart(2, '0')}`
}

/** 1.84 -> "0:01.8"; used where the playhead is shown to a tenth of a second. */
export function formatPlayhead(totalS: number): string {
  const t = Math.max(0, Number.isFinite(totalS) ? totalS : 0)
  const tenths = Math.floor(t * TENTH) % TENTH
  return `${formatClock(t)}.${tenths}`
}

export const secondsSince = (startMs: number, nowMs = Date.now()) => Math.floor((nowMs - startMs) / MS_PER_S)
