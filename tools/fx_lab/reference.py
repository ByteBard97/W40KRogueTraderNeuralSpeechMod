"""The real game voice, as a target for the FX Lab: average spectrum and stereo behaviour of a speaker's extracted clips.

Reads data/voices/catalog.json and, for clips the extractor left unattributed, data/voices/attribution.json (the overlay made by
tools/studio/server/studio_server/attribution.py). The average spectrum is in 25 third-octave bands from 50 Hz to 12.7 kHz with the overall
level removed, so it can be laid over the monitor's own average of the processed clip. Stereo stats come from the speaker's stereo clips
only (the game's processed voices are stereo files; the natural ones are mono). Results are cached per speaker.
"""
from __future__ import annotations

import json
import random
import wave
from pathlib import Path

import numpy as np

BAND_CENTRES = [1000 * 2 ** ((k - 13) / 3) for k in range(25)]
BAND_EDGE = 2 ** (1 / 6)
LEVEL_FROM, LEVEL_TO = 100, 8000          # the level reference: bands inside this range have mean 0 dB
MAX_CLIPS = 24
MIN_S, MAX_S = 2.0, 15.0
N_FFT = 4096
LOUD = 0.1                                 # frames quieter than this fraction of the loudest frame's RMS are skipped
ILD_FRAME_S = 0.02
_CACHE: dict = {}


def _catalog(root: Path) -> dict:
    cat = json.loads((root / "data/voices/catalog.json").read_text(encoding="utf-8"))
    over_path = root / "data/voices/attribution.json"
    over = json.loads(over_path.read_text(encoding="utf-8")) if over_path.is_file() else {}
    return {k: ({**e, "speaker": over[k]["speaker"]} if e["speaker"] == "_unattributed" and k in over else e) for k, e in cat.items()}


def speakers(root: Path) -> list[dict]:
    counts: dict[str, int] = {}
    for e in _catalog(root).values():
        if e["speaker"] != "_unattributed":
            counts[e["speaker"]] = counts.get(e["speaker"], 0) + 1
    return [{"speaker": s, "clips": n} for s, n in sorted(counts.items(), key=lambda kv: -kv[1])]


def _read(path: Path) -> tuple[np.ndarray, int]:
    with wave.open(str(path)) as w:
        n, sr, ch, sw = w.getnframes(), w.getframerate(), w.getnchannels(), w.getsampwidth()
        raw = w.readframes(n)
    x = np.frombuffer(raw, dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float32)
    x = x / max(1.0, float(np.abs(x).max()))
    return (x.reshape(-1, ch).T if ch > 1 else x[None, :]), sr


def _band_db(power: np.ndarray, sr: int) -> list[float | None]:
    f = np.fft.rfftfreq(N_FFT, 1 / sr)
    out = []
    for c in BAND_CENTRES:
        lo, hi = c / BAND_EDGE, c * BAND_EDGE
        m = (f >= lo) & (f < hi)
        out.append(float(10 * np.log10(power[m].mean() + 1e-20)) if hi <= sr / 2 and m.any() else None)
    return out


def _stft_power(x: np.ndarray) -> np.ndarray:
    w = np.hanning(N_FFT)
    frames = np.array([x[i : i + N_FFT] * w for i in range(0, len(x) - N_FFT, N_FFT // 2)])
    if not len(frames):
        return np.zeros((0, N_FFT // 2 + 1))
    rms = np.sqrt((frames ** 2).mean(1))
    keep = rms > LOUD * rms.max()
    return np.abs(np.fft.rfft(frames[keep], axis=1)) ** 2


def _stereo_stats(x: np.ndarray, sr: int) -> tuple[float, float, float] | None:
    left, right = x[0], x[1]
    mid, side = (left + right) / 2, (left - right) / 2
    if np.sqrt((mid ** 2).mean()) < 0.01:
        return None
    h = max(1, int(sr * ILD_FRAME_S)); nf = len(left) // h
    el = np.sqrt((left[: nf * h].reshape(nf, h) ** 2).mean(1)) + 1e-6
    er = np.sqrt((right[: nf * h].reshape(nf, h) ** 2).mean(1)) + 1e-6
    loud = (el + er) > (el + er).max() * 0.2
    ild = (20 * np.log10(el / er))[loud]
    corr = float(np.corrcoef(left, right)[0, 1]) if left.std() and right.std() else 1.0
    return corr, float(10 * np.log10((side ** 2).mean() / ((mid ** 2).mean() + 1e-12) + 1e-12)), float(ild.std()) if len(ild) > 1 else 0.0


def ltas(root: Path, speaker: str) -> dict:
    """{"freqs", "db", "clips_used", "stereo": {"corr", "side_mid_db", "ild_sd_db", "clips"} | None} for one speaker."""
    cat = _catalog(root)
    stamp = ((root / "data/voices/catalog.json").stat().st_mtime, (root / "data/voices/attribution.json").stat().st_mtime if (root / "data/voices/attribution.json").is_file() else 0)
    key = (str(root), speaker, stamp)
    if key in _CACHE:
        return _CACHE[key]
    clips = sorted((e for e in cat.values() if e["speaker"] == speaker and MIN_S <= e.get("duration", 0) <= MAX_S), key=lambda e: e["wav"])
    if not any(e["speaker"] == speaker for e in cat.values()):
        raise KeyError(speaker)
    random.Random(speaker).shuffle(clips)
    spectra, st, sr_used = [], [], 24000
    for e in clips[:MAX_CLIPS]:
        x, sr = _read(root / "data/voices" / e["wav"])
        sr_used = sr
        p = _stft_power(x.mean(axis=0))
        if len(p):
            spectra.append(p)
        if x.shape[0] >= 2:
            s = _stereo_stats(x, sr)
            if s:
                st.append(s)
    power = np.concatenate(spectra).mean(0) if spectra else np.zeros(N_FFT // 2 + 1)
    db = _band_db(power, sr_used)
    ref = [d for c, d in zip(BAND_CENTRES, db) if d is not None and LEVEL_FROM <= c <= LEVEL_TO]
    mean = float(np.mean(ref)) if ref else 0.0
    out = {"speaker": speaker, "freqs": BAND_CENTRES, "db": [None if d is None else round(d - mean, 2) for d in db], "clips_used": len(spectra),
           "stereo": {"corr": round(float(np.median([s[0] for s in st])), 3), "side_mid_db": round(float(np.median([s[1] for s in st])), 1),
                      "ild_sd_db": round(float(np.median([s[2] for s in st])), 2), "clips": len(st)} if st else None}
    _CACHE[key] = out
    return out
