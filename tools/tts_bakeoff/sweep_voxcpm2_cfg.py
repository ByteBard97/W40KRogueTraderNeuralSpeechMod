#!/usr/bin/env python3
"""cfg_value sweep for VoxCPM2, over the 19 Abelard bake-off lines, to look for a pattern that
reduces voice-identity drift / improves in-character consistency for full-corpus production
settings.

Design (per advisor + kimi review, both consulted before running):
- Sweep cfg_value in {1.5, 2.0, 2.5, 3.0} only. inference_timesteps held fixed at the documented
  default (10) - no source or mechanism ties timesteps to voice-identity drift specifically, so
  crossing it would multiply cells to test a hypothesis nobody has. cfg_value is the one lever
  with a plausible mechanism (stricter conditioning adherence -> less drift from the reference
  speaker embedding).
- 3 repeats per cell (19 lines x 4 cfg values x 3 repeats = 228 clips). No seed exists in the
  VoxCPM2 API, so a single render per cell can't distinguish a parameter effect from ordinary
  run-to-run variance (VoxCPM2's own team recommends generating 1-3 times and picking the best -
  i.e. they're telling you the variance is real). 3 repeats is the bare minimum to estimate
  within-cell noise against between-cell (cfg) differences.
- retry_badcase=False for every render (VoxCPM2 default is True, max_times=3). Left on, every
  cell would silently be "best of up to 4 internal retries", which launders away exactly the
  badcase/drift failures cfg_value is supposed to be reducing - would confound the measurement.
  Production can still use retry_badcase=True later; this sweep measures raw behavior.
- Render order is shuffled across all 228 cells (not grouped by cfg) so any session-level drift
  in the shared GPU/model state isn't confounded with cfg_value.
- instruct text is held fixed per line at the delivery-mechanics rewrite already applied in
  manifest.json's `voxcpm2:<guid>` entries (regen_voxcpm2_delivery_mechanics.py) - this sweep
  is only varying cfg_value, not instruction wording.

Output: data/bakeoff_abelard_cfg_sweep/manifest.json (list of entries) + wav files in
data/bakeoff_abelard_cfg_sweep/wav/. Kept separate from the main bake-off manifest.json so this
experiment can't disturb the live vote.

Resumable: writes the manifest after every clip, and skips any (guid, cfg, repeat) cell whose
wav file already exists on disk.

Run: /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/tts_bakeoff/sweep_voxcpm2_cfg.py
"""
from __future__ import annotations

import json
import random
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent.parent
BAKEOFF_ROOT = ROOT / "data/bakeoff_abelard_emotion_matched"
MANIFEST_PATH = BAKEOFF_ROOT / "manifest.json"

SWEEP_ROOT = ROOT / "data/bakeoff_abelard_cfg_sweep"
SWEEP_WAV_DIR = SWEEP_ROOT / "wav"
SWEEP_MANIFEST_PATH = SWEEP_ROOT / "manifest.json"

sys.path.insert(0, str(ROOT / "tools/tts_engines"))
import voxcpm2 as eng  # noqa: E402

CFG_VALUES = [1.5, 2.0, 2.5, 3.0]
INFERENCE_TIMESTEPS = 10  # held fixed - see module docstring
REPEATS = 3
RNG_SEED = 20260917  # only controls render-order shuffle, not generation (no seed exists there)


def synth_with_cfg(model, text, prompt_wav, instruct, cfg_value, inference_timesteps):
    """Like voxcpm2.synth() but with cfg_value/inference_timesteps/retry_badcase exposed -
    the module-level synth() hardcodes cfg_value=2.0, inference_timesteps=10, and leaves
    retry_badcase at the library default (True)."""
    full_text = f"({instruct}){text}" if instruct else text
    wav = model.generate(
        text=full_text,
        reference_wav_path=prompt_wav,
        cfg_value=cfg_value,
        inference_timesteps=inference_timesteps,
        retry_badcase=False,
    )
    wav = np.asarray(wav, dtype=np.float32).reshape(-1)
    return wav, model.tts_model.sample_rate


def load_sweep_manifest() -> list[dict]:
    if SWEEP_MANIFEST_PATH.exists():
        return json.loads(SWEEP_MANIFEST_PATH.read_text(encoding="utf-8"))
    return []


def save_sweep_manifest(entries: list[dict]) -> None:
    SWEEP_ROOT.mkdir(parents=True, exist_ok=True)
    tmp = SWEEP_MANIFEST_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(entries, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(SWEEP_MANIFEST_PATH)


def main() -> None:
    base_manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    lines = []
    for key, entry in base_manifest.items():
        if not key.startswith("voxcpm2:"):
            continue
        lines.append({
            "guid": entry["guid"],
            "text": entry["text"],
            "instruct": entry["annotation"].get("instruct"),
            "emotion": entry["annotation"].get("emotion"),
            "prompt_wav": entry["reference"]["wav"],
            "reference": entry["reference"],
        })
    lines.sort(key=lambda x: x["guid"])
    print(f"{len(lines)} lines loaded from base manifest")

    cells = [
        (line, cfg, r)
        for line in lines
        for cfg in CFG_VALUES
        for r in range(REPEATS)
    ]
    rng = random.Random(RNG_SEED)
    rng.shuffle(cells)
    print(f"{len(cells)} total cells, shuffled render order")

    SWEEP_WAV_DIR.mkdir(parents=True, exist_ok=True)
    entries = load_sweep_manifest()
    done_ids = {e["cell_id"] for e in entries}

    model = eng.load()
    t_start = time.time()
    n_done = 0
    for line, cfg, r in cells:
        cell_id = f"{line['guid']}_cfg{cfg}_ts{INFERENCE_TIMESTEPS}_r{r}"
        if cell_id in done_ids:
            continue
        wav_path = SWEEP_WAV_DIR / f"{cell_id}.wav"
        wav, sr = synth_with_cfg(
            model, line["text"], line["prompt_wav"], line["instruct"],
            cfg_value=cfg, inference_timesteps=INFERENCE_TIMESTEPS,
        )
        sf.write(str(wav_path), wav, sr)
        entries.append({
            "cell_id": cell_id,
            "guid": line["guid"],
            "text": line["text"],
            "instruct": line["instruct"],
            "emotion": line["emotion"],
            "cfg_value": cfg,
            "inference_timesteps": INFERENCE_TIMESTEPS,
            "repeat": r,
            "audio_seconds": round(len(wav) / sr, 2),
            "wav_path": str(wav_path.relative_to(ROOT)),
            "reference": line["reference"],
        })
        save_sweep_manifest(entries)
        n_done += 1
        elapsed = time.time() - t_start
        print(f"[{len(entries)}/{len(cells)}] {cell_id} dur={entries[-1]['audio_seconds']}s "
              f"(this run: {n_done} done, {elapsed:.0f}s elapsed)")

    print(f"\ndone - {len(entries)}/{len(cells)} cells in sweep manifest.")


if __name__ == "__main__":
    main()
