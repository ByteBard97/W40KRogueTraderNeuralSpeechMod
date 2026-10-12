#!/usr/bin/env python3
"""One-off migration: promote this session's ad-hoc scratch comparison clips
(_qwen3_timbre_test/*.wav) into real manifest entries, so they show up as normal votable,
checkbox-taggable clips on the main voting page instead of a separate plain-audio listing.

Skips exact duplicates of variants already registered via generate_variants.py, and skips the
handful of scratch files that used a shortened/different test sentence rather than the real
line's target text (those aren't valid variants of a real line).

Run once: tools/tts_bakeoff/.venv-qwen/bin/python3 tools/tts_bakeoff/promote_scratch_variants.py
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
OUT_ROOT = ROOT / "data/bakeoff_abelard_emotion_matched"
MANIFEST_PATH = OUT_ROOT / "manifest.json"
SCRATCH_DIR = OUT_ROOT / "_qwen3_timbre_test"
CATALOG = json.loads((ROOT / "data/voices/catalog.json").read_text(encoding="utf-8"))

FEAR = "bfe47a42-4849-41e9-af32-3169a2f01dc3"
GRATEFUL = "f10c2390-9b03-4351-b6cb-30cbe2ac0f65"
RELIEVED = "03267eb7-0120-44fb-b0b5-024df2a0a867"
CAUTIOUS = "1c796994-4a41-4b17-8781-8e9f557f07c2"
SURPRISED = "81dac0aa-dec3-4390-957c-cdcca5965873"
SKEPTICAL = "ea8e726f-ddf0-4f5f-bf8f-8ad7d47ff8b8"
INDIGNANT = "bf3ee630-ef78-451b-8a05-b08e0a0709c4"


def ref_override(event: str) -> dict:
    c = CATALOG[event]
    return {
        "event": event, "wav": str(ROOT / "data/voices/wav/Abelard" / c["wav"].split("/")[-1]),
        "text": c["texts"][0]["text"], "emotion": None, "duration": c.get("duration", 0),
        "decision": None, "distance": None, "exact_match": False,
        "matched_emotion": "manual-variant-override",
    }


# (scratch_filename_no_ext, label, base_engine, guid, ref_override_or_None, note)
JOBS = [
    ("6_xvec_orig_ref", "qwen3_tts_xvec", "qwen3_tts", RELIEVED, None,
     "x_vector_only_mode=True (no ICL text/audio pairing), original reference clip"),
    ("6_xvec_Chapter3_Abelard_10", "qwen3_tts_xvec_chapter3", "qwen3_tts", RELIEVED,
     "BNTRS_Chapter3_Abelard_10", "x_vector_only_mode=True, alt reference clip"),
    ("6_xvec_IdiraRecruit_19", "qwen3_tts_xvec_idira", "qwen3_tts", RELIEVED,
     "PRL_IdiraRecruit_19", "x_vector_only_mode=True, alt reference clip"),
    ("7_xvec_vladaym", "qwen3_tts_xvec", "qwen3_tts", CAUTIOUS, None,
     "x_vector_only_mode=True, original reference clip"),
    ("5_altref_indignant_bf3ee630", "qwen3_tts_altref_yrliet", "qwen3_tts", INDIGNANT,
     "CH2_Yrliet_BaseDialogue_24", "alt reference clip (clean, accusatory-tagged)"),
    ("8_full_original_text", "qwen3_tts_buggy_fulltext", "qwen3_tts", CAUTIOUS, None,
     "REGRESSION REFERENCE: full untrimmed ref text (pre-fix), kept for pattern comparison "
     "against the narration-echo bug - expected to be worse, not a real candidate"),
    ("11_voxcpm2_take0", "voxcpm2_retake_t0", "voxcpm2", SURPRISED, None, "extra retake"),
    ("11_voxcpm2_take1", "voxcpm2_retake_t1", "voxcpm2", SURPRISED, None, "extra retake"),
    ("11_voxcpm2_take2", "voxcpm2_retake_t2", "voxcpm2", SURPRISED, None, "extra retake"),
    ("12_voxcpm2_skeptical_take0", "voxcpm2_retake_t0", "voxcpm2", SKEPTICAL, None, "extra retake"),
    ("12_voxcpm2_skeptical_take1", "voxcpm2_retake_t1", "voxcpm2", SKEPTICAL, None, "extra retake"),
    ("12_voxcpm2_skeptical_take2", "voxcpm2_retake_t2", "voxcpm2", SKEPTICAL, None, "extra retake"),
    ("13_voxcpm2_fear_bfe47a42_take0", "voxcpm2_retake_t0", "voxcpm2", FEAR, None, "extra retake"),
    ("13_voxcpm2_fear_bfe47a42_take1", "voxcpm2_retake_t1", "voxcpm2", FEAR, None, "extra retake"),
    ("13_voxcpm2_fear_bfe47a42_take2", "voxcpm2_retake_t2", "voxcpm2", FEAR, None, "extra retake"),
    ("13_voxcpm2_grateful_f10c2390_take0", "voxcpm2_retake_t0", "voxcpm2", GRATEFUL, None, "extra retake"),
    ("13_voxcpm2_grateful_f10c2390_take1", "voxcpm2_retake_t1", "voxcpm2", GRATEFUL, None, "extra retake"),
    ("13_voxcpm2_grateful_f10c2390_take2", "voxcpm2_retake_t2", "voxcpm2", GRATEFUL, None, "extra retake"),
    ("13_voxcpm2_relieved_03267eb7_take0", "voxcpm2_retake_t0", "voxcpm2", RELIEVED, None, "extra retake"),
    ("13_voxcpm2_relieved_03267eb7_take1", "voxcpm2_retake_t1", "voxcpm2", RELIEVED, None, "extra retake"),
    ("13_voxcpm2_relieved_03267eb7_take2", "voxcpm2_retake_t2", "voxcpm2", RELIEVED, None, "extra retake"),
    ("14_voxcpm2_instruct_toned_down_v1", "voxcpm2_instruct_tonedv1", "voxcpm2", FEAR, None,
     "instruct text replaced with toned-down wording v1 (see manifest annotation.instruct)"),
    ("14_voxcpm2_instruct_toned_down_v2", "voxcpm2_instruct_tonedv2", "voxcpm2", FEAR, None,
     "instruct text replaced with toned-down wording v2 (see manifest annotation.instruct)"),
    ("15_voxcpm2_astartia_altref_take0", "voxcpm2_altref_chapter3_t0", "voxcpm2", GRATEFUL,
     "BNTRS_Chapter3_Abelard_10", "alt reference clip"),
    ("15_voxcpm2_astartia_altref_take1", "voxcpm2_altref_chapter3_t1", "voxcpm2", GRATEFUL,
     "BNTRS_Chapter3_Abelard_10", "alt reference clip"),
    ("15_voxcpm2_astartia_altref_take2", "voxcpm2_altref_chapter3_t2", "voxcpm2", GRATEFUL,
     "BNTRS_Chapter3_Abelard_10", "alt reference clip"),
    ("16_voxcpm2_cfg2.0_take0", "voxcpm2_cfg2.0_t0", "voxcpm2", SURPRISED, None, "cfg_value=2.0"),
    ("16_voxcpm2_cfg2.0_take1", "voxcpm2_cfg2.0_t1", "voxcpm2", SURPRISED, None, "cfg_value=2.0"),
    ("16_voxcpm2_cfg2.5_take0", "voxcpm2_cfg2.5_t0", "voxcpm2", SURPRISED, None, "cfg_value=2.5"),
    ("16_voxcpm2_cfg2.5_take1", "voxcpm2_cfg2.5_t1", "voxcpm2", SURPRISED, None, "cfg_value=2.5"),
    ("16_voxcpm2_cfg3.0_take0", "voxcpm2_cfg3.0_t0", "voxcpm2", SURPRISED, None, "cfg_value=3.0"),
    ("16_voxcpm2_cfg3.0_take1", "voxcpm2_cfg3.0_t1", "voxcpm2", SURPRISED, None, "cfg_value=3.0"),
]

TONED_INSTRUCT = {
    "voxcpm2_instruct_tonedv1": ("Deliver with quiet, restrained unease - a private prayer "
        "under his breath, composure mostly intact despite the dread underneath."),
    "voxcpm2_instruct_tonedv2": ("A low, controlled murmur - Abelard keeps his composure but "
        "his voice drops and tightens with quiet dread."),
}


def main() -> None:
    import soundfile as sf

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    added = skipped = 0

    for stem, label, base_engine, guid, ref_event, note in JOBS:
        src = SCRATCH_DIR / f"{stem}.wav"
        if not src.exists():
            print(f"  MISSING source file, skipping: {src.name}")
            skipped += 1
            continue

        entry_key = f"{label}:{guid}"
        base_entry = manifest[f"{base_engine}:{guid}"]

        annotation = dict(base_entry["annotation"])
        if label in TONED_INSTRUCT:
            annotation["instruct"] = TONED_INSTRUCT[label]

        reference = ref_override(ref_event) if ref_event else base_entry["reference"]

        out_dir = OUT_ROOT / label
        out_dir.mkdir(parents=True, exist_ok=True)
        dest = out_dir / f"{guid}.wav"
        shutil.copyfile(src, dest)

        info = sf.info(str(dest))
        audio_seconds = round(info.frames / info.samplerate, 2)

        manifest[entry_key] = {
            "engine": label, "guid": guid, "text": base_entry["text"],
            "annotation": annotation, "reference": reference,
            "synth_seconds": None, "audio_seconds": audio_seconds,
            "wav_path": str(dest.relative_to(ROOT)),
            "variant_note": note,
        }
        print(f"  added: {entry_key} ({audio_seconds}s) - {note}")
        added += 1

    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"\n{added} entries added, {skipped} skipped (missing source).")


if __name__ == "__main__":
    main()
