#!/usr/bin/env python3
"""Whisper pass over a render run: transcribe every finished take and compare it with the text it was meant to say.

  python tools/render_corpus/asr_check.py --run win-narr-real-pilot            # one pass over what exists
  python tools/render_corpus/asr_check.py --run NAME --follow                  # keep up with a render that is still going

Writes data/render/<run>/asr.jsonl, one row per take: {guid, heard, wer, flags}. Resumable (skips guids already done).
Flags (see asr_compare.py): asr_warn, asr_bad, asr_spelled, asr_truncated, asr_extra_words. The audit page shows them.
Uses transformers Whisper so it runs wherever the TTS engine runs, on the same GPU alongside it.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/TtsSidecar"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from asr_compare import compare  # noqa: E402
import lexicon  # noqa: E402

SR = 16000


def load_16k(path: Path) -> np.ndarray:
    x, sr = sf.read(str(path), dtype="float32")
    return resample_16k(x, sr)


def resample_16k(x: np.ndarray, sr: int) -> np.ndarray:
    x = x.mean(1) if x.ndim > 1 else x
    if sr != SR:
        from math import gcd
        from scipy.signal import resample_poly
        g = gcd(sr, SR)
        x = resample_poly(x, SR // g, sr // g).astype("float32")
    return x


def make_asr(model: str, device: str):
    import torch
    from transformers import pipeline
    return pipeline("automatic-speech-recognition", model=model, device=device,
                    torch_dtype=torch.float16 if device.startswith("cuda") else torch.float32,
                    chunk_length_s=30, return_timestamps=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--follow", action="store_true", help="poll the manifest until --idle-exit seconds pass with nothing new")
    ap.add_argument("--idle-exit", type=int, default=600)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    run = ROOT / "data/render" / a.run
    out_path = run / "asr.jsonl"
    entries, _ = lexicon._load()
    terms = list(entries)
    asr = make_asr(a.model, a.device)
    done = {json.loads(l)["guid"] for l in out_path.open(encoding="utf-8")} if out_path.exists() else set()
    idle_since, n = time.time(), 0
    while True:
        rows = []
        if (run / "manifest.jsonl").exists():
            rows = [json.loads(l) for l in (run / "manifest.jsonl").open(encoding="utf-8")]
        todo = [r for r in rows if r.get("status") == "ok" and r["guid"] not in done and (run / "wav" / f"{r['guid']}.wav").exists()]
        if a.limit:
            todo = todo[: a.limit - n]
        for r in todo:
            heard = asr({"raw": load_16k(run / "wav" / f"{r['guid']}.wav"), "sampling_rate": SR},
                        generate_kwargs={"language": "en", "task": "transcribe"})["text"].strip()
            res = compare(r["text"], heard, terms)
            with out_path.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"guid": r["guid"], "heard": heard, **res}, ensure_ascii=False) + "\n")
            done.add(r["guid"])
            n += 1
            idle_since = time.time()
        if not a.follow or (a.limit and n >= a.limit) or time.time() - idle_since > a.idle_exit:
            break
        time.sleep(15)
    print(f"{n} takes checked -> {out_path}", flush=True)


if __name__ == "__main__":
    main()
