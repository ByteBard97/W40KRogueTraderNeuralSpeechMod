/* Voice FX chain, browser + node. The python mirror is fx.py: keep the two in lockstep, the parity test
 * (tests/test_fx_parity.py) runs both on the same signal.
 *
 * fx = {hp, lp, drive, crush:{bits,hold}, ring:{hz,mix}, trem:{hz,depth}, chorus:{ms,hz,mix}, echo:{ms,fb,mix}, rrev:{decay,mix}}
 * Order: highpass -> lowpass -> drive -> bitcrush -> ring mod -> tremolo -> chorus -> echo -> reverse reverb -> peak limit.
 * mix is the wet/dry blend of the whole chain (1 = fully processed, 0 = original). The original is lined up with
 * where it sits in the processed signal (reverse reverb shifts it right by its tail).
 * Speed is not here: it is a time-stretch (browser playbackRate with preservesPitch, ffmpeg atempo in
 * production), applied after this chain in both.
 */
(function (root) {
  const DEFAULT_FX = {
    mix: 1, hp: 0, lp: 0, drive: 0,
    crush: { bits: 16, hold: 1 },
    ring: { hz: 0, mix: 0 },
    trem: { hz: 0, depth: 0 },
    chorus: { ms: 0, hz: 0.8, mix: 0 },
    echo: { ms: 0, fb: 0, mix: 0 },
    rrev: { decay: 0, mix: 0 },
  };
  const PEAK = 0.98;
  const CHORUS_BASE_MS = [15, 20, 25], CHORUS_RATE = [1, 1.17, 0.83];
  const MAX_TAIL_S = 1.5;

  function withDefaults(fx) {
    const d = JSON.parse(JSON.stringify(DEFAULT_FX));
    for (const k of Object.keys(fx || {})) {
      if (typeof d[k] === 'object') Object.assign(d[k], fx[k]); else d[k] = fx[k];
    }
    return d;
  }

  // RBJ cookbook biquad, Q = 1/sqrt(2); direct form I, same coefficients as fx.py
  function biquad(x, sr, kind, f0) {
    const w0 = 2 * Math.PI * f0 / sr, cos = Math.cos(w0), alpha = Math.sin(w0) / (2 * Math.SQRT1_2);
    let b0, b1, b2;
    if (kind === 'lp') { b0 = (1 - cos) / 2; b1 = 1 - cos; b2 = (1 - cos) / 2; }
    else { b0 = (1 + cos) / 2; b1 = -(1 + cos); b2 = (1 + cos) / 2; }
    const a0 = 1 + alpha, a1 = -2 * cos, a2 = 1 - alpha;
    const B0 = b0 / a0, B1 = b1 / a0, B2 = b2 / a0, A1 = a1 / a0, A2 = a2 / a0;
    const y = new Float64Array(x.length);
    let x1 = 0, x2 = 0, y1 = 0, y2 = 0;
    for (let n = 0; n < x.length; n++) {
      const v = B0 * x[n] + B1 * x1 + B2 * x2 - A1 * y1 - A2 * y2;
      x2 = x1; x1 = x[n]; y2 = y1; y1 = v; y[n] = v;
    }
    return y;
  }

  // Schroeder reverb (4 feedback combs in parallel, 2 allpasses), RT60 = decay seconds. Delays in ms.
  const COMB_MS = [29.7, 37.1, 41.1, 43.7], AP_MS = [5.0, 1.7], AP_G = 0.7;
  function schroeder(x, sr, decay) {
    const n = x.length, wet = new Float64Array(n);
    for (const ms of COMB_MS) {
      const D = Math.max(1, Math.round(ms * sr / 1000)), g = Math.pow(10, -3 * (ms / 1000) / decay);
      const y = new Float64Array(n);
      for (let i = 0; i < n; i++) { y[i] = x[i] + (i >= D ? g * y[i - D] : 0); wet[i] += y[i] / COMB_MS.length; }
    }
    let cur = wet;
    for (const ms of AP_MS) {
      const D = Math.max(1, Math.round(ms * sr / 1000)), y = new Float64Array(n);
      for (let i = 0; i < n; i++) y[i] = -AP_G * cur[i] + (i >= D ? cur[i - D] + AP_G * y[i - D] : 0);
      cur = y;
    }
    return cur;
  }
  // reverse -> reverb -> reverse: the swell arrives BEFORE each sound. The dry signal is shifted right by
  // the tail length so the swell before the first word has room.
  function reverseReverb(x, sr, decay, mix) {
    const tail = Math.min(Math.floor(MAX_TAIL_S * sr), Math.round(decay * sr));
    const n = x.length, r = new Float64Array(n + tail);
    for (let i = 0; i < n; i++) r[i] = x[n - 1 - i];
    const w = schroeder(r, sr, decay), y = new Float64Array(n + tail);
    for (let i = 0; i < n + tail; i++) y[i] = (i >= tail ? x[i - tail] : 0) + mix * w[n + tail - 1 - i];
    return y;
  }

  function applyFx(input, sr, fxIn) {
    const fx = withDefaults(fxIn);
    let x = Float64Array.from(input);
    const orig = Float64Array.from(input);  // untouched copy for the wet/dry blend (x is edited in place below)
    let lead = 0;
    if (fx.hp > 0) x = biquad(x, sr, 'hp', fx.hp);
    if (fx.lp > 0) x = biquad(x, sr, 'lp', fx.lp);
    if (fx.drive > 0) {
      const k = 1 + fx.drive * 9, t = Math.tanh(k);
      for (let n = 0; n < x.length; n++) x[n] = Math.tanh(k * x[n]) / t;
    }
    if (fx.crush.bits < 16 || fx.crush.hold > 1) {
      const lv = Math.pow(2, fx.crush.bits - 1) - 1, hold = Math.max(1, Math.round(fx.crush.hold));
      const y = new Float64Array(x.length);
      for (let n = 0; n < x.length; n++) {
        const v = x[Math.floor(n / hold) * hold];
        y[n] = fx.crush.bits < 16 ? Math.round(v * lv) / lv : v;
      }
      x = y;
    }
    if (fx.ring.hz > 0 && fx.ring.mix > 0) {
      for (let n = 0; n < x.length; n++) {
        const m = Math.sin(2 * Math.PI * fx.ring.hz * n / sr);
        x[n] = (1 - fx.ring.mix) * x[n] + fx.ring.mix * x[n] * m;
      }
    }
    if (fx.trem.hz > 0 && fx.trem.depth > 0) {
      for (let n = 0; n < x.length; n++) {
        const lfo = 0.5 + 0.5 * Math.sin(2 * Math.PI * fx.trem.hz * n / sr);
        x[n] *= 1 - fx.trem.depth + fx.trem.depth * lfo;
      }
    }
    if (fx.chorus.ms > 0 && fx.chorus.mix > 0) {
      const N = x.length, wet = new Float64Array(N);
      for (let v = 0; v < CHORUS_BASE_MS.length; v++) {
        for (let n = 0; n < N; n++) {
          const d = (CHORUS_BASE_MS[v] + fx.chorus.ms * Math.sin(2 * Math.PI * fx.chorus.hz * CHORUS_RATE[v] * n / sr + 2 * Math.PI * v / 3)) * sr / 1000;
          const p = n - d, i0 = Math.floor(p), f = p - i0;
          const a = i0 >= 0 && i0 < N ? x[i0] : 0, b = i0 + 1 >= 0 && i0 + 1 < N ? x[i0 + 1] : 0;
          wet[n] += ((1 - f) * a + f * b) / CHORUS_BASE_MS.length;
        }
      }
      const y = new Float64Array(N);
      for (let n = 0; n < N; n++) y[n] = x[n] + fx.chorus.mix * wet[n];
      x = y;
    }
    if (fx.echo.ms > 0 && fx.echo.mix > 0) {
      const D = Math.max(1, Math.round(fx.echo.ms * sr / 1000));
      const tail = Math.min(Math.floor(MAX_TAIL_S * sr), D * 8);
      const y = new Float64Array(x.length + tail), wet = new Float64Array(x.length + tail);
      for (let n = 0; n < y.length; n++) {
        const dry = n < x.length ? x[n] : 0;
        const w = (n >= D ? (n - D < x.length ? x[n - D] : 0) + fx.echo.fb * wet[n - D] : 0);
        wet[n] = w;
        y[n] = dry + fx.echo.mix * w;
      }
      x = y;
    }
    if (fx.rrev.decay > 0 && fx.rrev.mix > 0) {
      lead = Math.min(Math.floor(MAX_TAIL_S * sr), Math.round(fx.rrev.decay * sr));
      x = reverseReverb(x, sr, fx.rrev.decay, fx.rrev.mix);
    }
    if (fx.mix < 1) {
      const y = new Float64Array(x.length);
      for (let n = 0; n < x.length; n++) y[n] = fx.mix * x[n] + (1 - fx.mix) * (n >= lead && n - lead < orig.length ? orig[n - lead] : 0);
      x = y;
    }
    let peak = 0;
    for (let n = 0; n < x.length; n++) peak = Math.max(peak, Math.abs(x[n]));
    const g = peak > PEAK ? PEAK / peak : 1;
    const out = new Float32Array(x.length);
    for (let n = 0; n < x.length; n++) out[n] = x[n] * g;
    return out;
  }

  function encodeWav(samples, sr) {
    const buf = new ArrayBuffer(44 + samples.length * 2), v = new DataView(buf);
    const w = (o, s) => { for (let i = 0; i < s.length; i++) v.setUint8(o + i, s.charCodeAt(i)); };
    w(0, 'RIFF'); v.setUint32(4, 36 + samples.length * 2, true); w(8, 'WAVEfmt ');
    v.setUint32(16, 16, true); v.setUint16(20, 1, true); v.setUint16(22, 1, true);
    v.setUint32(24, sr, true); v.setUint32(28, sr * 2, true); v.setUint16(32, 2, true); v.setUint16(34, 16, true);
    w(36, 'data'); v.setUint32(40, samples.length * 2, true);
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]));
      v.setInt16(44 + i * 2, Math.round(s * 32767), true);
    }
    return buf;
  }

  const api = { applyFx, encodeWav, DEFAULT_FX, withDefaults };
  if (typeof module !== 'undefined' && module.exports) module.exports = api;
  else root.VoiceFx = api;
})(typeof window !== 'undefined' ? window : globalThis);
