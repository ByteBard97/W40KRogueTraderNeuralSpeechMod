#!/usr/bin/env python3
"""Generate labeled reference-clip/take variants for specific (engine, guid) lines in the
Abelard emotion-matched bake-off, so the voting page can compare them as extra options
alongside the normal qwen3_tts/voxcpm2 entries for that line.

Writes into the same manifest.json / wav directory layout as run_abelard_emotion_samples.py,
using a distinct `engine` label per variant (e.g. "qwen3_tts_altref_idira") - the vote page
and tally already treat `engine` as a free-form string, so no schema/UI changes are needed.

Usage: edit VARIANTS below, then run under the right venv per engine:
    tools/tts_bakeoff/.venv-qwen/bin/python3 tools/tts_bakeoff/generate_variants.py qwen3_tts
    /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/tts_bakeoff/generate_variants.py voxcpm2
"""
from __future__ import annotations

import importlib
import json
import sys
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tools/
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))
from annotation_bridge import route  # noqa: E402
from lexicon import respell  # noqa: E402

OUT_ROOT = ROOT / "data/bakeoff_abelard_emotion_matched"
MANIFEST_PATH = OUT_ROOT / "manifest.json"


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def load_manifest() -> dict:
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8")) if MANIFEST_PATH.exists() else {}


def save_manifest(m: dict) -> None:
    MANIFEST_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


# Each entry: (label, base_engine_module, base_guid, ref_wav_relpath, ref_event_name, n_takes)
# ref_wav_relpath=None means reuse the base guid's existing reference clip (for voxcpm2 retakes).
VARIANTS = [
    # --- fear / "Throne spare us..." (bfe47a42) ---
    ("qwen3_tts_altref_theodorachoice", "qwen3_tts", "bfe47a42-4849-41e9-af32-3169a2f01dc3",
     "data/voices/wav/Abelard/PRL_TheodoraChoice_10.wav", "PRL_TheodoraChoice_10", 1),
    ("voxcpm2_take1", "voxcpm2", "bfe47a42-4849-41e9-af32-3169a2f01dc3", None, None, 2),

    # --- grateful / "I am... obliged, dear Astartia." (f10c2390) ---
    ("qwen3_tts_altref_chapter3", "qwen3_tts", "f10c2390-9b03-4351-b6cb-30cbe2ac0f65",
     "data/voices/wav/Abelard/BNTRS_Chapter3_Abelard_10.wav", "BNTRS_Chapter3_Abelard_10", 1),
    ("voxcpm2_take1", "voxcpm2", "f10c2390-9b03-4351-b6cb-30cbe2ac0f65", None, None, 2),

    # --- relieved / "Sister Argenta!..." (03267eb7) ---
    ("qwen3_tts_altref_idira", "qwen3_tts", "03267eb7-0120-44fb-b0b5-024df2a0a867",
     "data/voices/wav/Abelard/PRL_IdiraRecruit_19.wav", "PRL_IdiraRecruit_19", 1),
    ("qwen3_tts_altref_chapter3", "qwen3_tts", "03267eb7-0120-44fb-b0b5-024df2a0a867",
     "data/voices/wav/Abelard/BNTRS_Chapter3_Abelard_10.wav", "BNTRS_Chapter3_Abelard_10", 1),
    ("voxcpm2_take1", "voxcpm2", "03267eb7-0120-44fb-b0b5-024df2a0a867", None, None, 2),

    # --- cautious / Vladaym line (1c796994) ---
    ("qwen3_tts_altref_recruit12", "qwen3_tts", "1c796994-4a41-4b17-8781-8e9f557f07c2",
     "data/voices/wav/Abelard/PRL_AbelardRecruit_12.wav", "PRL_AbelardRecruit_12", 1),
    ("voxcpm2_take1", "voxcpm2", "1c796994-4a41-4b17-8781-8e9f557f07c2", None, None, 2),

    # --- surprised / "Lord Captain, you must be joking, surely?" (81dac0aa) ---
    ("qwen3_tts_altref_areastressful164", "qwen3_tts", "81dac0aa-dec3-4390-957c-cdcca5965873",
     "data/voices/wav/Abelard/BNTRS_AreaStressful_Abelard_164.wav", "BNTRS_AreaStressful_Abelard_164", 1),
    ("voxcpm2_take1", "voxcpm2", "81dac0aa-dec3-4390-957c-cdcca5965873", None, None, 2),
]


def main() -> None:
    if len(sys.argv) != 2 or sys.argv[1] not in ("qwen3_tts", "voxcpm2"):
        raise SystemExit("usage: generate_variants.py <qwen3_tts|voxcpm2>")
    run_module = sys.argv[1]

    manifest = load_manifest()
    eng = importlib.import_module(f"tts_engines.{run_module}")
    ctx = eng.load()

    catalog = json.loads((ROOT / "data/voices/catalog.json").read_text(encoding="utf-8"))

    for label, base_engine, base_guid, ref_wav_rel, ref_event, n_takes in VARIANTS:
        if base_engine != run_module:
            continue
        base_key = f"{base_engine}:{base_guid}"
        base_entry = manifest[base_key]
        text = base_entry["text"]
        annotation = base_entry["annotation"]

        if ref_wav_rel is None:
            ref_wav = base_entry["reference"]["wav"]
            ref_text = base_entry["reference"]["text"]
            ref_meta = base_entry["reference"]
        else:
            ref_wav = str(ROOT / ref_wav_rel)
            ref_text = catalog[ref_event]["texts"][0]["text"]
            ref_meta = {
                "event": ref_event, "wav": ref_wav, "text": ref_text,
                "emotion": None, "duration": catalog[ref_event].get("duration", 0),
                "decision": None, "distance": None, "exact_match": False,
                "matched_emotion": "manual-variant-override",
            }

        synth_text, kwargs = route(run_module, respell(text), annotation)

        for take in range(n_takes):
            variant_label = label if n_takes == 1 else f"{label}_t{take}"
            entry_key = f"{variant_label}:{base_guid}"
            out_dir = OUT_ROOT / variant_label
            out_dir.mkdir(parents=True, exist_ok=True)
            wav_path = out_dir / f"{base_guid}.wav"

            try:
                audio, sr = eng.synth(ctx, synth_text, ref_wav, ref_text, **kwargs)
            except TypeError:
                audio, sr = eng.synth(ctx, synth_text, ref_wav, ref_text)
            audio = np.asarray(audio, dtype=np.float32).reshape(-1)
            write_wav(wav_path, audio, sr)

            manifest[entry_key] = {
                "engine": variant_label, "guid": base_guid, "text": text,
                "annotation": annotation, "reference": ref_meta,
                "synth_seconds": None, "audio_seconds": round(len(audio) / sr, 2),
                "wav_path": str(wav_path.relative_to(ROOT)),
            }
            save_manifest(manifest)
            print(f"  ok: {entry_key} ({round(len(audio) / sr, 2)}s)")


if __name__ == "__main__":
    main()
