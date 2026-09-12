# tools/audio_emotion_labeling/label.py
"""Resumable batch runner: labels catalog clips with a chosen audio-LLM backend.

Usage (run from inside the matching venv):
  .venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --pilot
  .venv-ultravox/bin/python label.py --backend ultravox --mode audio+text --pilot --limit 5
  .venv-qwen2audio/bin/python label.py --backend qwen2audio --mode audio --speaker Argenta --limit 20

Writes data/voices/emotion_banks/audio_llm_labels.json, keyed
event -> backend -> mode -> prompt_hash -> entry. Safe to interrupt and re-run: already
labeled (event, backend, mode, prompt_hash) combinations are skipped.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Iterator

from parsing import parse_model_response
from prompt import build_prompt

ROOT = Path(__file__).resolve().parent.parent.parent
VOICES = ROOT / "data/voices"
OUT_PATH = VOICES / "emotion_banks/audio_llm_labels.json"


def iter_labels(catalog: dict, existing: dict, backend_name: str, mode: str,
                 prompt_hash_value: str, generate_fn: Callable[[str, str], str],
                 vocab: dict, backend_meta: dict,
                 event_filter: set[str] | None = None) -> Iterator[tuple[str, dict]]:
    for event, clip in catalog.items():
        if event_filter is not None and event not in event_filter:
            continue
        already = (existing.get(event, {}).get(backend_name, {})
                   .get(mode, {}).get(prompt_hash_value))
        if already:
            continue

        transcript = clip["texts"][0]["text"] if mode == "audio+text" else None
        prompt_text = build_prompt(vocab, mode, transcript)

        t0 = time.monotonic()
        raw = generate_fn(clip["wav"], prompt_text)
        latency = time.monotonic() - t0

        parsed = parse_model_response(raw)
        entry = {
            "labels": parsed["labels"] if parsed else [],
            "notes": parsed["notes"] if parsed else "",
            "parse_ok": parsed is not None,
            "raw_response": raw,
            **backend_meta,
            "latency_s": round(latency, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        yield event, entry


def _atomic_write(path: Path, data: dict) -> None:
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, path)


SAVE_EVERY = 25  # re-serializing the whole file after every single clip is wasted work
                  # at full-corpus scale; batching costs at most this many clips on a crash


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", required=True, choices=["qwen2audio", "ultravox"])
    ap.add_argument("--mode", required=True, choices=["audio", "audio+text"])
    ap.add_argument("--pilot", action="store_true",
                    help="restrict to exactly the ground-truth events in curation.json")
    ap.add_argument("--speaker", default=None, help="restrict to one speaker's catalog clips")
    ap.add_argument("--limit", type=int, default=0, help="cap number of clips processed (debugging)")
    args = ap.parse_args()

    catalog = json.loads((VOICES / "catalog.json").read_text(encoding="utf-8"))
    if args.pilot:
        curation = json.loads((VOICES / "emotion_banks/curation.json").read_text(encoding="utf-8"))
        event_filter = {event for speaker_clips in curation.values()
                         for event, rec in speaker_clips.items() if rec.get("emotion")}
    elif args.speaker:
        event_filter = {event for event, clip in catalog.items()
                         if clip.get("speaker") == args.speaker}
    else:
        event_filter = None

    from vocab import load_vocab
    vocab = load_vocab(VOICES / "emotion_banks/custom_emotions.json")
    from prompt import prompt_hash
    ph = prompt_hash(vocab, args.mode)

    if args.backend == "qwen2audio":
        from backends.qwen2audio import generate as backend_generate
        from backends.qwen2audio import load_model
    else:
        from backends.ultravox import generate as backend_generate
        from backends.ultravox import load_model

    model, processor, backend_meta = load_model()
    print(f"loaded {args.backend}: {backend_meta}")

    def generate_fn(wav_path: str, prompt_text: str) -> str:
        return backend_generate(model, processor, str(VOICES / wav_path), prompt_text)

    existing = json.loads(OUT_PATH.read_text(encoding="utf-8")) if OUT_PATH.exists() else {}

    count = 0
    for event, entry in iter_labels(catalog, existing, args.backend, args.mode, ph,
                                     generate_fn, vocab, backend_meta, event_filter):
        existing.setdefault(event, {}).setdefault(args.backend, {}).setdefault(args.mode, {})[ph] = entry
        count += 1
        print(f"[{count}] {event}: {entry['labels']} (parse_ok={entry['parse_ok']}, "
              f"{entry['latency_s']}s)")
        if count % SAVE_EVERY == 0:
            _atomic_write(OUT_PATH, existing)
        if args.limit and count >= args.limit:
            break

    _atomic_write(OUT_PATH, existing)  # final flush, covers the last partial batch
    print(f"done: {count} clips labeled")


if __name__ == "__main__":
    main()
