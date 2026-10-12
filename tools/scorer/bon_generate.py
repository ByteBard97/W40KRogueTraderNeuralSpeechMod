#!/usr/bin/env python3
"""Resumable best-of-N take generator for a character's unvoiced lines (voxcpm2).

Generates in ROUNDS: round r renders take r for every line, so an interrupted or partial run
still leaves every line with at least one take and later rounds only add candidates.
Reference clip per line = emotion-matched clip from ReferenceLibrary (same as the bake-off).

Run: /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/scorer/bon_generate.py \
         [--takes 6] [--cfg 3.0] [--limit-lines N] [--speaker Abelard]
Output: data/bon/<speaker>/manifest.jsonl (one JSON line per take) + wav/<guid>/take<k>.wav
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools"))
sys.path.insert(0, str(ROOT / "tools/tts_bakeoff"))
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))
from annotation_bridge import route  # noqa: E402
from lexicon import respell  # noqa: E402
from run_abelard_emotion_samples import load_labeled_lines  # noqa: E402
from select_reference_clip import ReferenceLibrary  # noqa: E402
import tts_engines.voxcpm2 as eng  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default="Abelard")
    ap.add_argument("--takes", type=int, default=6)
    ap.add_argument("--cfg", type=float, default=3.0)
    ap.add_argument("--timesteps", type=int, default=10)
    ap.add_argument("--limit-lines", type=int, default=0)
    ap.add_argument("--out-name", default=None, help="output dir name under data/bon (default: speaker); use for setting sweeps")
    ap.add_argument("--guids-file", default=None, help="JSON list of guids: only generate these lines (retake rounds)")
    args = ap.parse_args()

    out = ROOT / "data/bon" / (args.out_name or args.speaker)
    (out / "wav").mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.jsonl"
    done = set()
    if mpath.exists():
        for ln in mpath.read_text(encoding="utf-8").splitlines():
            r = json.loads(ln)
            done.add((r["guid"], r["take"]))

    lines = load_labeled_lines(10**6, 42)
    lines.sort(key=lambda r: r["guid"])
    if args.guids_file:
        wanted = set(json.loads(Path(args.guids_file).read_text(encoding="utf-8")))
        lines = [r for r in lines if r["guid"] in wanted]
    if args.limit_lines:
        lines = lines[: args.limit_lines]
    lib = ReferenceLibrary(args.speaker)
    print(f"{len(lines)} lines x {args.takes} takes; {len(done)} takes already done", flush=True)

    model = eng.load()
    t0, n = time.time(), 0
    for take in range(args.takes):
        for rec in lines:
            guid = rec["guid"]
            if (guid, take) in done:
                continue
            ref = lib.find(rec["emotion"])
            annotation = {k: rec[k] for k in ("emotion", "intensity", "pace", "nonverbal", "instruct")}
            text, _ = route("voxcpm2", respell(rec["text"]), annotation)
            wav_path = out / "wav" / guid / f"take{take}.wav"
            wav_path.parent.mkdir(exist_ok=True)
            try:
                instruct = annotation.get("instruct")
                full = f"({instruct}){respell(rec['text'])}" if instruct else respell(rec["text"])
                wav = model.generate(text=full, reference_wav_path=ref["wav"], cfg_value=args.cfg,
                                     inference_timesteps=args.timesteps, retry_badcase=False)
                wav = np.asarray(wav, dtype=np.float32).reshape(-1)
                sr = model.tts_model.sample_rate
                sf.write(str(wav_path), wav, sr)
            except Exception as e:  # keep the queue moving; the failure is recorded and retried next run
                print(f"FAILED {guid} take{take}: {e}", flush=True)
                traceback.print_exc()
                continue
            row = {"guid": guid, "take": take, "text": rec["text"], "emotion": rec["emotion"],
                   "instruct": annotation.get("instruct"), "cfg": args.cfg, "timesteps": args.timesteps,
                   "reference": {"event": ref["event"], "wav": ref["wav"], "emotion": ref.get("matched_emotion")},
                   "wav": str(wav_path.relative_to(ROOT)), "seconds": round(len(wav) / sr, 2)}
            with open(mpath, "a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
            if n % 10 == 0:
                print(f"take{take}: {n} new in {time.time()-t0:.0f}s ({(time.time()-t0)/n:.1f}s each)", flush=True)
    print("done", n, "new takes", flush=True)


if __name__ == "__main__":
    main()
