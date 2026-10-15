"""Align several takes of the same line (different voices) to one timeline and mix them into a group voice.

align(ref, take, sr): DTW on Whisper encoder features gives a monotone map from the reference timeline to the take; a time-varying phase vocoder
(pitch preserved) renders the take on that timeline. The stretch is limited (default 0.8x to 1.25x) so words are not smeared.
mix(takes, sr, ...): picks the median-length take as the timeline, aligns the rest to it, levels, jitters, detunes slightly and sums.
numpy/librosa/scipy plus the Whisper-small encoder (CPU is fine). Used by mix_chorus.py.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))

N_FFT, HOP = 1024, 240                   # STFT hop 10 ms at 24 kHz
FEAT_MODEL = "openai/whisper-small"      # its encoder frames (20 ms) track what is said, not who says it, so voices align
FEAT_LAYER = 8
FEAT_FRAME_S = 0.02
SMOOTH_FRAMES = 2.0                      # gaussian smoothing of the warp map, in 20 ms frames
MAX_LAG_S = 0.2                          # the limited-slope warp may trail the DTW path by at most this much
MAX_STRETCH = (0.8, 1.25)                # allowed source seconds per output second

_ENC: dict = {}


def _encoder():
    if not _ENC:
        import torch
        from transformers import WhisperFeatureExtractor, WhisperModel
        _ENC["fx"] = WhisperFeatureExtractor.from_pretrained(FEAT_MODEL)
        _ENC["model"] = WhisperModel.from_pretrained(FEAT_MODEL).get_encoder().eval()
        _ENC["torch"] = torch
    return _ENC


def _features(y: np.ndarray, sr: int) -> np.ndarray:
    """(frames, dim) Whisper encoder states every 20 ms, for the audio only (the 30 s padding is dropped)."""
    import librosa
    e = _encoder()
    y16 = librosa.resample(y, orig_sr=sr, target_sr=16000) if sr != 16000 else y
    n = max(2, int(np.ceil(len(y16) / 16000 / FEAT_FRAME_S)))
    feats = e["fx"](y16, sampling_rate=16000, return_tensors="pt").input_features
    with e["torch"].no_grad():
        h = e["model"](feats, output_hidden_states=True).hidden_states[FEAT_LAYER][0].numpy()
    h = h[:n]
    return (h - h.mean(axis=0, keepdims=True)) / (h.std(axis=0, keepdims=True) + 1e-6)


def warp_map(ref: np.ndarray, take: np.ndarray, sr: int, max_stretch=MAX_STRETCH) -> np.ndarray:
    """For every HOP-sized output frame (reference timeline), the position in `take` in STFT frames (float)."""
    import librosa
    from scipy.ndimage import gaussian_filter1d
    fr, ft = _features(ref, sr), _features(take, sr)
    _, wp = librosa.sequence.dtw(X=fr.T, Y=ft.T, metric="cosine")
    wp = wp[::-1]
    n = fr.shape[0]
    pos = np.array([wp[wp[:, 0] == i, 1].mean() for i in range(n)])
    pos = np.maximum.accumulate(gaussian_filter1d(pos, SMOOTH_FRAMES, mode="nearest"))
    lag = MAX_LAG_S / FEAT_FRAME_S
    out = np.empty(n)
    out[0] = pos[0]
    for i in range(1, n):       # follow the DTW path, but never move faster or slower than max_stretch allows
        out[i] = np.clip(out[i - 1] + np.clip(pos[i] - pos[i - 1], *max_stretch), pos[i] - lag, pos[i] + lag)
    out = np.clip(out, 0, ft.shape[0] - 1)
    ratio = FEAT_FRAME_S / (HOP / sr)                       # 20 ms frames -> 10 ms STFT frames
    t_out = np.arange(int(np.ceil(len(ref) / HOP)) + 1) * (HOP / sr)
    return np.interp(t_out / FEAT_FRAME_S, np.arange(n), out) * ratio


def render_on_map(take: np.ndarray, pos_frames: np.ndarray, n_samples: int) -> np.ndarray:
    """Time-varying phase vocoder: output frame j reads the take at source frame pos_frames[j]."""
    import librosa
    D = librosa.stft(take, n_fft=N_FFT, hop_length=HOP)
    n_bins, n_src = D.shape
    phi_adv = HOP * 2 * np.pi * np.fft.rfftfreq(N_FFT)
    D = np.concatenate([D, np.zeros((n_bins, 2), dtype=D.dtype)], axis=1)
    out = np.zeros((n_bins, len(pos_frames)), dtype=D.dtype)
    phase = np.angle(D[:, 0])
    for j, step in enumerate(pos_frames):
        i = int(min(step, n_src - 1))
        a = step - i
        c0, c1 = D[:, i], D[:, i + 1]
        mag = (1 - a) * np.abs(c0) + a * np.abs(c1)
        out[:, j] = mag * np.exp(1j * phase)
        dphi = np.angle(c1) - np.angle(c0) - phi_adv
        phase += phi_adv + dphi - 2 * np.pi * np.round(dphi / (2 * np.pi))
    return librosa.istft(out, hop_length=HOP, length=n_samples)


def align(ref: np.ndarray, take: np.ndarray, sr: int, max_stretch=MAX_STRETCH) -> tuple[np.ndarray, dict]:
    pos = warp_map(ref, take, sr, max_stretch)
    y = render_on_map(take, pos, len(ref))
    slope = np.diff(pos)
    lo, hi = np.percentile(slope, [5, 95])    # percentiles: the flat tail after the last word would otherwise show 0
    return y, {"stretch_min": float(lo), "stretch_max": float(hi), "ratio": len(take) / len(ref)}


def rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(x ** 2)) + 1e-9)


def mix(takes: list[np.ndarray], sr: int, jitter_ms: float = 25.0, detune_cents: float = 8.0, reverb: float = 0.12,
        max_stretch=MAX_STRETCH, seed: int = 0) -> tuple[np.ndarray, list[dict]]:
    """Group voice from several takes of one line. Returns (mono float32 audio, per-take diagnostics)."""
    import librosa
    from stitch import trim_silence
    rng = np.random.default_rng(seed)
    takes = [trim_silence(np.asarray(t, dtype=np.float32), sr) for t in takes]      # leading silence differs per take; align the speech, not the pauses
    ref_i = int(np.argsort([len(t) for t in takes])[len(takes) // 2])
    ref = takes[ref_i]
    layers, info = [], []
    for k, t in enumerate(takes):
        y, d = (ref.copy(), {"stretch_min": 1.0, "stretch_max": 1.0, "ratio": 1.0}) if k == ref_i else align(ref, t, sr, max_stretch)
        y = y * (rms(ref) / rms(y))
        if detune_cents and k != ref_i:                                   # tiny resample detune keeps the voices from fusing into one
            f = 2 ** (rng.uniform(-detune_cents, detune_cents) / 1200)
            y = librosa.resample(y, orig_sr=int(sr * f), target_sr=sr)
            y = np.pad(y, (0, max(0, len(ref) - len(y))))[: len(ref)]
        shift = int(rng.uniform(-jitter_ms, jitter_ms) / 1000 * sr)
        y = np.roll(y, shift)
        if shift > 0:
            y[:shift] = 0
        elif shift < 0:
            y[shift:] = 0
        layers.append(y)
        info.append({"take": k, "reference": k == ref_i, "shift_ms": round(shift / sr * 1000, 1), **{a: round(b, 3) for a, b in d.items()}})
    out = np.sum(layers, axis=0) / np.sqrt(len(layers))
    if reverb:
        for delay_ms, g in ((31, 1.0), (57, 0.6), (89, 0.35)):
            d = int(delay_ms / 1000 * sr)
            out[d:] += reverb * g * out[:-d]
    peak = float(np.max(np.abs(out)))
    return (out / peak * 0.95 if peak > 0.95 else out).astype(np.float32), info
