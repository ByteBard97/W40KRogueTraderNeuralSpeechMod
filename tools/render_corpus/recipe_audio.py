"""Audio helpers for recipe renders (shared by the Render Lab and the render workers): 16-bit wav in and out, silence between pieces, and the numbers that flag a bad take.

numpy and the standard `wave` module only (the studio server runs under the system python, which has no soundfile).
"""
from __future__ import annotations

import io
import wave
from pathlib import Path

import numpy as np

FADE_MS = 8                  # edge fade on every piece so a join never clicks
FRAME_S = 0.05
SPEECH_FRAME_FRACTION = 0.1  # frames quieter than this share of the loudest frame's rms are pauses, not speech
CLIP_RUN = 3                 # consecutive samples at the file's ceiling that count as a clipped run
CEILING = 0.999
CREST_BAD_DB = 11.0          # below this the take sounds compressed / overdriven (measured on the cast render, 2026-10-13)


def read_wav(path: Path) -> tuple[np.ndarray, int]:
    """(float32 mono samples in -1..1, sample rate) from a 16-bit or 32-bit float wav."""
    raw = path.read_bytes()
    if raw[20:22] == b"\x03\x00":                       # IEEE float wav, which `wave` cannot read
        sr = int.from_bytes(raw[24:28], "little")
        i = raw.index(b"data")
        x = np.frombuffer(raw[i + 8:], dtype="<f4")
        ch = int.from_bytes(raw[22:24], "little")
        return (x.reshape(-1, ch).mean(axis=1) if ch > 1 else x).astype(np.float32), sr
    with wave.open(io.BytesIO(raw)) as w:
        sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
        if width != 2:
            raise ValueError(f"{path.name}: only 16-bit wav is supported, got {8 * width}-bit")
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    return (x.reshape(-1, ch).mean(axis=1) if ch > 1 else x), sr


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm = (np.clip(x, -1.0, 1.0) * 32767.0).astype("<i2")
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm.tobytes())


def limit_peak(x: np.ndarray, ceiling_db: float | None) -> np.ndarray:
    """Scale the whole take down (never up) so its peak is at most ceiling_db. Linear: dynamics are untouched."""
    if ceiling_db is None or not len(x):
        return x
    peak = float(np.abs(x).max())
    ceil = 10 ** (ceiling_db / 20)
    return x * (ceil / peak) if peak > ceil else x


LEVEL_WINDOW = 25.0          # dB below the loudest frame: quieter frames are pauses and do not count towards a piece's speech level
MAX_MATCH_GAIN_DB = 12.0
TRIM_THRESHOLD_DB = -40.0    # relative to the piece's peak
DEFAULT_KEEP_MS = 40


def speech_level_db(x: np.ndarray, sr: int) -> float | None:
    """Average level (dB rms) of the speech frames of a piece: what the ear takes as how loud it is."""
    w = max(1, int(sr * FRAME_S))
    n = len(x) // w
    if not n:
        return None
    ms = (x[: n * w].reshape(n, w) ** 2).mean(axis=1)
    db = 10 * np.log10(ms + 1e-12)
    keep = db > db.max() - LEVEL_WINDOW
    return float(10 * np.log10(ms[keep].mean() + 1e-12))


def match_levels(pieces: list[np.ndarray], sr: int) -> list[np.ndarray]:
    """Scale each piece so its speech level equals the median of the pieces (independent renders differ by several dB)."""
    levels = [speech_level_db(p, sr) for p in pieces]
    known = [v for v in levels if v is not None]
    if len(known) < 2:
        return pieces
    target = float(np.median(known))
    return [p if v is None else p * 10 ** (float(np.clip(target - v, -MAX_MATCH_GAIN_DB, MAX_MATCH_GAIN_DB)) / 20) for p, v in zip(pieces, levels)]


def trim_silence(x: np.ndarray, sr: int, keep_ms: int = DEFAULT_KEEP_MS) -> np.ndarray:
    """Cut the near-silence before and after the speech, keeping keep_ms, so the gap between pieces is the gap that was asked for."""
    if not len(x):
        return x
    loud = np.where(np.abs(x) > np.abs(x).max() * 10 ** (TRIM_THRESHOLD_DB / 20))[0]
    if not len(loud):
        return x
    keep = int(sr * keep_ms / 1000)
    return x[max(0, loud[0] - keep): loud[-1] + keep + 1]


def soften_onset(x: np.ndarray, sr: int, db: float, ms: int) -> np.ndarray:
    """Start the piece `db` quieter and rise smoothly to full level over `ms` (db is negative; 0 does nothing)."""
    n = min(len(x), int(sr * ms / 1000))
    if db >= 0 or n < 2:
        return x
    y = x.copy()
    t = np.linspace(0.0, 1.0, n, dtype=np.float32)
    y[:n] *= (10 ** (db / 20) + (1 - 10 ** (db / 20)) * (0.5 - 0.5 * np.cos(np.pi * t))).astype(np.float32)
    return y


def join(pieces: list[np.ndarray], gaps_ms: list[int], sr: int) -> np.ndarray:
    """Pieces in order with `gaps_ms[i]` of silence after piece i; each piece fades in and out by FADE_MS."""
    fade = int(sr * FADE_MS / 1000)
    out: list[np.ndarray] = []
    for i, p in enumerate(pieces):
        p = p.astype(np.float32).copy()
        n = min(fade, len(p) // 2)
        if n:
            ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
            p[:n] *= ramp
            p[-n:] *= ramp[::-1]
        out.append(p)
        if i < len(pieces) - 1 and gaps_ms[i] > 0:
            out.append(np.zeros(int(sr * gaps_ms[i] / 1000), dtype=np.float32))
    return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)


def metrics(x: np.ndarray, sr: int) -> dict:
    """Duration, peak, crest factor of the speech frames (peak over rms, dB) and clipped runs."""
    if not len(x):
        return {"seconds": 0.0, "peak_db": -120.0, "crest_db": None, "clip_runs": 0, "clipped_samples": 0, "flag": "empty"}
    a = np.abs(x)
    peak = float(a.max())
    w = max(1, int(sr * FRAME_S))
    n = len(x) // w
    crest = None
    if n:
        fr = x[: n * w].reshape(n, w)
        rms = np.sqrt((fr ** 2).mean(axis=1))
        keep = rms > rms.max() * SPEECH_FRAME_FRACTION
        if keep.any():
            s = fr[keep].ravel()
            crest = float(20 * np.log10(max(np.abs(s).max(), 1e-9) / max(np.sqrt((s ** 2).mean()), 1e-9)))
    hot = a >= min(CEILING, peak * 0.999) if peak >= 0.5 else np.zeros(len(a), dtype=bool)
    runs = 0
    if hot.any():
        d = np.diff(np.concatenate(([0], hot.astype(np.int8), [0])))
        runs = int(((np.where(d == -1)[0] - np.where(d == 1)[0]) >= CLIP_RUN).sum())
    flag = "overdriven" if crest is not None and crest < CREST_BAD_DB else "clipped" if runs else None
    return {"seconds": round(len(x) / sr, 2), "peak_db": round(20 * np.log10(max(peak, 1e-9)), 1),
            "crest_db": None if crest is None else round(crest, 1), "clip_runs": runs, "clipped_samples": int(hot.sum()), "flag": flag}
