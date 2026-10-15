// A built-in signal so the page makes sound before anyone loads a file. Deliberately a buzzy synthetic
// tone: a pitch-gliding pulse train through three fixed resonators, gated in bursts. It is not speech.

export const TEST_SIGNAL_SECONDS = 3
const BURST_HZ = 2
const BURST_DUTY = 0.7
const PITCH_LO = 110
const PITCH_HI = 165
const RESONATORS: ReadonlyArray<{ hz: number; q: number }> = [{ hz: 600, q: 6 }, { hz: 1200, q: 8 }, { hz: 2600, q: 10 }]
const PEAK = 0.7

export function makeTestSignal(sampleRate: number, seconds = TEST_SIGNAL_SECONDS): Float32Array {
  const n = Math.round(sampleRate * seconds)
  const pulses = new Float64Array(n)
  let phase = 0
  for (let i = 0; i < n; i++) {
    const t = i / sampleRate
    const f = PITCH_LO + (PITCH_HI - PITCH_LO) * (0.5 - 0.5 * Math.cos((2 * Math.PI * t) / seconds))
    phase += f / sampleRate
    if (phase >= 1) { phase -= 1; pulses[i] = 1 }
  }
  const out = new Float64Array(n)
  for (const { hz, q } of RESONATORS) {
    // Constant-skirt band-pass biquad (RBJ cookbook).
    const w = (2 * Math.PI * hz) / sampleRate
    const alpha = Math.sin(w) / (2 * q)
    const a0 = 1 + alpha
    const b0 = alpha / a0
    const a1 = (-2 * Math.cos(w)) / a0
    const a2 = (1 - alpha) / a0
    let y1 = 0
    let y2 = 0
    let x1 = 0
    let x2 = 0
    for (let i = 0; i < n; i++) {
      const x = pulses[i]
      const y = b0 * x - b0 * x2 - a1 * y1 - a2 * y2
      out[i] += y
      x2 = x1; x1 = x; y2 = y1; y1 = y
    }
  }
  const burst = (i: number) => ((i / sampleRate) * BURST_HZ) % 1 < BURST_DUTY ? 1 : 0
  let peak = 0
  for (let i = 0; i < n; i++) { out[i] *= burst(i); peak = Math.max(peak, Math.abs(out[i])) }
  const g = peak > 0 ? PEAK / peak : 0
  return Float32Array.from(out, (v) => v * g)
}
