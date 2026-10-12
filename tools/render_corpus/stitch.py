"""Join separately rendered segments of one line into a single take.

Each segment is trimmed of edge silence, RMS-matched to the loudest one's level target, then joined
with a fixed pause and a short crossfade at each end so no click lands on the seam.
"""
from __future__ import annotations

import numpy as np

SILENCE_DB = -45.0   # edges quieter than this (relative to full scale) count as silence
KEEP_S = 0.03        # leave a little room after trimming so word onsets are not clipped
PAUSE_S = 0.35
FADE_S = 0.015


def trim_silence(x: np.ndarray, sr: int, thresh_db: float = SILENCE_DB, keep_s: float = KEEP_S) -> np.ndarray:
    loud = np.flatnonzero(np.abs(x) > 10 ** (thresh_db / 20))
    if loud.size == 0:
        return x
    keep = int(keep_s * sr)
    return x[max(0, loud[0] - keep): loud[-1] + keep + 1]


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x)))) if x.size else 0.0


def stitch(segments: list[np.ndarray], sr: int, pause_s: float = PAUSE_S, fade_s: float = FADE_S,
           target_rms: float | None = None, match_levels: bool = True) -> np.ndarray:
    """Concatenate mono float32 segments with a pause between them."""
    parts = [trim_silence(np.asarray(s, dtype=np.float32), sr) for s in segments if len(s)]
    if not parts:
        return np.zeros(0, dtype=np.float32)
    target = target_rms or float(np.mean([rms(p) for p in parts]))
    fade = int(fade_s * sr)
    out: list[np.ndarray] = []
    for i, p in enumerate(parts):
        r = rms(p)
        p = p * (target / r) if r > 0 and match_levels else p
        p = p.copy()
        n = min(fade, len(p) // 2)
        if n:
            ramp = np.linspace(0.0, 1.0, n, dtype=np.float32)
            if i > 0:
                p[:n] *= ramp
            if i < len(parts) - 1:
                p[-n:] *= ramp[::-1]
        out.append(p)
        if i < len(parts) - 1:
            out.append(np.zeros(int(pause_s * sr), dtype=np.float32))
    y = np.concatenate(out)
    peak = float(np.max(np.abs(y)))
    return y / peak * 0.98 if peak > 0.98 else y
