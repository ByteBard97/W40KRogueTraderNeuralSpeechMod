import { describe, expect, it } from 'vitest'
import { moveItem } from './order'

describe('moveItem', () => {
  it('moves forward and back without mutating', () => {
    const a = ['a', 'b', 'c', 'd']
    expect(moveItem(a, 0, 2)).toEqual(['b', 'c', 'a', 'd'])
    expect(moveItem(a, 3, 0)).toEqual(['d', 'a', 'b', 'c'])
    expect(a).toEqual(['a', 'b', 'c', 'd'])
  })
  it('clamps out-of-range targets and ignores bad sources', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 99)).toEqual(['b', 'c', 'a'])
    expect(moveItem(['a', 'b', 'c'], 2, -5)).toEqual(['c', 'a', 'b'])
    expect(moveItem(['a', 'b'], 5, 0)).toEqual(['a', 'b'])
    expect(moveItem([], 0, 0)).toEqual([])
  })
})
