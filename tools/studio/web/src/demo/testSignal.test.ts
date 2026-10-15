import { describe, expect, it } from 'vitest'
import { makeTestSignal, TEST_SIGNAL_SECONDS } from './testSignal'

describe('built-in test signal', () => {
  const sig = makeTestSignal(48000)
  it('is the advertised length, finite and within range', () => {
    expect(sig.length).toBe(48000 * TEST_SIGNAL_SECONDS)
    let peak = 0
    for (const v of sig) { expect(Number.isFinite(v)).toBe(true); peak = Math.max(peak, Math.abs(v)) }
    expect(peak).toBeGreaterThan(0.3)
    expect(peak).toBeLessThanOrEqual(1)
  })
  it('has real energy and also gaps between bursts', () => {
    const rms = (a: Float32Array) => Math.sqrt(a.reduce((s, v) => s + v * v, 0) / a.length)
    expect(rms(sig)).toBeGreaterThan(0.01)
    expect(rms(sig.subarray(Math.round(48000 * 0.45), Math.round(48000 * 0.5)))).toBeLessThan(1e-6)
  })
})
