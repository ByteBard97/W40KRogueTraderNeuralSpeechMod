import { describe, expect, it } from 'vitest'
import { ago } from './ago'

const now = Date.parse('2026-10-10T12:00:00Z')

describe('ago', () => {
  it('words a recent timestamp', () => {
    expect(ago('2026-10-10T11:59:50Z', now)).toBe('just now')
    expect(ago('2026-10-10T11:55:00Z', now)).toBe('5 min ago')
    expect(ago('2026-10-10T09:00:00Z', now)).toBe('3 h ago')
    expect(ago('2026-10-07T12:00:00Z', now)).toBe('3 d ago')
  })
  it('returns text it cannot read as it was', () => {
    expect(ago('yesterday', now)).toBe('yesterday')
  })
})
