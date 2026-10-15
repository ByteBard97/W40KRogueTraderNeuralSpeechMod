#!/usr/bin/env python3
"""Null test: the same Faust chain through FaustWasm (node) and DawDreamer must agree.

  tools/fx_lab/.venv-fx/bin/python tools/fx_lab/null_test.py [file.dsp] [--params '{"Ring_Hz": 40, ...}']

Prints, per case, the correlation, the max sample difference and the RMS of the difference relative to the signal.
Controls that use noise (static) are not expected to match; run them with the noise level at zero.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402

SR = 24000
CASES = {
    "default": {},
    "bandpass": {"Highpass_Hz_0_off": 300, "Lowpass_Hz_0_off": 3400},
    "ring+drive": {"Ring_Hz": 40, "Ring_mix": 0.6, "Drive": 0.4},
    "echo+reverb": {"Echo_ms": 90, "Echo_feedback": 0.4, "Echo_mix": 0.5, "Reverb_mix": 0.3},
    "pitch": {"Pitch_semitones": -3},
    "deess": {"De_ess_threshold_dB_0_off": -30, "De_ess_frequency_Hz": 3000},
    "compressor": {"Compressor_ratio_1_off": 8, "Compressor_threshold_dB": -30, "Compressor_makeup_dB": 6},
    "phaser": {"Phaser_mix_0_off": 0.7, "Phaser_rate_Hz": 1.0},
    "phaser8fb": {"Phaser_mix_0_off": 1, "Phaser_rate_Hz": 0.7, "Phaser_feedback": 0.6, "Phaser_stages_2_4_6_8": 8},
    "vocoder16": {"Vocoder_mix_0_off": 1, "Vocoder_carrier_noise": 0},
    "vocoder8": {"Vocoder_mix_0_off": 1, "Vocoder_bands_8_16_24_32": 8, "Vocoder_carrier_noise": 0, "Vocoder_consonant_pass_4_5_kHz": 0},
    "vocoder32": {"Vocoder_mix_0_off": 0.8, "Vocoder_bands_8_16_24_32": 32, "Vocoder_carrier_noise": 0},
    "eq": {"EQ_mid_gain_dB": 9, "EQ_low_gain_dB": -6, "EQ_shelf_gain_dB": 6},
    "harmonizer": {"Harmonizer_voice_1_level": 0.6, "Harmonizer_voice_2_level": 0.4},
    "resonator": {"Resonator_mix_0_off": 0.8},
    "wow+flutter": {"Wow_cents": 20, "Flutter_cents": 10},
    "dropout": {"Dropout_amount_0_off": 0.6},
    "freqshift": {"Freq_shift_Hz_negative_shifts_down": 35, "Freq_shift_mix_0_off": 1},
    "freqshift-mix": {"Freq_shift_Hz_negative_shifts_down": -60, "Freq_shift_mix_0_off": 0.5},
    "metal": {"Metal_mix_0_off": 0.8, "Metal_base_Hz": 260, "Metal_Q_ring_length": 40},
    "metal-harmonic": {"Metal_mix_0_off": 1, "Metal_inharmonicity_0_harmonic_1_metal_bar": 0.2},
    "comb": {"Comb_mix_0_off": 0.8, "Comb_delay_ms": 2.5, "Comb_feedback": 0.6},
    "comb-negative": {"Comb_mix_0_off": 1, "Comb_delay_ms": 1.2, "Comb_feedback": -0.7},
    "autopan": {"Auto_pan_depth_0_off": 0.9, "Auto_pan_rate_Hz": 1.3},
    "stereo-chorus": {"Stereo_chorus_mix_0_off": 0.7, "Stereo_chorus_depth_ms": 4, "Stereo_chorus_right_offset_deg": 120},
    "stereo-phaser": {"Stereo_phaser_mix_0_off": 0.9, "Stereo_phaser_rate_Hz": 0.8, "Stereo_phaser_feedback": 0.5, "Stereo_phaser_stages_2_4_6_8": 6},
    "bass-spread": {"Bass_spread_mix_0_off": 1, "Bass_spread_delay_ms": 6, "Bass_spread_motion_depth": 0.7},
    "static": {"Static_level_dB_60_off": -20},
    "limiter": {"Limiter_threshold_dB_0_off": -12, "Output_dB": 6},
}
STATIC = {"Static_level_dB_60_off": -20}   # noise differs per runtime, so it gets a behaviour check, not a null test


def test_signal(sr: int = SR, seconds: float = 2.0) -> np.ndarray:
    n = np.arange(int(sr * seconds))
    env = 0.5 + 0.5 * np.sin(2 * np.pi * 3 * n / sr)
    return (env * (0.4 * np.sin(2 * np.pi * 220 * n / sr) + 0.2 * np.sin(2 * np.pi * 1330 * n / sr + 0.5)
                   + 0.1 * np.sin(2 * np.pi * 3100 * n / sr))).astype(np.float32)


def wasm_render(dsp: Path, x: np.ndarray, params: dict, tail_s: float) -> np.ndarray:
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        x.tofile(td / "in.f32")
        (td / "p.json").write_text(json.dumps(params))
        subprocess.run(["node", str(HERE / "render_wasm.mjs"), str(dsp), str(td / "in.f32"), str(SR), str(td / "p.json"),
                        str(td / "out.f32"), str(tail_s)], check=True, capture_output=True)
        return np.fromfile(td / "out.f32", dtype=np.float32).reshape(2, -1)        # left, then right


def compare(a: np.ndarray, b: np.ndarray) -> dict:
    """Worst of the channels when given (2, n) arrays."""
    if a.ndim == 2:
        rs = [compare(a[c], b[c]) for c in range(a.shape[0])]
        return {"corr": min(r["corr"] for r in rs), "max_diff": max(r["max_diff"] for r in rs), "rel_rms": max(r["rel_rms"] for r in rs)}
    n = min(len(a), len(b))
    a, b = a[:n].astype(np.float64), b[:n].astype(np.float64)
    d = a - b
    return {"corr": float(np.corrcoef(a, b)[0, 1]) if a.std() and b.std() else float("nan"),
            "max_diff": float(np.max(np.abs(d))), "rel_rms": float(np.sqrt(np.mean(d ** 2)) / max(1e-9, np.sqrt(np.mean(a ** 2))))}


def static_check(dsp: Path, code: str) -> None:
    """Static must follow the voice: silence in -> near silence out (after the tail), signal in -> audible hiss, in both runtimes."""
    sig = test_signal()
    quiet = np.zeros(SR * 2, dtype=np.float32)
    for name, run in (("wasm", lambda x: wasm_render(dsp, x, STATIC, 0.0)), ("dawdreamer", lambda x: dd_render.render(code, x, SR, STATIC))):
        rms = lambda v: float(np.sqrt(np.mean(v.astype(np.float64) ** 2)))
        base = run(sig) - (wasm_render(dsp, sig, {}, 0.0) if name == "wasm" else dd_render.render(code, sig, SR, {}))
        print(f"static[{name:10s}] silence-in rms={rms(run(quiet)):.5f}  added-hiss rms over signal={rms(base):.5f}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dsp", nargs="?", default=str(HERE / "faust/chain.dsp"))
    ap.add_argument("--params", default=None, help="JSON for one extra custom case")
    args = ap.parse_args()
    dsp = Path(args.dsp)
    code = dsp.read_text(encoding="utf-8")
    cases = dict(CASES)
    if args.params:
        cases["custom"] = json.loads(args.params)
    x = test_signal()
    for name, params in cases.items():
        tail = 1.0 if ("Echo_ms" in params or "Reverb_mix" in params) else 0.0
        y_w = wasm_render(dsp, x, params, tail)
        y_d = dd_render.render(code, x, SR, params, tail, stereo=True)
        r = compare(y_w, y_d)
        d = compare(y_d, dd_render.render(code, x, SR, {}, tail, stereo=True)) if name != "default" else {"rel_rms": 0}
        print(f"{name:12s} vs-default={d['rel_rms']:.3f}  corr={r['corr']:.5f}  max_diff={r['max_diff']:.5f}  rel_rms={r['rel_rms']:.5f}")

    static_check(dsp, code)


if __name__ == "__main__":
    main()