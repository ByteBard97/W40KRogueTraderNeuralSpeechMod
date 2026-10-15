import { describe, expect, it } from 'vitest'
import type { CatalogControl } from '../../pedalboard/types'
import { decimalsOf, fromT, toT, wheelValue } from './controlMath'

const hz: CatalogControl = { label: 'Cutoff Hz', type: 'hslider', init: 100, min: 20, max: 2020, step: 1 }
const lin: CatalogControl = { label: 'Level dB', type: 'hslider', init: 0, min: -60, max: 12, step: 0.1 }

describe('controlMath', () => {
  it('round-trips a value through the slider position', () => {
    for (const c of [hz, lin]) for (const v of [c.min, c.init, c.max]) expect(fromT(c, toT(c, v))).toBeCloseTo(v, 6)
  })
  it('skews Hz controls toward the low end and leaves others linear', () => {
    expect(toT(hz, 520)).toBeCloseTo(Math.sqrt(0.25), 6)
    expect(toT(lin, -24)).toBeCloseTo(0.5, 6)
  })
  it('snaps to the step without float noise', () => {
    expect(fromT(lin, 0.5)).toBe(-24)
    expect(String(fromT(lin, 0.8))).not.toMatch(/0000|9999/)
  })
  it('wheel up raises, wheel down lowers, and stays in range', () => {
    expect(wheelValue(lin, 0, -100, false)).toBeGreaterThan(0)
    expect(wheelValue(lin, 0, 100, false)).toBeLessThan(0)
    expect(wheelValue(lin, 12, -100, false)).toBe(12)
  })
  it('reads decimals from the step', () => {
    expect(decimalsOf(lin)).toBe(1)
    expect(decimalsOf(hz)).toBe(0)
  })
})
