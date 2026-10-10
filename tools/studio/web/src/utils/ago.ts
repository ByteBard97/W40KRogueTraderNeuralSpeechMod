const SECONDS = 1000
const MINUTE = 60
const HOUR = 3600
const DAY = 86400

/** "2 min ago" for a timestamp the server wrote; the raw text when it cannot be read as a date. */
export function ago(stamp: string, nowMs = Date.now()): string {
  const t = Date.parse(stamp)
  if (Number.isNaN(t)) return stamp
  const s = Math.max(0, Math.round((nowMs - t) / SECONDS))
  if (s < MINUTE) return 'just now'
  if (s < HOUR) return `${Math.floor(s / MINUTE)} min ago`
  if (s < DAY) return `${Math.floor(s / HOUR)} h ago`
  return `${Math.floor(s / DAY)} d ago`
}
