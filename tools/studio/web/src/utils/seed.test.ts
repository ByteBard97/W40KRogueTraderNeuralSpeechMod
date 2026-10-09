import { describe, expect, it } from 'vitest'
import { pickSeed } from './seed'

describe('pickSeed', () => {
  it('keeps a typed seed', () => expect(pickSeed(' 4242 ')).toBe('4242'))
  it('rolls a random 31-bit integer when blank', () => {
    expect(pickSeed('', () => 0.5)).toBe(String(Math.floor(0.5 * 2 ** 31)))
    const s = Number(pickSeed('   '))
    expect(Number.isInteger(s) && s >= 0 && s < 2 ** 31).toBe(true)
  })
})
