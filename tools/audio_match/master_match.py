#!/usr/bin/env python3
"""Fit and apply a "match mastering" profile: an EQ curve + compressor that pushes a TTS
engine's raw output toward the spectral balance and dynamics of the real game VO.

This is offline post-processing, not real-time DSP - every synthesized line is disk-cached
after first generation (see src/TtsSidecar/server.py), so a filter chain here just becomes
part of that one-time cost.

Hard ceiling to be aware of: the reference VO is 48kHz; every TTS engine we've bench-marked
tops out at 22.05-24kHz (see conversation/PROJECT_PLAN.md). Nothing here can restore content
above the engine's own Nyquist frequency - that would need a learned bandwidth-extension model
(audio super-resolution), not an EQ. This only matches what's already inside that band.

Method:
  1. Pool a batch of reference clips (real VO, data/voices/prompts/*) and a batch of generated
     clips for one engine (data/bakeoff/<engine>/*), loudness-normalize each to the same LUFS so
     spectral averaging isn't dominated by level differences.
  2. Average the Welch PSD across each pool, smooth in log-frequency (~1/3 octave), take the
     dB difference (reference - generated) as the target EQ curve, taper it to 0 at the very low
     end and at the engine's Nyquist edge, and realize it as a linear-phase FIR filter.
  3. Measure crest factor (peak - RMS, dB) on both pools; if the generated pool is peakier than
     the reference, fit a pedalboard.Compressor to close roughly that gap.
  4. Apply: FIR filter -> compressor -> loudness-normalize to the reference pool's own average
     LUFS -> a brick-wall limiter as a clip-safety net.

Usage:
  .venv-tts/bin/python master_match.py fit --engine chatterbox_turbo --out profile_chatterbox_turbo.json
  .venv-tts/bin/python master_match.py apply --profile profile_chatterbox_turbo.json \\
      --in-dir ../../data/bakeoff/chatterbox_turbo --out-dir ../../data/bakeoff/chatterbox_turbo_eq
"""
from __future__ import annotations

import argparse
import json
import math
import warnings
from pathlib import Path

import numpy as np
import pyloudnorm as pyln
import soundfile as sf
from pedalboard import Compressor, Gain, Limiter, Pedalboard
from scipy.ndimage import gaussian_filter1d
from scipy.signal import firwin2, fftconvolve, resample_poly, welch

warnings.filterwarnings("ignore", message="Possible clipped samples in output")  # we clamp peaks ourselves below

ROOT = Path(__file__).resolve().parent.parent.parent
TARGET_LUFS = -20.0  # arbitrary common ground for the analysis stage only; final output is
                      # re-normalized to the reference pool's own measured average LUFS instead.
NPERSEG = 2048
N_LOG_BINS = 300
FIR_TAPS = 1025
LOW_TAPER_HZ = (30.0, 60.0)     # fade EQ gain to 0 below this - no useful signal, avoid rumble
HIGH_TAPER_FRACS = (0.70, 0.85)  # fraction of Nyquist where the high taper starts/ends - tuned
                                  # against chatterbox_turbo's own vocoder rolloff knee (~9-9.5kHz
                                  # at 24kHz sr), which is a hard synthesis ceiling, not a tonal
                                  # gap: boosting past it just amplifies noise floor, not signal.
MAX_EQ_DB = 6.0


def read_mono(path: Path) -> tuple[np.ndarray, int]:
    audio, sr = sf.read(path, dtype="float32", always_2d=False)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    return audio, sr


def resample_to(audio: np.ndarray, sr_from: int, sr_to: int) -> np.ndarray:
    if sr_from == sr_to:
        return audio
    g = math.gcd(sr_from, sr_to)
    return resample_poly(audio, sr_to // g, sr_from // g).astype(np.float32)


def loudness_normalize(audio: np.ndarray, sr: int, target_lufs: float) -> np.ndarray | None:
    meter = pyln.Meter(sr)
    loudness = meter.integrated_loudness(audio)
    if not math.isfinite(loudness):
        return None  # near-silent clip, not usable for this analysis
    out = pyln.normalize.loudness(audio, loudness, target_lufs)
    peak = np.max(np.abs(out))
    if peak > 0.99:  # pyloudnorm applies pure gain with no limiter - guard against clipping,
        out = out * (0.99 / peak)  # which would distort the PSD/crest-factor measurements below
    return out


def crest_factor_db(audio: np.ndarray) -> float:
    peak = np.max(np.abs(audio)) + 1e-9
    rms = np.sqrt(np.mean(audio**2)) + 1e-9
    return 20 * np.log10(peak / rms)


def load_pool(paths: list[Path], sr_target: int, limit: int) -> list[np.ndarray]:
    clips = []
    for p in paths[:limit]:
        audio, sr = read_mono(p)
        audio = resample_to(audio, sr, sr_target)
        normed = loudness_normalize(audio, sr_target, TARGET_LUFS)
        if normed is not None and len(normed) >= NPERSEG:
            clips.append(normed)
    return clips


def avg_psd_db(clips: list[np.ndarray], sr: int) -> tuple[np.ndarray, np.ndarray]:
    psds = [welch(c, fs=sr, nperseg=NPERSEG)[1] for c in clips]
    freqs = welch(clips[0], fs=sr, nperseg=NPERSEG)[0]
    return freqs, 10 * np.log10(np.mean(psds, axis=0) + 1e-12)


def smooth_log_curve(freqs: np.ndarray, db: np.ndarray, nyquist: float) -> tuple[np.ndarray, np.ndarray]:
    log_freqs = np.geomspace(30.0, nyquist * 0.999, N_LOG_BINS)
    db_log = np.interp(log_freqs, freqs, db)
    octaves = math.log2(nyquist / 30.0)
    sigma = (N_LOG_BINS / octaves) / 3.0 / 2.355  # ~1/3-octave smoothing window
    return log_freqs, gaussian_filter1d(db_log, sigma=sigma, mode="nearest")


def taper(freqs: np.ndarray, gain_db: np.ndarray, nyquist: float) -> np.ndarray:
    out = gain_db.copy()
    lo0, lo1 = LOW_TAPER_HZ
    low_mask = freqs < lo1
    out[low_mask] *= np.clip((freqs[low_mask] - lo0) / (lo1 - lo0), 0.0, 1.0)
    hi0, hi1 = HIGH_TAPER_FRACS[0] * nyquist, HIGH_TAPER_FRACS[1] * nyquist
    hi_mask = freqs > hi0
    out[hi_mask] *= np.clip(1.0 - (freqs[hi_mask] - hi0) / (hi1 - hi0), 0.0, 1.0)
    return np.clip(out, -MAX_EQ_DB, MAX_EQ_DB)


def build_fir(freqs: np.ndarray, gain_db: np.ndarray, sr: int) -> np.ndarray:
    nyquist = sr / 2
    freq_norm = np.concatenate(([0.0], freqs / nyquist, [1.0]))
    gain_db_full = np.concatenate(([gain_db[0]], gain_db, [0.0]))
    gain_lin = 10 ** (gain_db_full / 20)
    return firwin2(FIR_TAPS, freq_norm, gain_lin)


def fit_profile(engine: str, ref_dir: Path, gen_dir: Path, n_ref: int, n_gen: int) -> dict:
    gen_paths = sorted(gen_dir.glob("*.wav"))
    if not gen_paths:
        raise SystemExit(f"no generated clips found in {gen_dir}")
    _, sr = read_mono(gen_paths[0])

    ref_paths = sorted(p for p in ref_dir.glob("*/*.wav"))
    print(f"pooling {min(n_ref, len(ref_paths))} reference clips, {min(n_gen, len(gen_paths))} "
          f"generated clips ({engine} @ {sr} Hz)")
    ref_clips = load_pool(ref_paths, sr, n_ref)
    gen_clips = load_pool(gen_paths, sr, n_gen)
    if len(ref_clips) < 10 or len(gen_clips) < 10:
        raise SystemExit(f"too few usable clips after loudness filtering: ref={len(ref_clips)} gen={len(gen_clips)}")

    ref_freqs, ref_db = avg_psd_db(ref_clips, sr)
    gen_freqs, gen_db = avg_psd_db(gen_clips, sr)
    nyquist = sr / 2
    log_freqs, ref_smooth = smooth_log_curve(ref_freqs, ref_db, nyquist)
    _, gen_smooth = smooth_log_curve(gen_freqs, gen_db, nyquist)
    diff_db = taper(log_freqs, ref_smooth - gen_smooth, nyquist)
    fir = build_fir(log_freqs, diff_db, sr)
    checkpoints = [100, 200, 500, 1000, 2000, 4000, 8000, 8500, 9000, 9500, 10000, 10500, 11000]
    curve_preview = {f: round(float(np.interp(f, log_freqs, diff_db)), 2) for f in checkpoints if f < nyquist}
    absolute_preview = {
        f: {"ref_db": round(float(np.interp(f, log_freqs, ref_smooth)), 1),
            "gen_db": round(float(np.interp(f, log_freqs, gen_smooth)), 1)}
        for f in checkpoints if f < nyquist
    }

    ref_crest = float(np.mean([crest_factor_db(c) for c in ref_clips]))
    gen_crest = float(np.mean([crest_factor_db(c) for c in gen_clips]))
    reduction = max(0.0, gen_crest - ref_crest)
    ratio = float(np.clip(1.0 / (1.0 - reduction / gen_crest), 1.2, 6.0)) if reduction > 0 else 1.0

    ref_lufs = float(np.mean([pyln.Meter(sr).integrated_loudness(c) for c in ref_clips]))

    return {
        "engine": engine,
        "sample_rate": sr,
        "fir_taps": fir.tolist(),
        "compressor": {
            "threshold_db": TARGET_LUFS + 3.0,  # ~rms level of the loudness-normalized pool
            "ratio": ratio,
            "attack_ms": 5.0,
            "release_ms": 120.0,
        },
        "target_lufs": ref_lufs,
        "diagnostics": {
            "n_ref_clips": len(ref_clips), "n_gen_clips": len(gen_clips),
            "ref_crest_db": ref_crest, "gen_crest_db": gen_crest,
            "compressor_ratio": ratio, "eq_db_range": [float(diff_db.min()), float(diff_db.max())],
            "eq_curve_hz_to_db": curve_preview,
            "absolute_psd_hz_to_db": absolute_preview,
        },
    }


def apply_profile(audio: np.ndarray, sr: int, profile: dict) -> np.ndarray:
    if sr != profile["sample_rate"]:
        raise ValueError(f"profile fit for {profile['sample_rate']} Hz, got {sr} Hz audio")
    fir = np.asarray(profile["fir_taps"], dtype=np.float64)
    filtered = fftconvolve(audio, fir, mode="same").astype(np.float32)

    c = profile["compressor"]
    board = Pedalboard([
        Compressor(threshold_db=c["threshold_db"], ratio=c["ratio"],
                   attack_ms=c["attack_ms"], release_ms=c["release_ms"]),
    ])
    compressed = board(filtered.reshape(1, -1), sr)[0]

    normed = loudness_normalize(compressed, sr, profile["target_lufs"])
    if normed is None:
        normed = compressed
    board = Pedalboard([Limiter(threshold_db=-0.3)])
    limited = board(normed.reshape(1, -1), sr)[0]

    peak = np.max(np.abs(limited))  # belt-and-suspenders: guarantee no int16 clipping regardless
    if peak > 0.97:                 # of the limiter's attack/release behavior on fast transients
        limited = limited * (0.97 / peak)
    return limited


def cmd_fit(args: argparse.Namespace) -> None:
    profile = fit_profile(args.engine, Path(args.ref_dir), Path(args.gen_dir), args.n_ref, args.n_gen)
    Path(args.out).write_text(json.dumps(profile, indent=2), encoding="utf-8")
    print(json.dumps(profile["diagnostics"], indent=2))
    print(f"wrote {args.out}")


def cmd_apply(args: argparse.Namespace) -> None:
    profile = json.loads(Path(args.profile).read_text(encoding="utf-8"))
    in_dir, out_dir = Path(args.in_dir), Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = sorted(in_dir.glob("*.wav"))
    if args.limit:
        paths = paths[: args.limit]
    for p in paths:
        audio, sr = read_mono(p)
        processed = apply_profile(audio, sr, profile)
        sf.write(out_dir / p.name, processed, sr, subtype="PCM_16")
    print(f"wrote {len(paths)} processed clips to {out_dir}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    fit_ap = sub.add_parser("fit", help="fit an EQ + compressor profile from reference vs. generated audio")
    fit_ap.add_argument("--engine", required=True)
    fit_ap.add_argument("--ref-dir", default=str(ROOT / "data/voices/prompts"))
    fit_ap.add_argument("--gen-dir", default=None, help="default: data/bakeoff/<engine>")
    fit_ap.add_argument("--n-ref", type=int, default=250)
    fit_ap.add_argument("--n-gen", type=int, default=150)
    fit_ap.add_argument("--out", required=True)
    fit_ap.set_defaults(func=cmd_fit)

    apply_ap = sub.add_parser("apply", help="apply a fitted profile to a directory of wavs")
    apply_ap.add_argument("--profile", required=True)
    apply_ap.add_argument("--in-dir", required=True)
    apply_ap.add_argument("--out-dir", required=True)
    apply_ap.add_argument("--limit", type=int, default=None)
    apply_ap.set_defaults(func=cmd_apply)

    args = ap.parse_args()
    if args.cmd == "fit" and args.gen_dir is None:
        args.gen_dir = str(ROOT / "data/bakeoff" / args.engine)
    args.func(args)


if __name__ == "__main__":
    main()
