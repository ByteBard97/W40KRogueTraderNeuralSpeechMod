"""Voice FX chain, numpy mirror of dsp.js (keep them in lockstep; tests/test_fx_parity.py checks it).

fx = {hp, lp, drive, crush:{bits,hold}, ring:{hz,mix}, trem:{hz,depth}, chorus:{ms,hz,mix}, echo:{ms,fb,mix}, rrev:{decay,mix}}
Order: highpass -> lowpass -> drive -> bitcrush -> ring mod -> tremolo -> chorus -> echo -> reverse reverb -> peak limit.
mix is the wet/dry blend of the whole chain (1 = processed, 0 = original), with the original lined up to
where it sits in the processed signal. Speed is a separate pitch-preserving time stretch applied last (see apply_speed).
"""
from __future__ import annotations

import copy
import io
import json
import subprocess

import numpy as np
from scipy.signal import lfilter

DEFAULT_FX = {
    "mix": 1, "hp": 0, "lp": 0, "drive": 0,
    "crush": {"bits": 16, "hold": 1},
    "ring": {"hz": 0, "mix": 0},
    "trem": {"hz": 0, "depth": 0},
    "chorus": {"ms": 0, "hz": 0.8, "mix": 0},
    "echo": {"ms": 0, "fb": 0, "mix": 0},
    "rrev": {"decay": 0, "mix": 0},
}
PEAK = 0.98
CHORUS_BASE_MS = (15.0, 20.0, 25.0)   # three voices, each with its own LFO rate and phase
CHORUS_RATE = (1.0, 1.17, 0.83)
MAX_TAIL_S = 1.5


def with_defaults(fx: dict | None) -> dict:
    d = copy.deepcopy(DEFAULT_FX)
    for k, v in (fx or {}).items():
        if isinstance(d.get(k), dict):
            d[k].update(v)
        else:
            d[k] = v
    return d


def _biquad(x: np.ndarray, sr: int, kind: str, f0: float) -> np.ndarray:
    w0 = 2 * np.pi * f0 / sr
    cos, alpha = np.cos(w0), np.sin(w0) / (2 * np.sqrt(0.5))
    if kind == "lp":
        b = [(1 - cos) / 2, 1 - cos, (1 - cos) / 2]
    else:
        b = [(1 + cos) / 2, -(1 + cos), (1 + cos) / 2]
    a = [1 + alpha, -2 * cos, 1 - alpha]
    return lfilter(np.array(b) / a[0], np.array(a) / a[0], x)


COMB_MS = [29.7, 37.1, 41.1, 43.7]
AP_MS = [5.0, 1.7]
AP_G = 0.7


def _schroeder(x: np.ndarray, sr: int, decay: float) -> np.ndarray:
    """4 parallel feedback combs + 2 allpasses, RT60 = decay seconds (mirrors dsp.js)."""
    wet = np.zeros(len(x))
    for ms in COMB_MS:
        d = max(1, int(round(ms * sr / 1000)))
        g = 10 ** (-3 * (ms / 1000) / decay)
        a = np.zeros(d + 1)
        a[0], a[d] = 1.0, -g
        wet += lfilter([1.0], a, x) / len(COMB_MS)
    for ms in AP_MS:
        d = max(1, int(round(ms * sr / 1000)))
        b = np.zeros(d + 1)
        b[0], b[d] = -AP_G, 1.0
        a = np.zeros(d + 1)
        a[0], a[d] = 1.0, -AP_G
        wet = lfilter(b, a, wet)
    return wet


def _reverse_reverb(x: np.ndarray, sr: int, decay: float, mix: float) -> np.ndarray:
    """Reverse -> reverb -> reverse, so the swell arrives before each sound; dry is shifted right by the tail."""
    tail = min(int(MAX_TAIL_S * sr), int(round(decay * sr)))
    r = np.concatenate([x[::-1], np.zeros(tail)])
    w = _schroeder(r, sr, decay)[::-1]
    return np.concatenate([np.zeros(tail), x]) + mix * w


def apply_fx(samples: np.ndarray, sr: int, fx_in: dict | None) -> np.ndarray:
    fx = with_defaults(fx_in)
    x = np.asarray(samples, dtype=np.float64).copy()
    orig = x.copy()
    lead = 0
    n = np.arange(len(x))
    if fx["hp"] > 0:
        x = _biquad(x, sr, "hp", fx["hp"])
    if fx["lp"] > 0:
        x = _biquad(x, sr, "lp", fx["lp"])
    if fx["drive"] > 0:
        k = 1 + fx["drive"] * 9
        x = np.tanh(k * x) / np.tanh(k)
    c = fx["crush"]
    if c["bits"] < 16 or c["hold"] > 1:
        hold = max(1, int(round(c["hold"])))
        v = x[(n // hold) * hold]
        if c["bits"] < 16:
            lv = 2 ** (c["bits"] - 1) - 1
            v = np.round(v * lv) / lv
        x = v
    r = fx["ring"]
    if r["hz"] > 0 and r["mix"] > 0:
        x = (1 - r["mix"]) * x + r["mix"] * x * np.sin(2 * np.pi * r["hz"] * n / sr)
    t = fx["trem"]
    if t["hz"] > 0 and t["depth"] > 0:
        lfo = 0.5 + 0.5 * np.sin(2 * np.pi * t["hz"] * n / sr)
        x = x * (1 - t["depth"] + t["depth"] * lfo)
    ch = fx["chorus"]
    if ch["ms"] > 0 and ch["mix"] > 0:
        wet = np.zeros(len(x))
        for i, (base, rate) in enumerate(zip(CHORUS_BASE_MS, CHORUS_RATE)):
            d = (base + ch["ms"] * np.sin(2 * np.pi * ch["hz"] * rate * n / sr + 2 * np.pi * i / 3)) * sr / 1000
            p = n - d
            i0 = np.floor(p).astype(np.int64)
            f = p - i0
            a = np.where(i0 >= 0, x[np.clip(i0, 0, len(x) - 1)], 0.0)
            b = np.where(i0 + 1 >= 0, x[np.clip(i0 + 1, 0, len(x) - 1)], 0.0)
            wet += ((1 - f) * a + f * b) / len(CHORUS_BASE_MS)
        x = x + ch["mix"] * wet
    e = fx["echo"]
    if e["ms"] > 0 and e["mix"] > 0:
        d = max(1, int(round(e["ms"] * sr / 1000)))
        tail = min(int(MAX_TAIL_S * sr), d * 8)
        xp = np.concatenate([x, np.zeros(tail)])
        b = np.zeros(d + 1)
        b[d] = 1.0
        a = np.zeros(d + 1)
        a[0], a[d] = 1.0, -e["fb"]
        x = xp + e["mix"] * lfilter(b, a, xp)
    rv = fx["rrev"]
    if rv["decay"] > 0 and rv["mix"] > 0:
        lead = min(int(MAX_TAIL_S * sr), int(round(rv["decay"] * sr)))
        x = _reverse_reverb(x, sr, rv["decay"], rv["mix"])
    if fx["mix"] < 1:
        dry = np.zeros(len(x))
        dry[lead:lead + len(orig)] = orig
        x = fx["mix"] * x + (1 - fx["mix"]) * dry
    peak = np.max(np.abs(x)) if len(x) else 0.0
    if peak > PEAK:
        x = x * (PEAK / peak)
    return x.astype(np.float32)


def apply_speed(samples: np.ndarray, sr: int, speed: float) -> np.ndarray:
    """Pitch-preserving tempo change with ffmpeg atempo (WSOLA). 1.0 returns the input unchanged."""
    if abs(speed - 1.0) < 1e-3:
        return samples
    import soundfile as sf
    buf = io.BytesIO()
    sf.write(buf, samples, sr, format="WAV", subtype="FLOAT")
    p = subprocess.run(["ffmpeg", "-v", "error", "-f", "wav", "-i", "pipe:0", "-af", f"atempo={speed:.4f}",
                        "-f", "wav", "pipe:1"], input=buf.getvalue(), capture_output=True, check=True)
    out, _ = sf.read(io.BytesIO(p.stdout), dtype="float32")
    return out


def preset_key(preset: dict) -> str:
    return json.dumps(preset, sort_keys=True)
