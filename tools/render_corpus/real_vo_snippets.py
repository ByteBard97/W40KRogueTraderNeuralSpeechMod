#!/usr/bin/env python3
"""For each lexicon word, cut short snippets of the game's own voice acting saying it, to settle pronunciations by ear.

  tools/scorer/.venv-scorer/bin/python tools/render_corpus/real_vo_snippets.py --out data/render/win-lexall [--per-word 3]

Uses data/voices/catalog.json (the extracted voiced lines). Whisper only locates the word in each clip (word timestamps);
the snippet is that word plus a little context either side. Writes <out>/real/<word>_<n>.wav and <out>/real.json
({word: [{wav, speaker, event, text, located}]}); the audit page shows them as "Real:" buttons next to our render.
"""
from __future__ import annotations

import argparse
import difflib
import json
import re
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).resolve().parent))
PAD = 0.7   # seconds of context kept either side of the word


def plain(t: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"\{[^}]*\}|<[^>]*>", "", t)).strip()


def norm(w: str) -> str:
    return re.sub(r"[^a-z0-9']", "", w.lower())


def locate(term: str, text: str, chunks: list[dict]):
    """(start, end) seconds of `term` in the clip, from Whisper word chunks, or None. The script text says where the term
    falls (its word index); Whisper may misspell invented names, so match by position first, then by closest spelling."""
    tw = [norm(w) for w in re.split(r"[\s\-]+", term)]
    words = [norm(w) for w in re.split(r"\s+", text) if norm(w)]
    heard = [(norm(c["text"]), c["timestamp"]) for c in chunks if norm(c["text"])]
    if not heard:
        return None
    idx = next((i for i in range(len(words) - len(tw) + 1) if all(words[i + k].startswith(tw[k]) or tw[k].startswith(words[i + k]) for k in range(len(tw)))), None)
    if idx is None:
        return None
    # candidate Whisper positions: same index (when word counts agree) plus every close spelling
    cands = []
    if len(heard) == len(words):
        cands.append(idx)
    cands += [i for i in range(len(heard) - len(tw) + 1)
              if difflib.SequenceMatcher(None, " ".join(h for h, _ in heard[i:i + len(tw)]), " ".join(tw)).ratio() >= 0.6]
    if not cands:
        i = min(range(len(heard)), key=lambda j: abs(j / len(heard) - idx / max(len(words), 1)))   # proportional fallback
        cands = [min(i, len(heard) - len(tw))]
    i = cands[0]
    start, end = heard[i][1][0], heard[i + len(tw) - 1][1][1]
    return (start, end) if start is not None and end is not None else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--per-word", type=int, default=3)
    ap.add_argument("--model", default="openai/whisper-small")
    ap.add_argument("--device", default="cpu")
    ap.add_argument("--shard", default="0/1", help="i/n: handle every n-th word, so n copies can run at once")
    ap.add_argument("--threads", type=int, default=0, help="torch threads for this process")
    ap.add_argument("--max-clip", type=float, default=12.0, help="ignore voiced lines longer than this many seconds")
    ap.add_argument("--only-missing", action="store_true", help="only words not yet in real.json; results go to real.extra.json")
    ap.add_argument("--merge", action="store_true", help="combine the real.<i>.json files of finished shards and exit")
    a = ap.parse_args()
    out = Path(a.out)
    if a.merge:
        merged = {}
        for f in sorted(out.glob("real.*.json")):
            merged.update(json.loads(f.read_text(encoding="utf-8")))
        (out / "real.json").write_text(json.dumps(merged, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{sum(len(v) for v in merged.values())} snippets for {len(merged)} words -> {out / 'real.json'}")
        return
    shard_i, shard_n = (int(x) for x in a.shard.split("/"))
    if a.threads:
        import torch
        torch.set_num_threads(a.threads)
    (out / "real").mkdir(parents=True, exist_ok=True)
    cat = json.loads((ROOT / "data/voices/catalog.json").read_text(encoding="utf-8"))
    lex = {k for k in json.loads((ROOT / "data/lexicon/lexicon.json").read_text(encoding="utf-8")) if not k.startswith("_")}
    by: dict[str, list] = {}
    for ev, e in cat.items():
        p = ROOT / "data/voices" / e["wav"]
        if not p.exists() or e["duration"] > a.max_clip:
            continue
        text = " ".join(plain(t["text"]) for t in e["texts"])
        for term in lex:
            if re.search(r"(?<![\w])" + re.escape(term) + r"(?![\w])", text, re.I):
                by.setdefault(term, []).append((e["duration"], ev, e["speaker"], p, text))
    if a.only_missing:
        have = json.loads((out / "real.json").read_text(encoding="utf-8")) if (out / "real.json").exists() else {}
        by = {t: r for t, r in by.items() if t not in have}
    from asr_check import make_asr
    asr = make_asr(a.model, a.device)
    result = {}
    for k, (term, rows) in enumerate(sorted(by.items())):
        if k % shard_n != shard_i:
            continue
        rows.sort()
        picked, seen_sp = [], set()
        for r in rows:   # shortest first, different speakers first
            if r[2] not in seen_sp or len(rows) <= a.per_word:
                picked.append(r)
                seen_sp.add(r[2])
            if len(picked) >= a.per_word:
                break
        result[term] = []
        for n, (dur, ev, sp, p, text) in enumerate(picked, 1):
            x, sr = sf.read(str(p), dtype="float32")
            mono = x.mean(1) if x.ndim > 1 else x
            from asr_check import resample_16k
            chunks = asr({"raw": resample_16k(mono, sr), "sampling_rate": 16000}, return_timestamps="word",
                         generate_kwargs={"language": "en", "task": "transcribe"})["chunks"]
            span = locate(term, text, chunks)
            if span:
                lo, hi = max(0, int((span[0] - PAD) * sr)), min(len(mono), int((span[1] + PAD) * sr))
                snip = mono[lo:hi].copy()
                f = min(int(0.03 * sr), len(snip) // 2)
                snip[:f] *= np.linspace(0, 1, f)
                snip[len(snip) - f:] *= np.linspace(1, 0, f)
            else:
                snip = mono
            name = f"{term.replace(' ', '_')}_{n}.wav"
            sf.write(str(out / "real" / name), snip, sr)
            result[term].append({"wav": f"real/{name}", "speaker": sp, "event": ev, "text": text, "located": bool(span)})
        print(term, [bool(r["located"]) for r in result[term]], flush=True)
    dest = out / ("real.extra.json" if a.only_missing else f"real.{shard_i}.json" if shard_n > 1 else "real.json")
    dest.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{sum(len(v) for v in result.values())} snippets for {len(result)} words -> {dest}")


if __name__ == "__main__":
    main()
