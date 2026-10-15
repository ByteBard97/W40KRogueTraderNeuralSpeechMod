import { describe, expect, it } from 'vitest'
import { COALESCE_MS, History, HISTORY_LIMIT } from './history'

describe('History', () => {
  it('undoes and redoes in order, and a new change drops the redo steps', () => {
    const h = new History<number>()
    h.record(1, 0)
    h.record(2, 1)
    expect(h.undo(3)).toBe(2)
    expect(h.undo(2)).toBe(1)
    expect(h.undo(1)).toBeNull()
    expect(h.redo(1)).toBe(2)
    h.record(9, 2)
    expect(h.redoCount).toBe(0)
  })

  it('merges changes to the same key inside the window and splits them outside it or for another key', () => {
    const h = new History<number>()
    h.record(0, 0, 'knob')
    h.record(1, 100, 'knob')
    h.record(2, 100 + COALESCE_MS - 1, 'knob')
    expect(h.undoCount).toBe(1)
    h.record(3, 100 + COALESCE_MS - 1, 'other')
    expect(h.undoCount).toBe(2)
    h.record(4, 5000, 'other')
    expect(h.undoCount).toBe(3)
    h.record(5, 5001)
    h.record(6, 5002)
    expect(h.undoCount).toBe(5)
  })

  it('keeps at most the limit, dropping the oldest', () => {
    const h = new History<number>()
    for (let i = 0; i < HISTORY_LIMIT + 20; i++) h.record(i, i)
    expect(h.undoCount).toBe(HISTORY_LIMIT)
    let last = -1
    for (let s = h.undo(0); s !== null; s = h.undo(0)) last = s
    expect(last).toBe(20)
  })
})
