import { describe, expect, it } from 'vitest'
import { keyAction, tagIndex, tagKey } from './qaKeys'

describe('keyAction', () => {
  it.each([
    ['j', 'next'], ['k', 'prev'], [' ', 'play'], ['g', 'good'], ['b', 'bad'], ['u', 'clear'], ['n', 'nextUnjudged'], ['x', 'toggleFx'],
  ])('%j maps to %s', (key, action) => expect(keyAction(key)).toBe(action))

  it('ignores case and unknown keys', () => {
    expect(keyAction('J')).toBe('next')
    expect(keyAction('q')).toBeNull()
    expect(keyAction('Enter')).toBeNull()
    expect(keyAction('')).toBeNull()
  })

  it('maps 1-9 and 0 to the ten tags', () => {
    expect(keyAction('1')).toBe('tag0')
    expect(keyAction('9')).toBe('tag8')
    expect(keyAction('0')).toBe('tag9')
    expect(tagIndex('tag9')).toBe(9)
    expect(tagIndex('next')).toBeNull()
    expect([0, 8, 9].map(tagKey)).toEqual(['1', '9', '0'])
  })
})
