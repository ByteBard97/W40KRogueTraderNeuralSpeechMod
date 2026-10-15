// @vitest-environment node
// Proves the generated text is valid Faust and behaves: each program is compiled and rendered by
// tools/fx_lab/render_wasm.mjs (FaustWasm under plain Node) and the output levels are checked.
import { mkdtempSync, readFileSync, writeFileSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join, resolve } from 'node:path'
import { spawnSync } from 'node:child_process'
import { describe, expect, it } from 'vitest'
import { generate } from './generate'
import { paramsFor } from './graph'
import { fixtureCatalog as cat, fixtureLib as lib, FIXTURE_DIR, seriesGraph, skipGraph, splitMergeGraph } from './fixtures/testkit'
import type { Graph } from './types'

const RENDER_WASM = resolve(FIXTURE_DIR, '../../../../../fx_lab/render_wasm.mjs')
const SAMPLE_RATE = 48000
const SECONDS = 1
const TONE_HZ = 1000
const TONE_AMP = 0.1
const SETTLE_FRACTION = 0.5 // the smoothers (si.smoo) settle well inside the first half
const COMPILE_TIMEOUT_MS = 120_000
const DB_TOLERANCE = 0.1
const work = mkdtempSync(join(tmpdir(), 'pedalboard-compile-'))

const toneFile = join(work, 'tone.f32')
{
  const n = SAMPLE_RATE * SECONDS
  const x = new Float32Array(n)
  for (let i = 0; i < n; i++) x[i] = TONE_AMP * Math.sin((2 * Math.PI * TONE_HZ * i) / SAMPLE_RATE)
  writeFileSync(toneFile, new Uint8Array(x.buffer))
}

function rms(x: Float32Array): number {
  const from = Math.floor(x.length * SETTLE_FRACTION)
  let s = 0
  for (let i = from; i < x.length; i++) s += x[i] * x[i]
  return Math.sqrt(s / (x.length - from))
}

// Renders the graph with the given param overrides and returns [leftRms, rightRms].
let counter = 0
function render(graph: Graph, overrides: Record<string, number> = {}): [number, number] {
  const id = ++counter
  const dsp = join(work, `g${id}.dsp`)
  const paramsFile = join(work, `p${id}.json`)
  const out = join(work, `o${id}.f32`)
  writeFileSync(dsp, generate(graph, cat, lib).code)
  writeFileSync(paramsFile, JSON.stringify({ ...paramsFor(graph, cat), ...overrides }))
  const r = spawnSync('node', [RENDER_WASM, dsp, toneFile, String(SAMPLE_RATE), paramsFile, out], {
    encoding: 'utf8',
    timeout: COMPILE_TIMEOUT_MS,
  })
  expect(r.status, r.stderr).toBe(0)
  const raw = readFileSync(out)
  const all = new Float32Array(raw.buffer.slice(raw.byteOffset, raw.byteOffset + raw.byteLength))
  const half = all.length / 2
  return [rms(all.subarray(0, half)), rms(all.subarray(half))]
}

const toneRms = (TONE_AMP / Math.SQRT2)
const db = (ratio: number) => 20 * Math.log10(ratio)

describe('generated programs compile and run', () => {
  it('series: two gains at +6 dB each give about +12 dB on both channels', () => {
    const flat = render(seriesGraph())
    for (const ch of flat) expect(db(ch / toneRms)).toBeCloseTo(0, 1)
    const hot = render(seriesGraph(), { n2_Gain_dB: 6, n3_Gain_dB: 6 })
    for (const ch of hot) expect(Math.abs(db(ch / toneRms) - 12)).toBeLessThan(DB_TOLERANCE)
  }, COMPILE_TIMEOUT_MS)

  it('series: the stomp bypasses a gain', () => {
    const off = render(seriesGraph(), { n2_Gain_dB: 6, n2_on: 0 })
    for (const ch of off) expect(db(ch / toneRms)).toBeCloseTo(0, 1)
  }, COMPILE_TIMEOUT_MS)

  it('split/merge: a mix of two branches sums them', () => {
    const both = render(splitMergeGraph())
    for (const ch of both) expect(Math.abs(db(ch / toneRms) - 6.02)).toBeLessThan(DB_TOLERANCE) // x + x
    const lifted = render(splitMergeGraph(), { n2_Gain_dB: 6 })
    // 1.995 + 1 = 2.995
    for (const ch of lifted) expect(Math.abs(ch / toneRms - 2.995)).toBeLessThan(0.02)
    const one = render(splitMergeGraph(), { n4_In_2_dB: -24 })
    for (const ch of one) expect(Math.abs(ch / toneRms - (1 + 0.0631))).toBeLessThan(0.01)
  }, COMPILE_TIMEOUT_MS)

  it('skip connection: the wire that jumps a layer arrives intact', () => {
    // mix = gain branch + raw input; gain +6 dB gives 1.995 + 1
    const [l, r] = render(skipGraph(), { n2_Gain_dB: 6 })
    expect(Math.abs(l / toneRms - 2.995)).toBeLessThan(0.02)
    expect(Math.abs(r / toneRms - 2.995)).toBeLessThan(0.02)
  }, COMPILE_TIMEOUT_MS)
})
