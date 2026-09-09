#!/usr/bin/env python3
"""Score every catalog clip's audio with emotion2vec+ (audio-based SER), independent of the
LLM's text-based emotion prediction. Used to auto-flag agreement/disagreement for clip curation
(see tools/curate_emotion_clips and tools/emotion_coverage) rather than requiring a human to
listen to every candidate.

Requires .venv-tts (funasr, modelscope, torch+cuda already installed there).

Usage: python3 score_catalog_emotions.py [--speaker Abelard] [--limit 50]
Reads  data/voices/catalog.json
Writes data/voices/emotion_banks/ser_scores.json (event -> {label, score, all_scores})
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VOICES = ROOT / "data/voices"
OUT_PATH = VOICES / "emotion_banks/ser_scores.json"

LABEL_MAP = {  # emotion2vec+'s bilingual labels -> plain English
    "生气/angry": "angry", "厌恶/disgusted": "disgusted", "恐惧/fearful": "fearful",
    "开心/happy": "happy", "中立/neutral": "neutral", "其他/other": "other",
    "难过/sad": "sad", "吃惊/surprised": "surprised", "<unk>": "unknown",
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--speaker", default=None, help="only score this speaker's clips")
    ap.add_argument("--limit", type=int, default=0, help="cap number of clips scored (debugging)")
    args = ap.parse_args()

    from funasr import AutoModel
    model = AutoModel(model="iic/emotion2vec_plus_large", disable_pbar=True, disable_log=True)

    catalog = json.loads((VOICES / "catalog.json").read_text(encoding="utf-8"))
    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else {}

    events = [(e, c) for e, c in catalog.items()
              if not args.speaker or c.get("speaker") == args.speaker]
    todo = [(e, c) for e, c in events if e not in existing]
    print(f"{len(events)} catalog clips in scope, {len(todo)} not yet scored")

    t0 = time.time()
    for i, (event, c) in enumerate(todo, 1):
        wav_path = VOICES / c["wav"]
        if not wav_path.is_file():
            continue
        try:
            res = model.generate(str(wav_path), granularity="utterance", extract_embedding=False)[0]
        except Exception as e:  # noqa: BLE001 - keep going, one bad file shouldn't sink the run
            print(f"  SKIP {event}: {e}")
            continue
        scores = {LABEL_MAP.get(lbl, lbl): round(float(s), 4)
                  for lbl, s in zip(res["labels"], res["scores"])}
        top = max(scores, key=scores.get)
        existing[event] = {"label": top, "confidence": scores[top], "scores": scores}
        if i % 200 == 0 or i == len(todo):
            rate = i / (time.time() - t0)
            print(f"  {i}/{len(todo)} scored ({rate:.1f}/s)")
            OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
            OUT_PATH.write_text(json.dumps(existing, indent=1), encoding="utf-8")
        if args.limit and i >= args.limit:
            break

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_text(json.dumps(existing, indent=1), encoding="utf-8")
    print(f"done: {len(existing)} total clips scored -> {OUT_PATH}")


if __name__ == "__main__":
    main()
