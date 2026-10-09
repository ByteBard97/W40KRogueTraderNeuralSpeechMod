import { describe, expect, it } from 'vitest'
import { keyAction } from './qaKeys'

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
})
