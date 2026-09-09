#!/usr/bin/env python3
"""Run one TTS engine over the fixed test set, cloning each companion from their prompt bank.

Usage:  run_bakeoff.py <engine> [--limit N] [--speakers A B ...]
Engines are adapters in engines/<name>.py exposing:
    load() -> ctx
    synth(ctx, text: str, prompt_wav: str|None, prompt_text: str|None) -> (np.float32 mono, sr)
Prompt: the top-ranked clip from data/voices/prompts/<speaker>/ (narrator uses a designed
voice or the engine default; adapters may ignore prompts they can't use).

Output: data/bakeoff/<engine>/<test_id>_<speaker>.wav + results.json (timings, errors).
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))
from annotation_bridge import route  # noqa: E402


def write_wav(path: Path, x: np.ndarray, sr: int) -> None:
    import wave
    x = np.clip(x, -1, 1)
    pcm = (x * 32767).astype("<i2").tobytes()
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sr)
        w.writeframes(pcm)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("engine")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--speakers", nargs="*")
    ap.add_argument("--ids", nargs="*", help="only these test-set line ids (e.g. t003 t078)")
    ap.add_argument("--force", action="store_true", help="regenerate even if the wav already exists")
    ap.add_argument("--prompt-rank", type=int, default=1)
    args = ap.parse_args()

    test = json.load(open(ROOT / "data/tts_test_set.json", encoding="utf-8"))
    prompts = json.load(open(ROOT / "data/voices/prompts/prompts.json", encoding="utf-8"))
    ann_path = ROOT / "data/annotations/annotations.enGB.json"
    annotations = json.loads(ann_path.read_text(encoding="utf-8")) if ann_path.exists() else {}
    out_dir = ROOT / "data/bakeoff" / args.engine
    out_dir.mkdir(parents=True, exist_ok=True)

    eng = importlib.import_module(f"tts_engines.{args.engine}")
    t0 = time.time()
    ctx = eng.load()
    load_s = time.time() - t0
    print(f"{args.engine}: loaded in {load_s:.1f}s")

    results = {"engine": args.engine, "load_seconds": round(load_s, 1), "items": []}
    done = 0
    for item in test:
        if args.speakers and item["speaker"] not in args.speakers:
            continue
        if args.ids and item["id"] not in args.ids:
            continue
        sp = item["speaker"]
        prompt_wav = prompt_text = None
        bank = prompts.get(sp) or []
        # some engines need >=5s prompts; prefer the requested rank among long-enough clips
        usable = [p for p in bank if p.get("duration", 0) >= 5.5] or bank
        if usable:
            p = usable[min(args.prompt_rank, len(usable)) - 1]
            prompt_wav = str(ROOT / "data/voices" / p["wav"])
            prompt_text = p["text"]
        wav_path = out_dir / f"{item['id']}_{sp}.wav"
        rec = {"id": item["id"], "speaker": sp, "chars": len(item["text"])}
        if args.force or not wav_path.exists():
            ann = annotations.get(item.get("source_key"))
            text, kwargs = route(args.engine, item["text"], ann)
            try:
                t0 = time.time()
                try:
                    audio, sr = eng.synth(ctx, text, prompt_wav, prompt_text, **kwargs)
                except TypeError:
                    audio, sr = eng.synth(ctx, text, prompt_wav, prompt_text)  # engine ignores the extra kwargs
                rec["synth_seconds"] = round(time.time() - t0, 2)
                write_wav(wav_path, np.asarray(audio, dtype=np.float32).reshape(-1), sr)
                rec["audio_seconds"] = round(len(audio) / sr, 2)
            except Exception as e:
                rec["error"] = f"{type(e).__name__}: {e}"
                traceback.print_exc()
        results["items"].append(rec)
        done += 1
        if done % 20 == 0:
            print(f"  {done} lines...")
        if args.limit and done >= args.limit:
            break

    ok = [r for r in results["items"] if "audio_seconds" in r]
    if ok:
        rtf = sum(r["synth_seconds"] for r in ok) / max(0.1, sum(r["audio_seconds"] for r in ok))
        results["rtf"] = round(rtf, 3)
        print(f"done: {len(ok)}/{done} ok, RTF={rtf:.2f} (lower is faster)")
    (out_dir / "results.json").write_text(json.dumps(results, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
