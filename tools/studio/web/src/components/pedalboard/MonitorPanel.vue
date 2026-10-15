<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref, watch } from 'vue'
import type { ReferenceData } from '../../api/referenceApi'
import type { EngineTaps } from '../../composables/useGraphEngine'
import { BAND_CENTRES, bandPowers, ema, relativeDb, smoothStats, stereoStats, type StereoStats } from '../../utils/audioMonitor'

const props = defineProps<{ taps: EngineTaps | null; reference: ReferenceData | null; running: boolean }>()

const F_MIN = 40
const F_MAX = 14000
const Y_RANGE = 36
const AVG_ALPHA = 0.04
const STAT_ALPHA = 0.1
const MIN_TOTAL_POWER = 1e-9
const GRID_FREQS = [100, 1000, 10000]
const GRID_DB = [-24, -12, 0, 12, 24]
const PAD_L = 28
const PAD_R = 8
const PAD_T = 6
const PAD_B = 18
const SCOPE_GAIN = 1.6
const SCOPE_RADIUS = 0.46
const DOT = 2
const LINE_W = 2
const DASH = [6, 4]

const spec = ref<HTMLCanvasElement | null>(null)
const scope = ref<HTMLCanvasElement | null>(null)
const stats = ref<StereoStats | null>(null)
const power = new Float64Array(BAND_CENTRES.length)
let seen = false
let raf = 0
let fbuf: Float32Array | null = null
let lbuf: Float32Array | null = null
let rbuf: Float32Array | null = null

const token = (n: string) => getComputedStyle(document.documentElement).getPropertyValue(n).trim()
const fmt = (v: number | null | undefined, d: number) => (v === null || v === undefined ? '-' : v.toFixed(d))
const refCorr = () => (props.reference ? (props.reference.stereo ? fmt(props.reference.stereo.corr, 2) : 'mono') : '-')
const refWidth = () => (props.reference ? (props.reference.stereo ? fmt(props.reference.stereo.side_mid_db, 1) : 'mono') : '-')

function sizeCanvas(cv: HTMLCanvasElement, square: boolean) {
  const dpr = window.devicePixelRatio || 1
  cv.width = Math.max(1, cv.clientWidth * dpr)
  cv.height = square ? cv.width : Math.max(1, cv.clientHeight * dpr)
  return dpr
}

function drawSpectrum() {
  const cv = spec.value
  const g = cv?.getContext?.('2d')
  if (!cv || !g) return
  const dpr = sizeCanvas(cv, false)
  const W = cv.width
  const H = cv.height
  const x0 = PAD_L * dpr
  const X = (f: number) => x0 + (W - (PAD_L + PAD_R) * dpr) * (Math.log(f / F_MIN) / Math.log(F_MAX / F_MIN))
  const Y = (d: number) => H - PAD_B * dpr - (H - (PAD_B + PAD_T) * dpr) * ((d + Y_RANGE) / (2 * Y_RANGE))
  g.clearRect(0, 0, W, H)
  g.font = `${11 * dpr}px ${token('--font-mono')}`
  g.fillStyle = token('--text-3')
  g.strokeStyle = token('--line')
  g.lineWidth = 1
  for (const f of GRID_FREQS) {
    g.beginPath(); g.moveTo(X(f), PAD_T * dpr); g.lineTo(X(f), H - PAD_B * dpr); g.stroke()
    g.fillText(f >= 1000 ? `${f / 1000}k` : String(f), X(f) - 8 * dpr, H - 4 * dpr)
  }
  for (const d of GRID_DB) {
    g.beginPath(); g.moveTo(x0, Y(d)); g.lineTo(W - PAD_R * dpr, Y(d)); g.stroke()
    g.fillText(String(d), 2, Y(d) + 4 * dpr)
  }
  const line = (freqs: number[], vals: (number | null)[], color: string, dashed: boolean) => {
    g.beginPath(); g.setLineDash(dashed ? DASH.map((v) => v * dpr) : []); g.strokeStyle = color; g.lineWidth = LINE_W * dpr
    let on = false
    vals.forEach((v, i) => {
      if (v === null || v === undefined) { on = false; return }
      const x = X(freqs[i])
      const y = Y(Math.max(-Y_RANGE, Math.min(Y_RANGE, v)))
      if (on) g.lineTo(x, y); else g.moveTo(x, y)
      on = true
    })
    g.stroke(); g.setLineDash([])
  }
  if (props.reference) line(props.reference.freqs, props.reference.db, token('--text-3'), true)
  if (seen) line(BAND_CENTRES, relativeDb(power), token('--accent'), false)
}

function drawScope() {
  const cv = scope.value
  const g = cv?.getContext?.('2d')
  if (!cv || !g) return
  const dpr = sizeCanvas(cv, true)
  const S = cv.width
  g.clearRect(0, 0, S, S)
  g.strokeStyle = token('--line'); g.lineWidth = 1
  g.beginPath(); g.moveTo(S / 2, 4); g.lineTo(S / 2, S - 4); g.moveTo(4, S / 2); g.lineTo(S - 4, S / 2); g.stroke()
  g.fillStyle = token('--text-3'); g.font = `${10 * dpr}px ${token('--font-mono')}`
  g.fillText('mono', S / 2 + 4, 12 * dpr); g.fillText('L', 6, S / 2 - 4); g.fillText('R', S - 14 * dpr, S / 2 - 4)
  if (!lbuf || !rbuf) return
  g.fillStyle = token('--accent'); g.globalAlpha = 0.5
  const r = S * SCOPE_RADIUS * SCOPE_GAIN
  for (let i = 0; i < lbuf.length; i += 2) {
    const x = (rbuf[i] - lbuf[i]) / Math.SQRT2
    const y = (rbuf[i] + lbuf[i]) / Math.SQRT2
    g.fillRect(S / 2 + x * r, S / 2 - y * r, DOT * dpr, DOT * dpr)
  }
  g.globalAlpha = 1
}

function sample() {
  const t = props.taps
  if (!t) return
  fbuf ??= new Float32Array(t.mid.frequencyBinCount)
  t.mid.getFloatFrequencyData(fbuf)
  const p = bandPowers(fbuf, t.mid.context.sampleRate, t.mid.fftSize)
  if (p.reduce((a, b) => a + b, 0) > MIN_TOTAL_POWER) {
    p.forEach((v, i) => { power[i] = seen ? ema(power[i], v, AVG_ALPHA) : v })
    seen = true
  }
  lbuf ??= new Float32Array(t.left.fftSize)
  rbuf ??= new Float32Array(t.right.fftSize)
  t.left.getFloatTimeDomainData(lbuf)
  t.right.getFloatTimeDomainData(rbuf)
  stats.value = smoothStats(stats.value, stereoStats(lbuf, rbuf), STAT_ALPHA)
}

function tick() {
  sample()
  drawSpectrum()
  drawScope()
  raf = props.running ? requestAnimationFrame(tick) : 0
}
function startLoop() { if (props.running && !raf) raf = requestAnimationFrame(tick) }
function stopLoop() { if (raf) cancelAnimationFrame(raf); raf = 0 }

function resetAverage() {
  power.fill(0)
  seen = false
  stats.value = null
  drawSpectrum()
}

watch(() => props.running, (r) => (r ? startLoop() : stopLoop()))
watch(() => props.reference, drawSpectrum)
let resizer: ResizeObserver | null = null
onMounted(() => {
  startLoop()
  drawSpectrum(); drawScope()
  if (typeof ResizeObserver !== 'undefined' && spec.value) {
    resizer = new ResizeObserver(() => { drawSpectrum(); drawScope() })
    resizer.observe(spec.value)
  }
})
onBeforeUnmount(() => { stopLoop(); resizer?.disconnect() })
defineExpose({ stats, resetAverage })
</script>

<template>
  <section class="monitor" aria-label="Monitor">
    <div class="card">
      <header>
        <h3>Spectrum</h3>
        <button type="button" class="reset" data-test="reset" @click="resetAverage">Reset average</button>
      </header>
      <canvas ref="spec" class="spec" />
      <div class="legend">
        <span class="mine"><i />your processed clip, averaged</span>
        <span class="game"><i />game voice{{ reference ? `, ${reference.speaker}` : '' }}, averaged</span>
      </div>
    </div>
    <div class="card">
      <header><h3>Stereo</h3></header>
      <canvas ref="scope" class="scope" />
      <div class="stats" data-test="stats">
        <span class="h" /><span class="h n">yours</span><span class="h n">game</span>
        <span>L/R correlation</span><span class="n" data-test="st-corr">{{ fmt(stats?.corr, 2) }}</span><span class="n" data-test="rf-corr">{{ refCorr() }}</span>
        <span>side / mid dB</span><span class="n" data-test="st-width">{{ fmt(stats?.sideMidDb, 1) }}</span><span class="n" data-test="rf-width">{{ refWidth() }}</span>
        <span>balance dB</span><span class="n" data-test="st-bal">{{ fmt(stats?.balanceDb, 1) }}</span><span class="n" />
      </div>
    </div>
  </section>
</template>

<style scoped>
.monitor { display: grid; grid-template-columns: minmax(0, 2fr) minmax(220px, 1fr); gap: var(--s-4); }
@media (max-width: 900px) { .monitor { grid-template-columns: 1fr; } }
.card { background: var(--surface); border: 1px solid var(--line); border-radius: var(--r-md); padding: var(--s-3); }
header { display: flex; align-items: center; justify-content: space-between; margin-bottom: var(--s-2); }
h3 { margin: 0; font-size: var(--fs-md); color: var(--text-2); font-weight: 600; }
.reset { background: var(--raised); color: var(--text-2); border: 1px solid var(--line-strong); border-radius: var(--r-sm); padding: 2px var(--s-2); font-size: var(--fs-sm); cursor: pointer; }
.reset:hover { background: var(--hover); }
canvas { display: block; width: 100%; background: var(--inset); border-radius: var(--r-sm); }
.spec { height: 170px; }
.scope { aspect-ratio: 1; max-width: 200px; margin: 0 auto; }
.legend { display: flex; gap: var(--s-4); margin-top: var(--s-2); font-size: var(--fs-sm); }
.legend i { display: inline-block; width: 18px; border-top: 2px solid currentColor; margin-right: var(--s-1); vertical-align: middle; }
.mine { color: var(--accent); }
.game { color: var(--text-3); }
.game i { border-top-style: dashed; }
.stats { display: grid; grid-template-columns: 1fr auto auto; gap: var(--s-1) var(--s-3); margin-top: var(--s-3); font-size: var(--fs-sm); color: var(--text-2); }
.h { color: var(--text-3); }
.n { text-align: right; font-family: var(--font-mono); }
</style>
