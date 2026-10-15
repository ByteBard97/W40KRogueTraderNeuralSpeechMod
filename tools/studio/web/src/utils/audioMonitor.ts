/** Pure maths for the pedalboard monitor: third-octave band power, level-free spectrum, stereo statistics. */

const BAND_COUNT = 25
const THIRD_OCTAVE_STEPS = 3
const CENTRE_INDEX_OF_1K = 13
/** Half a third-octave step, as a frequency ratio: the band edges sit at centre / EDGE and centre * EDGE. */
const BAND_EDGE = 2 ** (1 / 6)
export const LEVEL_LO_HZ = 100
export const LEVEL_HI_HZ = 8000
const SILENT_ENERGY = 1e-6
const EPS = 1e-12
const SIDE_MID_EPS = 1e-9

export const BAND_CENTRES: number[] = Array.from({ length: BAND_COUNT }, (_, k) => 1000 * 2 ** ((k - CENTRE_INDEX_OF_1K) / THIRD_OCTAVE_STEPS))

export interface StereoStats { corr: number; sideMidDb: number; balanceDb: number }

/** Mean power per band from an AnalyserNode dB array (getFloatFrequencyData). */
export function bandPowers(fftDb: Float32Array, sampleRate: number, fftSize: number): Float64Array {
  const hzPerBin = sampleRate / fftSize
  const out = new Float64Array(BAND_CENTRES.length)
  BAND_CENTRES.forEach((c, i) => {
    const lo = Math.ceil(c / BAND_EDGE / hzPerBin)
    const hi = Math.floor((c * BAND_EDGE) / hzPerBin)
    let sum = 0
    let n = 0
    for (let k = lo; k <= hi && k < fftDb.length; k++) {
      const db = fftDb[k]
      if (!Number.isFinite(db)) continue
      sum += 10 ** (db / 10)
      n++
    }
    out[i] = n ? sum / n : 0
  })
  return out
}

/** Band levels in dB with the overall level removed: the mean of the bands inside 100..8000 Hz is 0 dB. */
export function relativeDb(power: ArrayLike<number>): (number | null)[] {
  const db = Array.from(power, (v) => (v > 0 ? 10 * Math.log10(v) : null))
  const inside = db.filter((v, i): v is number => v !== null && BAND_CENTRES[i] >= LEVEL_LO_HZ && BAND_CENTRES[i] <= LEVEL_HI_HZ)
  const mean = inside.reduce((a, b) => a + b, 0) / Math.max(1, inside.length)
  return db.map((v) => (v === null ? null : v - mean))
}

/** Exponential moving average; a null previous value takes the new one outright. */
export function ema(prev: number | null, next: number, alpha: number): number {
  return prev === null ? next : prev * (1 - alpha) + next * alpha
}

/** L/R correlation, side/mid and balance in dB of one block of samples; null when it is silent. */
export function stereoStats(left: Float32Array, right: Float32Array): StereoStats | null {
  let ll = 0, rr = 0, lr = 0, ss = 0, mm = 0
  const n = Math.min(left.length, right.length)
  for (let i = 0; i < n; i++) {
    const l = left[i]
    const r = right[i]
    ll += l * l
    rr += r * r
    lr += l * r
    ss += ((l - r) / 2) ** 2
    mm += ((l + r) / 2) ** 2
  }
  if (ll + rr < SILENT_ENERGY) return null
  return {
    corr: lr / Math.sqrt(ll * rr + EPS),
    sideMidDb: 10 * Math.log10(ss / (mm + EPS) + SIDE_MID_EPS),
    balanceDb: 10 * Math.log10((ll + EPS) / (rr + EPS)),
  }
}

/** Smooth a stream of stereo readings; a null reading keeps the previous value. */
export function smoothStats(prev: StereoStats | null, next: StereoStats | null, alpha: number): StereoStats | null {
  if (!next) return prev
  return {
    corr: ema(prev ? prev.corr : null, next.corr, alpha),
    sideMidDb: ema(prev ? prev.sideMidDb : null, next.sideMidDb, alpha),
    balanceDb: ema(prev ? prev.balanceDb : null, next.balanceDb, alpha),
  }
}
