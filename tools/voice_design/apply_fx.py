#!/usr/bin/env python3
"""Apply each speaker's saved voice FX preset to the merged render, without touching the raw master.

Reads data/render/export/{index.json,wav/} (tools/render_corpus/merge.py) and data/voice_fx/presets.json
({speaker: {"fx": {...}, "speed": 1.12}}, saved from the audition page). Writes the processed audio to
data/render/export_fx/ (same layout). The sidecar (prerendered.py) serves export_fx ahead of export, so
speakers with a preset get the processed audio and everyone else is untouched. Re-running only redoes
lines whose preset changed. Needs numpy, scipy, soundfile and ffmpeg (roguetts env or the scorer venv).

  python tools/voice_design/apply_fx.py [--only "Pasqal"]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from fx import apply_fx, apply_speed, preset_key  # noqa: E402


def process(src_root: Path, out_root: Path, presets: dict, only: str | None = None) -> tuple[int, int]:
    """(processed, skipped_up_to_date). Pure file IO, so it is testable with temp dirs."""
    index = json.loads((src_root / "index.json").read_text(encoding="utf-8"))
    out_idx_path = out_root / "index.json"
    out_idx = json.loads(out_idx_path.read_text(encoding="utf-8")) if out_idx_path.exists() else {}
    (out_root / "wav").mkdir(parents=True, exist_ok=True)
    done = skipped = 0
    for guid, e in index.items():
        preset = presets.get(e.get("speaker"))
        if not preset or (only and e.get("speaker") != only):
            continue
        key = hashlib.md5(preset_key(preset).encode()).hexdigest()[:12]
        dst = out_root / "wav" / f"{guid}.wav"
        if out_idx.get(guid, {}).get("fx_key") == key and dst.is_file():
            skipped += 1
            continue
        x, sr = sf.read(str(src_root / e["wav"]), dtype="float32")
        if x.ndim > 1:
            x = x.mean(axis=1)
        y = apply_speed(apply_fx(x, sr, preset.get("fx")), sr, float(preset.get("speed", 1.0)))
        sf.write(str(dst), y, sr, subtype="PCM_16")
        out_idx[guid] = {**e, "wav": f"wav/{guid}.wav", "fx_key": key}
        done += 1
        if done % 200 == 0:
            out_idx_path.write_text(json.dumps(out_idx, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"{done} processed", flush=True)
    out_idx_path.write_text(json.dumps(out_idx, ensure_ascii=False, indent=1), encoding="utf-8")
    return done, skipped


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", default=None, help="one speaker name")
    args = ap.parse_args()
    presets = json.loads((ROOT / "data/voice_fx/presets.json").read_text(encoding="utf-8"))
    done, skipped = process(ROOT / "data/render/export", ROOT / "data/render/export_fx", presets, args.only)
    print(f"processed {done}, up to date {skipped}; presets for: {sorted(presets)}")


if __name__ == "__main__":
    main()
