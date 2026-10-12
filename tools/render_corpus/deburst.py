"""Soften the percussive consonant bursts (t, k, p, c, d) in generated speech.

The renders have bursts 25-40 dB above the surrounding 2.5-9 kHz level; the real BG3 narrator tops out near 16 dB.
This is a dynamic compressor on the high band only: it measures that band against its own running median level
and pulls down whatever sticks out past `thresh_db`. The low band and everything quieter than a burst is untouched.
"""
from __future__ import annotations

import numpy as np
from scipy.signal import butter, sosfiltfilt


def _smooth_gain(g: np.ndarray, sr: int, attack_ms: float, release_ms: float) -> np.ndarray:
    """One-pole smoothing of a gain curve (dB, <= 0): fast on the way down, slower on the way up."""
    a, r = np.exp(-1 / (sr * attack_ms / 1000)), np.exp(-1 / (sr * release_ms / 1000))
    out = np.empty_like(g)
    cur = 0.0
    for i, v in enumerate(g):
        k = a if v < cur else r
        cur = k * cur + (1 - k) * v
        out[i] = cur
    return out


def deburst(x: np.ndarray, sr: int, band=(2500.0, 9000.0), thresh_db=12.0, ratio=4.0) -> np.ndarray:
    hi_sos = butter(4, band[0], btype="high", fs=sr, output="sos")
    hf = sosfiltfilt(hi_sos, x)
    rest = x - hf
    step = max(1, int(sr * 0.002))
    win = int(sr * 0.004)
    e = np.sqrt(np.convolve(hf ** 2, np.ones(win) / win, "same") + 1e-12)
    db = 20 * np.log10(e)
    # running median over ~100 ms, evaluated on a coarse grid and interpolated back
    grid = db[::step]
    half = 25
    med = np.array([np.median(grid[max(0, i - half):i + half + 1]) for i in range(len(grid))])
    over = np.maximum(grid - med - thresh_db, 0.0)
    gain_db = -over * (1 - 1 / ratio)
    gain = np.interp(np.arange(len(x)), np.arange(len(grid)) * step, gain_db)
    gain = _smooth_gain(gain, sr, attack_ms=0.5, release_ms=15.0)
    return (rest + hf * 10 ** (gain / 20)).astype(np.float32)


PRESETS = {"mild": {"thresh_db": 12.0, "ratio": 4.0}, "strong": {"thresh_db": 8.0, "ratio": 6.0}}
