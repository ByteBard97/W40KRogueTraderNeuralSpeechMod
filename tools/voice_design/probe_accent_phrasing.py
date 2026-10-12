#!/usr/bin/env python3
"""Does any phrasing make VoiceDesign (or VoxCPM2 design) produce a non-American accent?

Renders 2 clips per phrasing into data/voice_design/probe/<engine>_<variant>/ ; score them with
score_candidates.py-style accent scoring afterwards. Run in the qwen env for engine=qwen, the VoxCPM2
env for engine=vox:
  python tools/voice_design/probe_accent_phrasing.py --engine qwen|vox
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "data/voice_design/probe"
TEXT = json.loads((Path(__file__).parent / "npcs.json").read_text(encoding="utf-8"))["design_text"]

BASE = "An elderly man, dry and gravelly voice, formal and weary, an old administrator speaking slowly with quiet authority"
VARIANTS = {
    "baseline": f"{BASE}, British English accent.",
    "rp": f"{BASE}. He speaks with a refined Received Pronunciation accent, like a BBC newsreader from England.",
    "london": f"{BASE}. He has a Southern English accent from London, never American.",
    "yorkshire": f"{BASE}. He has a broad Northern English accent from Yorkshire.",
    "scottish": f"{BASE}. He has a Scottish accent from Edinburgh.",
    "uk_first": f"An elderly Englishman from Britain. {BASE.split(', ', 1)[1]}.",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--engine", choices=["qwen", "vox"], required=True)
    ap.add_argument("--clips", type=int, default=2)
    args = ap.parse_args()
    import numpy as np
    import soundfile as sf
    if args.engine == "qwen":
        import torch
        from qwen_tts import Qwen3TTSModel
        dev = "cuda:0" if torch.cuda.is_available() else "mps"
        m = Qwen3TTSModel.from_pretrained("Qwen/Qwen3-TTS-12Hz-1.7B-VoiceDesign", device_map=dev, dtype=torch.bfloat16)
    else:
        from voxcpm import VoxCPM
        m = VoxCPM.from_pretrained("openbmb/VoxCPM2", load_denoiser=False)
    for name, desc in VARIANTS.items():
        d = OUT / f"{args.engine}_{name}"
        d.mkdir(parents=True, exist_ok=True)
        for i in range(args.clips):
            if (d / f"c{i}.wav").exists():
                continue
            if args.engine == "qwen":
                w, sr = m.generate_voice_design(text=TEXT, language="English", instruct=desc, max_new_tokens=700)
                w = w[0]
            else:
                w = m.generate(text=f"({desc}){TEXT}", cfg_value=2.0, inference_timesteps=10)
                sr = m.tts_model.sample_rate
            sf.write(str(d / f"c{i}.wav"), np.asarray(w, dtype=np.float32).reshape(-1), sr)
        print("done", args.engine, name, flush=True)


if __name__ == "__main__":
    sys.exit(main())
