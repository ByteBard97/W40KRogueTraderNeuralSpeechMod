#!/usr/bin/env python3
"""Full-set experiment: rewrite every voxcpm2 line's instruct text from stacked emotion
adjectives to single-focus delivery-mechanics phrasing (pace/pitch/volume/manner), per
docs/research/voxcpm2-in-character-consistency-findings.md's confirmed guidance, and
regenerate all 19 voxcpm2 clips so the whole set can be evaluated before deciding what
instruction style/settings to standardize on for the full corpus.

cfg_value stays at the documented default (2.0) across the board - the research only supports
lowering it reactively for buzzy/over-driven individual lines, not as a blanket change.

Run: /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/tts_bakeoff/regen_voxcpm2_delivery_mechanics.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
OUT_ROOT = ROOT / "data/bakeoff_abelard_emotion_matched"
MANIFEST_PATH = OUT_ROOT / "manifest.json"

sys.path.insert(0, str(ROOT / "tools/tts_engines"))
import voxcpm2 as eng  # noqa: E402

# guid -> new single-focus, delivery-mechanics instruct (pace/pitch/volume/manner only,
# no stacked emotion adjectives). Kept short, matching the official cookbook's own examples.
NEW_INSTRUCT = {
    "c488c38b-2d47-4ebc-ad0a-8edf135f188c": "sharp and clipped, hardening voice, fast pace",
    "bd409f76-e22d-4148-ab0e-365e01bce07a": "flat deadpan pace, then firm and steady",
    "ea8e726f-ddf0-4f5f-bf8f-8ad7d47ff8b8": "slow pace, faint wry lilt",
    "90827196-b1bf-476d-a840-9d2b3da15ea0": "firm, even pace, no rise in pitch",
    "bfe47a42-4849-41e9-af32-3169a2f01dc3": "quiet, low volume, near-whisper, slightly unsteady pace",
    "f10c2390-9b03-4351-b6cb-30cbe2ac0f65": "soft, halting pace, slightly higher pitch",
    "6b5c3963-a3d0-45bf-99a8-6b205e222b88": "gentle tone, slightly rising pitch on the questions",
    "860c80a6-1f48-4da9-a156-f39634d1b150": "flat, drained monotone, slow pace",
    "7e137ab5-504d-4c02-ad56-f0fb67c6ec1d": "low murmur, dry, faint wry edge",
    "e9096f08-89bb-4eeb-bdbe-0d19d411c774": "warm tone, even pace, gentle volume",
    "03267eb7-0120-44fb-b0b5-024df2a0a867": "warm tone, brighter pitch, relieved pace",
    "42f3127f-4751-45f9-a5e2-9f7f02f4f94d": "slow, heavy pace, lower pitch",
    "1c796994-4a41-4b17-8781-8e9f557f07c2": "steady, measured pace, low firm volume",
    "81dac0aa-dec3-4390-957c-cdcca5965873": "quick intake, slightly raised pitch, faster pace",
    "82e0df30-5484-4020-97bf-7c6bef9b155a": "breathless, barely audible, unsteady pace",
    "1983e00b-186a-48b4-9f8e-12196aa581d1": "calm, even pace, low steady volume",
    "bf3e87db-539b-45df-9d46-f9d7bf8d7dea": "sharp, loud, fast pace",
    "bf3ee630-ef78-451b-8a05-b08e0a0709c4": "sharp tone, rising pitch, fast pace",
    "4b4545fd-c001-44d5-80c3-07aa7ad7b37f": "slow, thoughtful pace, low murmuring tone",
}


def main() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    model = eng.load()

    for guid, new_instruct in NEW_INSTRUCT.items():
        key = f"voxcpm2:{guid}"
        entry = manifest[key]
        old_instruct = entry["annotation"]["instruct"]
        entry["annotation"] = dict(entry["annotation"], instruct=new_instruct)

        wav, sr = eng.synth(
            model, entry["text"],
            prompt_wav=entry["reference"]["wav"], prompt_text=entry["reference"]["text"],
            instruct=new_instruct,
        )
        wav = np.asarray(wav, dtype=np.float32).reshape(-1)
        wav_path = ROOT / entry["wav_path"]
        sf.write(str(wav_path), wav, sr)
        entry["audio_seconds"] = round(len(wav) / sr, 2)

        print(f"  {guid[:8]}: dur={entry['audio_seconds']}s")
        print(f"    old: {old_instruct}")
        print(f"    new: {new_instruct}")

        manifest[key] = entry
        MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    print("\ndone - all 19 voxcpm2 default clips regenerated with delivery-mechanics instructions.")


if __name__ == "__main__":
    main()
