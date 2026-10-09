#!/usr/bin/env python3
"""Generate candidate voices for side NPCs from text descriptions (VoxCPM2 design mode by default).

Qwen3-TTS VoiceDesign was tried first and ignored every accent request (12/12 clips American, see
probe_accent_phrasing.py), so VoxCPM2's `(description)text` design mode is the default engine.

Every candidate speaks the same fixed neutral sentence so they can be compared by ear, and so the
winner can serve as a cloning reference (Qwen3-TTS README: design a clip once, clone from it for
consistency). Candidates are different samples of the same description, each with its own recorded seed
(manifest `gen.candidates`; clips from before seeding was added have no entry).

Run in the VoxCPM2 env (Mac: ~/rt-tts/.venv-vox) for --engine vox, or the qwen env for --engine qwen:
  python tools/voice_design/design.py [--engine vox] [--candidates 6] [--only "Muaran"] [--redo]
Output: data/voice_design/clips/<slug>/c<i>.wav + data/voice_design/design_manifest.json.
Descriptions come from npcs.json; data/voice_design/overrides.json ({name: description}, written by
the audit page's "redo" button) wins over it. Resumable: existing clips are skipped unless --redo.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/voice_design"
MODEL = "Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign"
BATCH = 3


ACCENT = "British English accent"


def vox_prompt(description: str) -> str:
    """The probe's best phrasing put the accent last: '..., British English accent.'"""
    d = description.replace(f", {ACCENT},", ",").replace(f", {ACCENT}", "").rstrip(" .")
    return f"{d}, {ACCENT}."


def seed_for(name: str, i: int, salt: str = "") -> int:
    """Stable 31-bit seed for candidate `i` of an NPC, so a candidate can be regenerated.

    Same name + index + salt -> same seed. Change `salt` (--salt) to draw a fresh set of voices."""
    h = hashlib.sha256(f"{name}|{i}|{salt}".encode("utf-8")).digest()
    return int.from_bytes(h[:4], "big") & 0x7FFFFFFF


def seed_all(seed: int) -> None:
    import random
    import numpy as np
    import torch
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", name.lower()).strip("_")


def descriptions() -> tuple[str, list[dict]]:
    cfg = json.loads((Path(__file__).parent / "npcs.json").read_text(encoding="utf-8"))
    ov_path = OUT / "overrides.json"
    ov = json.loads(ov_path.read_text(encoding="utf-8")) if ov_path.exists() else {}
    npcs = [{**n, "description": ov.get(n["name"], n["description"])} for n in cfg["npcs"]]
    return cfg["design_text"], npcs


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--candidates", type=int, default=6)
    ap.add_argument("--only", default=None, help="comma-separated NPC names")
    ap.add_argument("--redo", action="store_true")
    ap.add_argument("--engine", choices=["vox", "qwen"], default="vox")
    ap.add_argument("--cfg", type=float, default=2.0, help="VoxCPM cfg_value")
    ap.add_argument("--timesteps", type=int, default=10, help="VoxCPM inference_timesteps")
    ap.add_argument("--salt", default="", help="changes every candidate's seed; use with --redo for a fresh set")
    args = ap.parse_args()

    text, npcs = descriptions()
    if args.only:
        want = {s.strip() for s in args.only.split(",")}
        npcs = [n for n in npcs if n["name"] in want]
    import numpy as np
    import soundfile as sf
    if args.engine == "qwen":
        import torch
        from qwen_tts import Qwen3TTSModel
        device = "cuda:0" if torch.cuda.is_available() else "mps"
        model = Qwen3TTSModel.from_pretrained(MODEL, device_map=device, dtype=torch.bfloat16)
    else:
        from voxcpm import VoxCPM
        model = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)

    mpath = OUT / "design_manifest.json"
    manifest = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    for n in npcs:
        d = OUT / "clips" / slug(n["name"])
        d.mkdir(parents=True, exist_ok=True)
        todo = [i for i in range(args.candidates) if args.redo or not (d / f"c{i}.wav").exists()]
        t0 = time.time()
        prev = manifest.get(n["name"], {}).get("gen", {}).get("candidates", {})
        gen = {c: dict(v) for c, v in prev.items()}  # keep records of clips not regenerated now
        seeds = {f"c{i}.wav": seed_for(n["name"], i, args.salt) for i in todo}
        for c, sd in seeds.items():
            gen[c] = {"seed": sd, "salt": args.salt, "cfg": args.cfg, "timesteps": args.timesteps,
                      "description": n["description"], "text": text}
        if args.engine == "vox":
            for i in todo:  # seeded per (name, index, salt) so any candidate can be regenerated
                seed_all(seeds[f"c{i}.wav"])
                w = model.generate(text=f"({vox_prompt(n['description'])}){text}", cfg_value=args.cfg,
                                   inference_timesteps=args.timesteps)
                sf.write(str(d / f"c{i}.wav"), np.asarray(w, dtype=np.float32).reshape(-1), model.tts_model.sample_rate)
        for k in range(0, len(todo) if args.engine == "qwen" else 0, BATCH):
            ids = todo[k:k + BATCH]
            seed_all(seeds[f"c{ids[0]}.wav"])
            wavs, sr = model.generate_voice_design(
                text=[text] * len(ids), language=["English"] * len(ids),
                instruct=[n["description"]] * len(ids), max_new_tokens=700)
            for i, w in zip(ids, wavs):
                sf.write(str(d / f"c{i}.wav"), np.asarray(w, dtype=np.float32).reshape(-1), sr)
        manifest[n["name"]] = {"slug": slug(n["name"]), "gender": n["gender"], "role": n["role"],
                               "description": n["description"], "text": text, "engine": args.engine,
                               "gen": {"candidates": gen},
                               "candidates": [f"c{i}.wav" for i in range(args.candidates)]}
        mpath.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{n['name']}: {len(todo)} new in {time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
