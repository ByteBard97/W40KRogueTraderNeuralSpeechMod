import { reactive, ref, type Ref } from 'vue'

/** Structurally identical to the pedalboard generator's Control. */
export interface EngineControl {
  key: string
  type: 'hslider' | 'checkbox'
  init: number
  min: number
  max: number
  step: number
}

export interface FaustDescriptor { type: string; label: string; shortname?: string; address: string; init?: number; min?: number; max?: number; step?: number }
export interface FaustNodeLike {
  getDescriptors(): FaustDescriptor[]
  setParamValue(address: string, value: number): void
  connect(dest: AudioNode): unknown
  disconnect(dest?: AudioNode): unknown
  destroy?(): void
}
export type MakeNode = (ctx: AudioContext, name: string, code: string) => Promise<FaustNodeLike | null>
export interface EngineOptions { ctx?: AudioContext; makeNode?: MakeNode }
export type EngineStatus = 'idle' | 'compiling' | 'ready' | 'error'
export interface EngineTaps { mid: AnalyserNode; left: AnalyserNode; right: AnalyserNode }

export const CROSSFADE_S = 0.05
/** Teardown waits a little past the ramp so the old node is silent when it goes. */
const TEARDOWN_MARGIN_MS = 30
const MID_FFT_SIZE = 8192
const SIDE_FFT_SIZE = 2048
const DEFAULT_GAP_S = 0
const FAUST_MODULE_URL = '/faustwasm/index.js'

/** Parameter key from a Faust control address: the root segment is dropped, the rest joined with underscores. Never the shortname. */
export function keyOfAddress(address: string): string {
  const parts = address.split('/').filter(Boolean)
  return parts.slice(1).join('/').replace(/[^A-Za-z0-9]+/g, '_').replace(/^_+|_+$/g, '')
}

const defaultMakeNode: MakeNode = async (ctx, name, code) => {
  const errs: string[] = []
  const original = console.error
  console.error = (...a: unknown[]) => { errs.push(a.join(' ')); original(...a) }
  try {
    const mod = await import(/* @vite-ignore */ FAUST_MODULE_URL)
    return (await new mod.FaustDspGenerator().createFaustNode(ctx, name, code)) as FaustNodeLike | null
  } catch (e) {
    throw new Error([...errs, String(e)].join('\n'))
  } finally {
    console.error = original
  }
}

interface Live { node: FaustNodeLike; gain: GainNode; addresses: Map<string, string> }

export function useGraphEngine(options: EngineOptions = {}) {
  const ownsCtx = !options.ctx
  const ctx = options.ctx ?? new AudioContext({ latencyHint: 'interactive' })
  const makeNode = options.makeNode ?? defaultMakeNode

  const status = ref<EngineStatus>('idle')
  const error = ref('')
  const playing = ref(false)
  const bypassRaw = ref(false)
  const params = reactive<Record<string, number>>({})

  const dry = ctx.createGain()
  const wet = ctx.createGain()
  const out = ctx.createGain()
  dry.connect(out)
  wet.connect(out)
  out.connect(ctx.destination)
  dry.gain.value = 0
  const mid = ctx.createAnalyser()
  mid.fftSize = MID_FFT_SIZE
  mid.smoothingTimeConstant = 0
  const split = ctx.createChannelSplitter(2)
  const left = ctx.createAnalyser()
  const right = ctx.createAnalyser()
  left.fftSize = SIDE_FFT_SIZE
  right.fftSize = SIDE_FFT_SIZE
  out.connect(mid)
  out.connect(split)
  split.connect(left, 0)
  split.connect(right, 1)
  const taps: EngineTaps = { mid, left, right }

  let live: Live | null = null
  let controls = new Map<string, EngineControl>()
  let seq = 0
  let raw: AudioBuffer | null = null
  let buf: AudioBuffer | null = null
  let src: AudioBufferSourceNode | null = null
  let gapS = DEFAULT_GAP_S
  let disposed = false

  const initOf = (c: EngineControl) => (c.type === 'checkbox' ? (Number.isFinite(c.init) ? c.init : 1) : c.init)
  const clamp = (c: EngineControl, v: number) => Math.min(c.max, Math.max(c.min, v))

  function teardown(l: Live) {
    try { src?.disconnect(l.node as unknown as AudioNode) } catch { /* not connected */ }
    try { l.node.disconnect() } catch { /* already gone */ }
    try { l.gain.disconnect() } catch { /* already gone */ }
    try { l.node.destroy?.() } catch { /* optional */ }
  }

  async function compile(code: string, ctrls: EngineControl[], wanted: Record<string, number>): Promise<void> {
    const my = ++seq
    status.value = 'compiling'
    error.value = ''
    let node: FaustNodeLike | null = null
    let failure = ''
    try {
      node = await makeNode(ctx, `fx${my}`, code)
      if (!node) failure = 'Compile failed (no details from the compiler)'
    } catch (e) {
      failure = e instanceof Error ? e.message : String(e)
    }
    if (my !== seq || disposed) {
      if (node) { try { node.disconnect() } catch { /* unused */ } try { node.destroy?.() } catch { /* optional */ } }
      return
    }
    if (!node) {
      status.value = 'error'
      error.value = failure
      return
    }

    const addresses = new Map<string, string>()
    for (const d of node.getDescriptors()) addresses.set(keyOfAddress(d.address), d.address)
    const next = new Map<string, EngineControl>()
    const values: Record<string, number> = {}
    for (const c of ctrls) {
      const address = addresses.get(c.key)
      if (!address) continue
      next.set(c.key, c)
      const v = c.key in wanted ? wanted[c.key] : c.key in params ? params[c.key] : initOf(c)
      values[c.key] = clamp(c, v)
      node.setParamValue(address, values[c.key])
    }

    const gain = ctx.createGain()
    node.connect(gain as unknown as AudioNode)
    gain.connect(wet)
    if (src) src.connect(node as unknown as AudioNode)
    const old = live
    live = { node, gain, addresses }
    controls = next
    for (const k of Object.keys(params)) delete params[k]
    Object.assign(params, values)

    if (old) {
      const t = ctx.currentTime
      gain.gain.setValueAtTime(0, t)
      gain.gain.linearRampToValueAtTime(1, t + CROSSFADE_S)
      old.gain.gain.setValueAtTime(1, t)
      old.gain.gain.linearRampToValueAtTime(0, t + CROSSFADE_S)
      setTimeout(() => teardown(old), CROSSFADE_S * 1000 + TEARDOWN_MARGIN_MS)
    }
    status.value = 'ready'
  }

  function setParam(key: string, value: number): void {
    const c = controls.get(key)
    const address = live?.addresses.get(key)
    if (!c || !live || !address) return
    const v = clamp(c, value)
    params[key] = v
    live.node.setParamValue(address, v)
  }

  function rebuildBuffer() {
    if (!raw) return
    const sr = raw.sampleRate
    const gap = Math.round(gapS * sr)
    const x = raw.getChannelData(0)
    const b = ctx.createBuffer(1, x.length + gap, sr)
    b.getChannelData(0).set(x)
    buf = b
    if (src) startSource()
  }

  async function loadClip(input: AudioBuffer | ArrayBuffer): Promise<void> {
    raw = input instanceof ArrayBuffer ? await ctx.decodeAudioData(input) : input
    rebuildBuffer()
  }

  function startSource() {
    stopSource()
    if (!buf) return
    const s = ctx.createBufferSource()
    s.buffer = buf
    s.loop = true
    s.connect(dry)
    if (live) s.connect(live.node as unknown as AudioNode)
    s.start()
    src = s
    playing.value = true
  }

  function stopSource() {
    if (src) {
      try { src.stop() } catch { /* never started */ }
      src.disconnect()
      src = null
    }
    playing.value = false
  }

  function play() {
    ctx.resume?.().catch?.(() => {})
    startSource()
  }
  const stop = stopSource

  function setBypassRaw(b: boolean) {
    bypassRaw.value = b
    dry.gain.value = b ? 1 : 0
    wet.gain.value = b ? 0 : 1
  }

  function setGap(seconds: number) {
    gapS = Math.max(0, seconds)
    rebuildBuffer()
  }

  function dispose() {
    disposed = true
    seq++
    stopSource()
    if (live) { teardown(live); live = null }
    for (const n of [dry, wet, out, split, mid, left, right]) { try { n.disconnect() } catch { /* ok */ } }
    if (ownsCtx) void ctx.close?.()
  }

  return { status, error, playing, bypassRaw, params, compile, setParam, loadClip, play, stop, setBypassRaw, setGap, taps, dispose } as {
    status: Ref<EngineStatus>; error: Ref<string>; playing: Ref<boolean>; bypassRaw: Ref<boolean>; params: Record<string, number>
    compile: typeof compile; setParam: typeof setParam; loadClip: typeof loadClip; play: typeof play; stop: typeof stop
    setBypassRaw: typeof setBypassRaw; setGap: typeof setGap; taps: EngineTaps; dispose: typeof dispose
  }
}
