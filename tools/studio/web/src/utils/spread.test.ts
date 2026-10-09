import { describe, expect, it } from 'vitest'
import type { Line } from '../api/types'
import { spreadPick } from './spread'

const L = (guid: string, emotion: string | null, len = 80): Line => ({ guid, text: 'x'.repeat(len), emotion, intensity: null, pace: null, instruct: null, baseline: null })

describe('spreadPick', () => {
  it('takes one mid-length line from each of the largest emotion groups', () => {
    const lines = [L('a1', 'calm'), L('a2', 'calm'), L('a3', 'calm'), L('b1', 'sad'), L('b2', 'sad'), L('c1', 'angry')]
    const pick = spreadPick(lines, 2)
    expect(pick).toHaveLength(2)
    expect(new Set(pick.map((g) => lines.find((l) => l.guid === g)!.emotion))).toEqual(new Set(['calm', 'sad']))
  })
  it('skips too-short and too-long lines and handles empty or null emotions', () => {
    expect(spreadPick([L('s', 'calm', 10), L('l', 'calm', 500)], 6)).toEqual([])
    expect(spreadPick([], 6)).toEqual([])
    expect(spreadPick([L('n', null)], 6)).toEqual(['n'])
  })
  it('never returns more than n or duplicates', () => {
    const lines = Array.from({ length: 20 }, (_, i) => L(`g${i}`, `e${i}`))
    const pick = spreadPick(lines, 6)
    expect(pick).toHaveLength(6)
    expect(new Set(pick).size).toBe(6)
  })
})
