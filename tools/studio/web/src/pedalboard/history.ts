// Undo/redo as whole-graph snapshots. A board is a few dozen small nodes, so snapshots are cheaper to get right than per-action inverses.

export const HISTORY_LIMIT = 100
// A knob drag fires many changes in a row; changes to the same control inside this window are one undo step.
export const COALESCE_MS = 600

export class History<T> {
  private past: T[] = []
  private future: T[] = []
  private lastKey: string | null = null
  private lastAt = 0

  get undoCount(): number { return this.past.length }
  get redoCount(): number { return this.future.length }

  /** Call BEFORE a change with the state it is about to replace. A repeat of `coalesceKey` within the window adds no step. */
  record(before: T, now: number, coalesceKey: string | null = null): void {
    const repeat = coalesceKey !== null && coalesceKey === this.lastKey && now - this.lastAt < COALESCE_MS
    this.lastKey = coalesceKey
    this.lastAt = now
    if (repeat) return
    this.past.push(before)
    if (this.past.length > HISTORY_LIMIT) this.past.shift()
    this.future = []
  }

  undo(current: T): T | null {
    const prev = this.past.pop()
    if (prev === undefined) return null
    this.future.push(current)
    this.lastKey = null
    return prev
  }

  redo(current: T): T | null {
    const next = this.future.pop()
    if (next === undefined) return null
    this.past.push(current)
    this.lastKey = null
    return next
  }

  clear(): void {
    this.past = []
    this.future = []
    this.lastKey = null
  }
}
