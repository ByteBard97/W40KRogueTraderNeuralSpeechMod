#!/usr/bin/env python3
"""Render every scenario in scenarios.json on a few real lines and report level safety (DawDreamer, same .dsp as the page).

  tools/fx_lab/.venv-fx/bin/python tools/fx_lab/check_scenarios.py [--only "v2 "] [--clips 4]

Per scenario: worst peak, fraction of samples at full scale (clipping), RMS relative to the raw clip in dB, NaN check.
The export wavs are already normalised to about full scale, so a scenario without enough Output dB trim will clip.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf
from scipy.signal import resample_poly

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
import dd_render  # noqa: E402

SR = 24000


def pick_clips(n: int) -> list[tuple[str, np.ndarray]]:
    idx = json.loads((ROOT / "data/render/export/index.json").read_text(encoding="utf-8"))
    by: dict[str, list[str]] = {}
    for g, e in idx.items():
        if 60 <= len(e.get("text", "")) <= 200:
            by.setdefault(e.get("speaker") or "?", []).append(g)
    chosen = [v[0] for k, v in sorted(by.items(), key=lambda kv: -len(kv[1]))[:n]]
    out = []
    for g in chosen:
        x, sr = sf.read(ROOT / "data/render/export" / idx[g]["wav"], dtype="float32")
        x = x if x.ndim == 1 else x[:, 0]
        if sr != SR:
            x = resample_poly(x, SR, sr).astype(np.float32)
        out.append((idx[g].get("speaker", "?"), x))
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default="")
    ap.add_argument("--clips", type=int, default=4)
    ap.add_argument("--dsp", default=str(HERE / "faust/chain.dsp"))
    a = ap.parse_args()
    code = Path(a.dsp).read_text(encoding="utf-8")
    scen = [s for s in json.loads((HERE / "scenarios.json").read_text(encoding="utf-8"))["scenarios"] if a.only in s["name"]]
    clips = pick_clips(a.clips)
    print(f"{len(scen)} scenarios x {len(clips)} clips ({', '.join(c[0] for c in clips)})")
    for s in scen:
        peaks, clipped, gains, bad = [], [], [], False
        for _, x in clips:
            y = dd_render.render(code, x, SR, s["params"], tail_s=1.0)
            bad |= not np.isfinite(y).all()
            peaks.append(float(np.max(np.abs(y))))
            clipped.append(float(np.mean(np.abs(y) >= 0.999)))
            r = lambda v: float(np.sqrt(np.mean(v.astype(np.float64) ** 2)) + 1e-12)
            gains.append(20 * np.log10(r(y) / r(x)))
        flag = "  <-- CLIPS" if max(clipped) > 0.001 else ("  <-- NaN" if bad else "")
        print(f"{s['name'][:44]:44s} peak {max(peaks):.2f}  clipped {100*max(clipped):.2f}%  rms vs raw {min(gains):+.1f}..{max(gains):+.1f} dB{flag}")


if __name__ == "__main__":
    main()
