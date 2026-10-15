import { describe, expect, it } from 'vitest'
import { BAND_CENTRES } from '../utils/audioMonitor'
import { analyseReference, averageSpectrumDb, fft, stereoSummary } from './analyse'

const SR = 48000
const sine = (hz: number, seconds = 1, amp = 0.5) => Float32Array.from({ length: SR * seconds }, (_, i) => amp * Math.sin((2 * Math.PI * hz * i) / SR))

describe('fft', () => {
  it('puts a bin-centred sine in exactly its bin', () => {
    const n = 64
    const re = Float64Array.from({ length: n }, (_, i) => Math.cos((2 * Math.PI * 5 * i) / n))
    const im = new Float64Array(n)
    fft(re, im)
    const mag = Array.from(re, (r, i) => Math.hypot(r, im[i]))
    expect(mag.indexOf(Math.max(...mag.slice(0, n / 2)))).toBe(5)
    expect(mag[5]).toBeCloseTo(n / 2, 6)
  })
})

describe('analyseReference', () => {
  it('a 1 kHz sine peaks in the 1 kHz third-octave band', () => {
    const ref = analyseReference('tone', [sine(1000)], SR)
    const vals = ref.db.map((v) => v ?? -Infinity)
    expect(ref.freqs).toEqual(BAND_CENTRES)
    expect(vals.indexOf(Math.max(...vals))).toBe(13)
    expect(ref.stereo).toBeNull()
  })
  it('a 250 Hz sine peaks in the 250 Hz band', () => {
    const ref = analyseReference('tone', [sine(250)], SR)
    const vals = ref.db.map((v) => v ?? -Infinity)
    expect(BAND_CENTRES[vals.indexOf(Math.max(...vals))]).toBeCloseTo(250, 0)
  })
  it('handles a clip shorter than one frame', () => {
    expect(() => averageSpectrumDb(sine(1000, 1).subarray(0, 500))).not.toThrow()
  })
})

describe('stereoSummary', () => {
  const x = sine(440)
  it('identical channels: correlation 1, no side, no level difference', () => {
    const s = stereoSummary(x, x.slice())!
    expect(s.corr).toBeCloseTo(1, 6)
    expect(s.side_mid_db).toBeLessThan(-80)
    expect(s.ild_sd_db).toBeCloseTo(0, 6)
  })
  it('anti-phase channels: correlation -1, side dominates', () => {
    const s = stereoSummary(x, x.map((v) => -v))!
    expect(s.corr).toBeCloseTo(-1, 6)
    expect(s.side_mid_db).toBeGreaterThan(60)
  })
  it('silence and mono give null', () => {
    expect(stereoSummary(new Float32Array(9000), new Float32Array(9000))).toBeNull()
    expect(stereoSummary(x, null)).toBeNull()
  })
})
