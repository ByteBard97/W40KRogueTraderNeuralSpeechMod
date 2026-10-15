import { describe, expect, it } from 'vitest'
import { BAND_CENTRES, bandPowers, ema, relativeDb, smoothStats, stereoStats } from './audioMonitor'

const SR = 48000
const FFT = 8192
const bins = FFT / 2

describe('BAND_CENTRES', () => {
  it('spans 50 Hz to 12.7 kHz in 25 bands', () => {
    expect(BAND_CENTRES).toHaveLength(25)
    expect(BAND_CENTRES[0]).toBeCloseTo(50, 0)
    expect(BAND_CENTRES[24]).toBeCloseTo(12699, -1)
    expect(BAND_CENTRES[13]).toBeCloseTo(1000, 6)
  })
})

describe('bandPowers and relativeDb', () => {
  it('a flat spectrum is flat in relative dB', () => {
    const rel = relativeDb(bandPowers(new Float32Array(bins).fill(-60), SR, FFT))
    for (const v of rel) if (v !== null) expect(v).toBeCloseTo(0, 6)
  })
  it('one raised band stands out', () => {
    const fft = new Float32Array(bins).fill(-60)
    const hz = SR / FFT
    for (let k = Math.round(900 / hz); k <= Math.round(1100 / hz); k++) fft[k] = -40
    const rel = relativeDb(bandPowers(fft, SR, FFT))
    expect(rel[13]!).toBeGreaterThan(15)
    expect(rel[10]!).toBeLessThan(1)
  })
  it('bands with no bins or no energy are null', () => {
    const rel = relativeDb(new Float64Array(BAND_CENTRES.length))
    expect(rel.every((v) => v === null)).toBe(true)
  })
})

describe('ema', () => {
  it('starts from the first value then blends', () => {
    expect(ema(null, 4, 0.1)).toBe(4)
    expect(ema(4, 8, 0.25)).toBeCloseTo(5)
  })
})

const sine = (n: number, g = 1) => Float32Array.from({ length: n }, (_, i) => g * Math.sin(i / 5))

describe('stereoStats', () => {
  it('identical channels: correlation 1, side/mid very low, balance 0', () => {
    const x = sine(512)
    const s = stereoStats(x, x)!
    expect(s.corr).toBeCloseTo(1, 3)
    expect(s.sideMidDb).toBeLessThan(-50)
    expect(s.balanceDb).toBeCloseTo(0, 3)
  })
  it('anti-phase gives correlation -1', () => {
    const x = sine(512)
    expect(stereoStats(x, x.map((v) => -v))!.corr).toBeCloseTo(-1, 3)
  })
  it('left only has a large positive balance', () => {
    expect(stereoStats(sine(512), new Float32Array(512))!.balanceDb).toBeGreaterThan(50)
  })
  it('silence is null', () => {
    expect(stereoStats(new Float32Array(512), new Float32Array(512))).toBeNull()
  })
})

describe('smoothStats', () => {
  it('keeps previous on null, adopts first reading, blends after', () => {
    const a = { corr: 1, sideMidDb: -20, balanceDb: 0 }
    expect(smoothStats(null, null, 0.1)).toBeNull()
    expect(smoothStats(a, null, 0.1)).toBe(a)
    expect(smoothStats(null, a, 0.1)).toEqual(a)
    expect(smoothStats(a, { corr: 0, sideMidDb: -10, balanceDb: 10 }, 0.5)).toEqual({ corr: 0.5, sideMidDb: -15, balanceDb: 5 })
  })
})
