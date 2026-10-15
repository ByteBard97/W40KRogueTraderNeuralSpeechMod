/**
 * Read-only window into the pedalboard for the scripted browser suite (e2e/).
 *
 * Why it exists: the page's real state (graph, generated program, engine status, how many times the compiler ran, what the analysers hear)
 * lives inside Vue and Web Audio and cannot be read from the DOM. The hook is installed only in dev builds or when the URL has `?qa`,
 * so a normal visit to the built app has no `window.__pedalboard`. It never changes what the page does: the one wrap (counting compiles)
 * passes every call straight through.
 */
import type { useGraphEngine } from '../composables/useGraphEngine'
import type { usePedalboardStore } from '../stores/pedalboard'
import { BAND_CENTRES, bandPowers, ema, relativeDb, smoothStats, stereoStats, type StereoStats } from '../utils/audioMonitor'

const QA_FLAG = 'qa'
const SAMPLE_MS = 50
const AVG_ALPHA = 0.04
const STAT_ALPHA = 0.1
const MIN_TOTAL_POWER = 1e-9
const SYLLABLE_HZ = 3.5
const NOISE_LEVEL = 0.35
const BUZZ_HZ = 130
const CLIP_PEAK = 0.5

type Store = ReturnType<typeof usePedalboardStore>
type Engine = ReturnType<typeof useGraphEngine>

export interface QaMonitorReading {
  corr: number | null
  sideMidDb: number | null
  balanceDb: number | null
  /** Average band levels in dB with the overall level removed, as the Spectrum panel draws them; empty until sound has been heard. */
  bands: (number | null)[]
  samples: number
}

export interface PedalboardQa {
  graph(): unknown
  compiled(): { code: string; controls: unknown[] } | null
  engineStatus(): { status: string; error: string }
  compileCount(): number
  paramValue(key: string): number | undefined
  monitor(): QaMonitorReading
  selection(): string[]
  loadSyntheticClip(seconds: number): Promise<void>
  loadStarterBySlug(slug: string): boolean
}

declare global {
  interface Window { __pedalboard?: PedalboardQa }
}

export function qaEnabled(dev: boolean, search: string): boolean {
  return dev || new URLSearchParams(search).has(QA_FLAG)
}

/** Voiced-looking noise under a syllable envelope, so spectra and stereo stats have something to measure. Deterministic. */
export function syntheticSpeech(seconds: number, sampleRate: number): Float32Array {
  const n = Math.max(1, Math.round(seconds * sampleRate))
  const out = new Float32Array(n)
  let seed = 12345
  const rand = () => ((seed = (seed * 1664525 + 1013904223) >>> 0) / 4294967296) * 2 - 1
  for (let i = 0; i < n; i++) {
    const t = i / sampleRate
    const env = Math.max(0, Math.sin(2 * Math.PI * SYLLABLE_HZ * t)) ** 2
    let buzz = 0
    for (let k = 1; k <= 10; k++) buzz += Math.sin(2 * Math.PI * BUZZ_HZ * k * t) / k
    out[i] = CLIP_PEAK * env * (0.5 * buzz + NOISE_LEVEL * rand()) / 1.5
  }
  return out
}

export function installPedalboardQaHook(deps: { store: Store; engine: Engine; enabled?: boolean }): () => void {
  const { store, engine } = deps
  const on = deps.enabled ?? qaEnabled(import.meta.env.DEV, window.location.search)
  if (!on) return () => {}

  let compiles = 0
  // The view calls store.compileNow() right before every engine.compile(), and a null result means "nothing to compile", so a non-null
  // result is one compile. Counting here leaves the engine object untouched (view tests give it spies).
  const realCompileNow = store.compileNow
  store.compileNow = () => {
    const c = realCompileNow()
    if (c) compiles++
    return c
  }

  const power = new Float64Array(BAND_CENTRES.length)
  let heard = false
  let stats: StereoStats | null = null
  let samples = 0
  let fbuf: Float32Array | null = null
  let lbuf: Float32Array | null = null
  let rbuf: Float32Array | null = null

  // Own sampler (not the MonitorPanel's) so the page needs no change; it only reads the analysers while a clip is playing.
  function sample() {
    if (!engine.playing.value) return
    const t = engine.taps
    fbuf ??= new Float32Array(t.mid.frequencyBinCount)
    t.mid.getFloatFrequencyData(fbuf)
    const p = bandPowers(fbuf, t.mid.context.sampleRate, t.mid.fftSize)
    if (p.reduce((a, b) => a + b, 0) > MIN_TOTAL_POWER) {
      p.forEach((v, i) => { power[i] = heard ? ema(power[i], v, AVG_ALPHA) : v })
      heard = true
    }
    lbuf ??= new Float32Array(t.left.fftSize)
    rbuf ??= new Float32Array(t.right.fftSize)
    t.left.getFloatTimeDomainData(lbuf)
    t.right.getFloatTimeDomainData(rbuf)
    stats = smoothStats(stats, stereoStats(lbuf, rbuf), STAT_ALPHA)
    samples++
  }
  const timer = setInterval(sample, SAMPLE_MS)

  const hook: PedalboardQa = {
    graph: () => JSON.parse(JSON.stringify(store.graph)),
    compiled: () => (store.compiled ? JSON.parse(JSON.stringify({ code: store.compiled.code, controls: store.compiled.controls })) : null),
    engineStatus: () => ({ status: engine.status.value, error: engine.error.value }),
    compileCount: () => compiles,
    paramValue: (key) => engine.params[key],
    monitor: () => ({
      corr: stats ? stats.corr : null,
      sideMidDb: stats ? stats.sideMidDb : null,
      balanceDb: stats ? stats.balanceDb : null,
      bands: heard ? relativeDb(power) : [],
      samples,
    }),
    selection: () => [...store.selection],
    async loadSyntheticClip(seconds) {
      const ctx = engine.taps.mid.context
      const buf = ctx.createBuffer(1, Math.max(1, Math.round(seconds * ctx.sampleRate)), ctx.sampleRate)
      buf.getChannelData(0).set(syntheticSpeech(seconds, ctx.sampleRate))
      await engine.loadClip(buf)
    },
    loadStarterBySlug: (slug) => store.loadStarter(slug),
  }
  window.__pedalboard = hook

  return () => {
    clearInterval(timer)
    store.compileNow = realCompileNow
    if (window.__pedalboard === hook) delete window.__pedalboard
  }
}
