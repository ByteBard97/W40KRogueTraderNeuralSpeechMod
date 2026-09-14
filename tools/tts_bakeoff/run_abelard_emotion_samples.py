#!/usr/bin/env python3
"""Synthesize a sample of Abelard's labeled unvoiced dialogue with one TTS engine,
using an emotion-matched zero-shot reference clip picked from his real, ear-verified
voiced lines (curation.json) - exact emotion match preferred, nearest-PAD-neighbor
fallback (see ../select_reference_clip.py).

Must be run under the correct venv/conda env for the given engine - same convention as
run_bakeoff.py (this project doesn't import all engines into one process; each has its
own, sometimes conflicting, dependency set):
  chatterbox, chatterbox_turbo, indextts2  -> .venv-tts (repo root)
  fish_s2, fish_s2cpp                      -> tools/tts_bakeoff/.venv-fish
  higgs                                    -> tools/tts_bakeoff/.venv-higgs
  qwen3_tts                                -> tools/tts_bakeoff/.venv-qwen
  voxcpm2                                  -> conda env `roguetts`

Usage: run_abelard_emotion_samples.py <engine> [--n N] [--seed S] [--force]

Output: data/bakeoff_abelard_emotion_matched/<engine>/<guid>.wav + manifest.json
  (manifest is shared/appended across engine runs, keyed by engine+guid, so re-running
  a different engine doesn't clobber earlier engines' entries).
"""
from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))  # tools/
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))
from annotation_bridge import route  # noqa: E402
from select_reference_clip import ReferenceLibrary  # noqa: E402

OUT_ROOT = ROOT / "data/bakeoff_abelard_emotion_matched"
MANIFEST_PATH = OUT_ROOT / "manifest.json"


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    import wave
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def load_manifest() -> dict:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {}


def save_manifest(m: dict) -> None:
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")


def load_labeled_lines(n: int, seed: int) -> list[dict]:
    """A sample of already-labeled unvoiced Abelard lines from
    data/annotations/cache_claude_abelard/, joined back to their real text via
    conversations.enGB.json (the cache only stores guid + annotation, not text)."""
    cache_dir = ROOT / "data/annotations/cache_claude_abelard"
    labeled = []
    for f in sorted(cache_dir.glob("*.json")):
        d = json.loads(f.read_text(encoding="utf-8"))
        for rec in d["lines"]:
            labeled.append(rec)
    if not labeled:
        raise SystemExit(f"no labeled lines found in {cache_dir} - run the unvoiced "
                          f"labeling harness first")

    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    text_by_key = {}
    for c in convs:
        for l in c.get("lines", []):
            if l.get("text_key"):
                text_by_key[l["text_key"]] = l["text"]

    random.Random(seed).shuffle(labeled)
    lines = []
    for rec in labeled:
        text = text_by_key.get(rec["guid"])
        if not text:
            continue
        lines.append({**rec, "text": text})
        if len(lines) >= n:
            break
    return lines


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("engine")
    ap.add_argument("--n", type=int, default=8, help="how many labeled lines to sample")
    ap.add_argument("--seed", type=int, default=42, help="fixed seed so every engine "
                     "synthesizes the SAME sample of lines for a fair comparison")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    lines = load_labeled_lines(args.n, args.seed)
    lib = ReferenceLibrary("Abelard")

    out_dir = OUT_ROOT / args.engine
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()

    eng = importlib.import_module(f"tts_engines.{args.engine}")
    t0 = time.time()
    ctx = eng.load()
    load_s = time.time() - t0
    print(f"{args.engine}: loaded in {load_s:.1f}s")

    for rec in lines:
        guid = rec["guid"]
        wav_path = out_dir / f"{guid}.wav"
        entry_key = f"{args.engine}:{guid}"
        if not args.force and wav_path.exists() and entry_key in manifest:
            continue

        ref = lib.find(rec["emotion"])
        annotation = {"emotion": rec["emotion"], "intensity": rec["intensity"],
                      "pace": rec["pace"], "nonverbal": rec["nonverbal"],
                      "instruct": rec["instruct"]}
        text, kwargs = route(args.engine, rec["text"], annotation)

        entry = {
            "engine": args.engine, "guid": guid, "text": rec["text"],
            "annotation": annotation, "reference": ref,
        }
        try:
            t0 = time.time()
            try:
                audio, sr = eng.synth(ctx, text, ref["wav"], ref["text"], **kwargs)
            except TypeError:
                audio, sr = eng.synth(ctx, text, ref["wav"], ref["text"])
            entry["synth_seconds"] = round(time.time() - t0, 2)
            write_wav(wav_path, np.asarray(audio, dtype=np.float32).reshape(-1), sr)
            entry["audio_seconds"] = round(len(audio) / sr, 2)
            entry["wav_path"] = str(wav_path.relative_to(ROOT))
            print(f"  ok: {guid} ({rec['emotion']} -> ref {ref['matched_emotion']}, "
                  f"dist={ref['distance']})")
        except Exception as e:
            entry["error"] = f"{type(e).__name__}: {e}"
            print(f"  FAILED: {guid}: {entry['error']}")
            traceback.print_exc()

        manifest[entry_key] = entry
        save_manifest(manifest)  # save after every item - a crash mid-run loses nothing


if __name__ == "__main__":
    main()
