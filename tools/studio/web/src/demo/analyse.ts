// Average spectrum and stereo statistics of a decoded clip, in the shape the server sends for a game voice
// (ReferenceData), so MonitorPanel draws a user's own reference exactly like a built-in one.
import type { ReferenceData, ReferenceStereo } from '../api/referenceApi'
import { BAND_CENTRES, bandPowers, relativeDb, stereoStats } from '../utils/audioMonitor'

export const FFT_SIZE = 8192
/** Long clips are sampled at an even stride: the average of 400 frames is already stable and keeps the page responsive. */
const MAX_FRAMES = 400
const BLOCK = 4096
const FLOOR_POWER = 1e-20

/** In-place iterative radix-2 FFT; re and im must have the same power-of-two length. */
export function fft(re: Float64Array, im: Float64Array): void {
  const n = re.length
  for (let i = 1, j = 0; i < n; i++) {
    let bit = n >> 1
    for (; j & bit; bit >>= 1) j ^= bit
    j ^= bit
    if (i < j) { [re[i], re[j]] = [re[j], re[i]]; [im[i], im[j]] = [im[j], im[i]] }
  }
  for (let len = 2; len <= n; len <<= 1) {
    const ang = (-2 * Math.PI) / len
    const wr = Math.cos(ang)
    const wi = Math.sin(ang)
    for (let i = 0; i < n; i += len) {
      let cr = 1
      let ci = 0
      for (let k = 0; k < len / 2; k++) {
        const a = i + k
        const b = a + len / 2
        const tr = re[b] * cr - im[b] * ci
        const ti = re[b] * ci + im[b] * cr
        re[b] = re[a] - tr; im[b] = im[a] - ti
        re[a] += tr; im[a] += ti
        const nr = cr * wr - ci * wi
        ci = cr * wi + ci * wr
        cr = nr
      }
    }
  }
}

/** Mean power per FFT bin (Hann window, 50% overlap), returned in dB the way AnalyserNode reports it. */
export function averageSpectrumDb(samples: Float32Array, size = FFT_SIZE): Float32Array {
  const bins = size / 2
  const hann = Float64Array.from({ length: size }, (_, i) => 0.5 - 0.5 * Math.cos((2 * Math.PI * i) / size))
  const hop = size / 2
  const total = samples.length >= size ? Math.floor((samples.length - size) / hop) + 1 : 1
  const stride = Math.max(1, Math.ceil(total / MAX_FRAMES))
  const acc = new Float64Array(bins)
  const re = new Float64Array(size)
  const im = new Float64Array(size)
  let frames = 0
  for (let f = 0; f < total; f += stride) {
    const start = f * hop
    for (let i = 0; i < size; i++) { re[i] = (samples[start + i] ?? 0) * hann[i]; im[i] = 0 }
    fft(re, im)
    // Normalised so a full-scale sine reads about 0 dB; only the shape matters after relativeDb.
    for (let k = 0; k < bins; k++) acc[k] += (re[k] * re[k] + im[k] * im[k]) / (size * size)
    frames++
  }
  return Float32Array.from(acc, (p) => 10 * Math.log10(p / frames + FLOOR_POWER))
}

/** Correlation, side/mid and level-difference spread over 4096-sample blocks; null for a mono or silent clip. */
export function stereoSummary(left: Float32Array, right: Float32Array | null): ReferenceStereo | null {
  if (!right) return null
  const whole = stereoStats(left, right)
  if (!whole) return null
  const balances: number[] = []
  for (let s = 0; s + BLOCK <= Math.min(left.length, right.length); s += BLOCK) {
    const st = stereoStats(left.subarray(s, s + BLOCK), right.subarray(s, s + BLOCK))
    if (st) balances.push(st.balanceDb)
  }
  const mean = balances.reduce((a, b) => a + b, 0) / Math.max(1, balances.length)
  const sd = Math.sqrt(balances.reduce((a, b) => a + (b - mean) ** 2, 0) / Math.max(1, balances.length))
  return { corr: whole.corr, side_mid_db: whole.sideMidDb, ild_sd_db: sd, clips: 1 }
}

/** Channels may be one (mono) or two; extra channels are ignored. */
export function analyseReference(name: string, channels: Float32Array[], sampleRate: number): ReferenceData {
  const mono = channels.length > 1 ? channels[0].map((v, i) => (v + channels[1][i]) / 2) : channels[0]
  const db = relativeDb(bandPowers(averageSpectrumDb(mono), sampleRate, FFT_SIZE))
  return { speaker: name, freqs: [...BAND_CENTRES], db, clips_used: 1, stereo: stereoSummary(channels[0], channels[1] ?? null) }
}
