import { describe, expect, it } from 'vitest'
import { seedsFor } from './seedPolicy'

const seq = () => { let n = 0; return () => (++n) / 10 }

describe('seedsFor', () => {
  it('draws a different seed per line for "new"', () => {
    const s = seedsFor('new', '', 3, seq())
    expect(new Set(s).size).toBe(3)
  })
  it('uses one seed for every line for "one"', () => {
    const s = seedsFor('one', '', 3, seq())
    expect(new Set(s).size).toBe(1)
  })
  it('uses the typed seed for "fixed", and falls back to per-line seeds when it is blank', () => {
    expect(seedsFor('fixed', ' 42 ', 2)).toEqual(['42', '42'])
    expect(new Set(seedsFor('fixed', ' ', 3, seq())).size).toBe(3)
  })
})
