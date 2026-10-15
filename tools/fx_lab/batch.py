#!/usr/bin/env python3
"""Batch-apply FX Lab presets to rendered lines with DawDreamer. Raw renders are never touched.

  tools/fx_lab/.venv-fx/bin/python tools/fx_lab/batch.py [--only SPEAKER] [--limit N] [--src DIR] [--out DIR]

Reads  data/render/export/{index.json,wav/}                      (tools/render_corpus/merge.py)
       data/fx_lab/assignments.json  {"speakers": {name: [preset, ...]}, "lines": {guid: [preset, ...]}}
       tools/fx_lab/scenarios.json + data/fx_lab/presets.json     (preset name -> params; the page's saved presets win)
Writes data/render/export_fx/{index.json,wav/}  in the same layout apply_fx.py used, so src/TtsSidecar/prerendered.py
and the bank patcher can take it unchanged. Per line "lines" beats "speakers"; several presets run in series, in order.

Per clip: pad the input so echo / reverb / static tails ring out, run the chain, trim trailing silence, then match the
loudness of the raw clip (RMS over the active part), then run a short look-ahead limiter at -1 dBFS so a stray peak
dips only itself instead of pulling the whole clip down. The bank already plays
at the right level, so the goal is "same loudness, different character", not an absolute LUFS target.
Re-running redoes only lines whose preset (or the chain file) changed.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.ndimage import minimum_filter1d, uniform_filter1d

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402

PEAK_CEILING = 10 ** (-1 / 20)       # -1 dBFS
SILENCE_DB = -55                      # trailing audio below this (relative to the clip peak) is trimmed
KEEP_AFTER_S = 0.08
MAX_TAIL_S = 2.0


TAIL_CONTROLS = ("Echo_mix", "Echo_ms", "Reverb_mix", "Reverb_size", "Static_level_dB_60_off", "Static_tail_ms")


def _by_node(params: dict) -> dict[str, dict]:
    """The time-effect controls grouped by node: 'n3_Echo_mix' belongs to node 'n3', a flat 'Echo_mix' to node ''.
    A graph preset has one set per pedal, and a pedal's mix and delay only count together."""
    out: dict[str, dict] = {}
    for key, value in params.items():
        for name in TAIL_CONTROLS:
            if key == name:
                out.setdefault("", {})[name] = value
            elif key.endswith("_" + name):
                out.setdefault(key[: -len(name) - 1], {})[name] = value
    return out


def tail_seconds(params: dict) -> float:
    """How much silence to append so delay / reverb / static tails are not cut off (the longest over all pedals)."""
    t = 0.0
    for p in _by_node(params).values():
        if p.get("Echo_mix", 0) > 0 and p.get("Echo_ms", 0) > 0:
            t = max(t, min(MAX_TAIL_S, p["Echo_ms"] / 1000 * 8))
        if p.get("Reverb_mix", 0) > 0:
            t = max(t, 0.6 + 1.6 * p.get("Reverb_size", 0.5))
        if p.get("Static_level_dB_60_off", -60) > -59.5:
            t = max(t, p.get("Static_tail_ms", 120) / 1000 + 0.1)
    return min(MAX_TAIL_S, t)


def trim_tail(y: np.ndarray, sr: int, keep_s: float = KEEP_AFTER_S, thr_db: float = SILENCE_DB) -> np.ndarray:
    """Cut trailing silence. y is (n,) or (channels, n); the end is where the louder channel falls silent."""
    level = np.abs(y).max(axis=0) if y.ndim == 2 else np.abs(y)
    n = len(level)
    peak = float(level.max()) if n else 0.0
    if peak <= 0:
        return y
    live = np.nonzero(level > peak * 10 ** (thr_db / 20))[0]
    end = min(n, int(live[-1]) + 1 + int(keep_s * sr)) if len(live) else n
    return y[..., :end]


def active_rms(v: np.ndarray, sr: int) -> float:
    """RMS over 50 ms frames that are within 30 dB of the loudest frame, so silence and tails do not drag it down."""
    fr = max(1, int(0.05 * sr))
    n = len(v) // fr
    if n == 0:
        return float(np.sqrt(np.mean(v.astype(np.float64) ** 2)) + 1e-12)
    e = np.sqrt(np.mean(v[: n * fr].astype(np.float64).reshape(n, fr) ** 2, axis=1))
    keep = e > e.max() * 10 ** (-30 / 20)
    return float(np.sqrt(np.mean(e[keep] ** 2)) + 1e-12)


def limit_peaks(y: np.ndarray, sr: int, ceiling: float = PEAK_CEILING, window_s: float = 0.005) -> np.ndarray:
    """Look-ahead limiter: gain dips only around samples that would pass the ceiling, so the rest of the clip keeps its level.
    Min-filter the required gain over the window, then smooth it over the same window; the result never exceeds the ceiling."""
    a = np.abs(y).max(axis=0) if y.ndim == 2 else np.abs(y)       # stereo: one gain for both channels, set by the louder one
    if not a.size or a.max() <= ceiling:
        return y
    w = max(3, int(window_s * sr))
    need = np.minimum(1.0, ceiling / np.maximum(a, 1e-9))
    g = uniform_filter1d(minimum_filter1d(need, size=2 * w + 1), size=2 * w + 1)
    return (y * g).astype(np.float32)


def match_loudness(y: np.ndarray, ref: np.ndarray, sr: int) -> np.ndarray:
    """Scale y to ref's active RMS, then limit the peaks that would pass the ceiling. Stereo y: both channels together carry the loudness."""
    power = np.sqrt((y ** 2).mean(axis=0)) if y.ndim == 2 else y          # its square is the mean power over the channels
    y = y * (active_rms(ref, sr) / active_rms(power, sr))
    return limit_peaks(y, sr).astype(np.float32)


def load_presets() -> dict:
    out = {s["name"]: {"dsp": "chain.dsp", "params": s["params"]}
           for s in json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))["scenarios"]}
    saved = ROOT / "data/fx_lab/presets.json"
    if saved.exists():
        out.update(json.loads(saved.read_text(encoding="utf-8")))
    return out


def unclip(code: str) -> str:
    """The page keeps a hard clip at +-1 as a last safety. In batch we lift it so loud transients survive to the
    loudness-match step, which then scales the whole clip down instead of flattening the peaks."""
    return code.replace("max(-1) : min(1)", "max(-16) : min(16)")


IDENTICAL = 1e-5      # left and right closer than this are the same signal: the clip stays mono


def process_clip(x: np.ndarray, sr: int, steps: list[dict], dsp_codes: dict[str, str]) -> np.ndarray:
    """The clip through each preset in turn. Mono (n,) unless a stereo block made the sides differ, then (2, n).
    Between presets the signal is folded to mono again, so only the last preset's stereo survives."""
    y = x
    for st in steps:
        if y.ndim == 2:
            y = y.mean(axis=0)
        y = dd_render.render(unclip(dsp_codes[st["dsp"]]), y, sr, st["params"], tail_s=tail_seconds(st["params"]), stereo=True)
        y = trim_tail(y, sr)
        if np.abs(y[0] - y[1]).max() < IDENTICAL:
            y = y[0]
    return match_loudness(y, x, sr)


def run(src: Path, out: Path, assign: dict, presets: dict, only: str | None = None, limit: int | None = None) -> tuple[int, int]:
    index = json.loads((src / "index.json").read_text(encoding="utf-8"))
    idx_path = out / "index.json"
    out_idx = json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.exists() else {}
    (out / "wav").mkdir(parents=True, exist_ok=True)
    dsp_codes: dict[str, str] = {}
    done = skipped = 0
    for guid, e in index.items():
        names = assign.get("lines", {}).get(guid) or assign.get("speakers", {}).get(e.get("speaker") or "")
        if not names or (only and e.get("speaker") != only):
            continue
        steps = []
        for n in names:
            p = presets[n]
            f = p.get("dsp", "chain.dsp")
            if f not in dsp_codes:
                dsp_codes[f] = (HERE / "faust" / f).read_text(encoding="utf-8")
            steps.append({"dsp": f, "params": p["params"]})
        key = hashlib.md5(json.dumps([steps, [dsp_codes[s["dsp"]] for s in steps]], sort_keys=True).encode()).hexdigest()[:12]
        dst = out / "wav" / f"{guid}.wav"
        if out_idx.get(guid, {}).get("fx_key") == key and dst.is_file():
            skipped += 1
            continue
        x, sr = sf.read(str(src / e["wav"]), dtype="float32")
        x = x if x.ndim == 1 else x.mean(axis=1)
        y = process_clip(x, sr, steps, dsp_codes)
        sf.write(str(dst), y.T if y.ndim == 2 else y, sr, subtype="PCM_16")
        out_idx[guid] = {**e, "wav": f"wav/{guid}.wav", "fx_key": key, "fx": names, "channels": 2 if y.ndim == 2 else 1}
        done += 1
        if done % 100 == 0:
            idx_path.write_text(json.dumps(out_idx, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{done} processed", flush=True)
        if limit and done >= limit:
            break
    idx_path.write_text(json.dumps(out_idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return done, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", default=str(ROOT / "data/render/export"))
    ap.add_argument("--out", default=str(ROOT / "data/render/export_fx"))
    ap.add_argument("--assign", default=str(ROOT / "data/fx_lab/assignments.json"))
    ap.add_argument("--only", default=None, help="one speaker name")
    ap.add_argument("--limit", type=int, default=None, help="stop after N processed lines (for timing / spot checks)")
    a = ap.parse_args()
    assign = json.loads(Path(a.assign).read_text(encoding="utf-8"))
    done, skipped = run(Path(a.src), Path(a.out), assign, load_presets(), a.only, a.limit)
    print(f"processed {done}, up to date {skipped}")


if __name__ == "__main__":
    main()
