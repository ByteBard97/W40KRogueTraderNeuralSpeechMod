#!/usr/bin/env python3
"""Annotate Rogue Trader dialogue with emotion/delivery labels, one conversation per LLM call.

Usage:
  annotate.py --backend ollama --model qwen3:14b [--limit 20] [--shard 0/2] [--review]

Reads  data/conversations.enGB.json
Writes data/annotations/cache/<conv_guid>.json   (one file per conversation, resumable)
       data/annotations/annotations.enGB.json    (merged guid -> record, run with --merge)

Design notes (lessons from Alexandria):
  - constrained JSON schema, low temperature
  - every input guid must come back exactly once, else the whole chunk is retried split in half
  - a non-stop finish reason is a hard failure (issue #81: silent truncation)
  - narration segments {n}..{/n} are annotated as part of the line but the instruct should
    describe the SPOKEN part; pure-narration lines get the 'narrator' speaker
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from backends import BACKENDS, BackendError  # noqa: E402
from schema import EMOTIONS, JSON_SCHEMA, NONVERBALS, PACES  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent.parent
CACHE = ROOT / "data/annotations/cache"

SYSTEM = f"""You are annotating lines from the dark-gothic sci-fi CRPG Warhammer 40,000: Rogue Trader
for expressive text-to-speech. For EVERY line you receive, output one record:
- emotion: one of {EMOTIONS}
- intensity: 0.0-1.0 (0.2 subtle, 0.5 clear, 0.9 extreme)
- pace: one of {PACES}
- nonverbal: subset of {NONVERBALS} - vocal sounds the actor should ADD (usually empty; use only
  when the text or stage direction clearly implies it, e.g. laughing, a sigh, a gasp)
- instruct: one sentence of voice direction for the SPOKEN words (tone, delivery, subtext).
  Never describe physical actions; only how the voice sounds.
Text in {{n}}...{{/n}} is narrator stage direction: use it as evidence for the speaker's state,
but direct the spoken words. Lines whose speaker is "narrator" are read by a calm audiobook
narrator - annotate them with restrained emotion (intensity <= 0.4) unless the prose demands more.
Return JSON only."""


def line_hash(text: str) -> str:
    return hashlib.sha1(text.encode()).hexdigest()[:12]


def conv_payload(conv: dict) -> tuple[str, list[dict]]:
    """Render a conversation as a numbered script; return (user_prompt, lines)."""
    lines = []
    for l in conv.get("lines", []):
        if "guid" not in l or not l.get("text") or not l.get("text_key"):
            continue
        sp = l.get("speaker") or {}
        who = sp.get("name") or sp.get("kind") or "unknown"
        lines.append({"guid": l["text_key"], "speaker": who, "text": l["text"],
                      "animation": l.get("animation"), "kind": l["kind"]})
    if not lines:
        return "", []
    script = []
    for i, l in enumerate(lines):
        anim = f" (animation: {l['animation']})" if l.get("animation") not in (None, "None") else ""
        script.append(f"[{l['guid']}] {l['speaker']}{anim}: {l['text']}")
    user = (f"Conversation '{conv.get('name')}' ({len(lines)} lines). Annotate every line.\n\n"
            + "\n".join(script))
    return user, lines


def validate(result: dict, lines: list[dict]) -> list[dict]:
    got = {r["guid"]: r for r in result.get("lines", [])}
    want = [l["guid"] for l in lines]
    missing = [g for g in want if g not in got]
    if missing:
        raise BackendError(f"missing {len(missing)} guids (first: {missing[0]})")
    out = []
    for l in lines:
        r = got[l["guid"]]
        r["emotion"] = r["emotion"] if r["emotion"] in EMOTIONS else "neutral"
        r["pace"] = r["pace"] if r["pace"] in PACES else "normal"
        r["nonverbal"] = [n for n in r.get("nonverbal", []) if n in NONVERBALS]
        r["intensity"] = max(0.0, min(1.0, float(r.get("intensity", 0.3))))
        r["text_hash"] = line_hash(l["text"])
        out.append(r)
    return out


def annotate_conv(conv: dict, backend, model: str) -> list[dict] | None:
    user, lines = conv_payload(conv)
    if not lines:
        return []
    # split recursively if the model can't handle the whole conversation
    def go(lines_subset: list[dict], depth=0) -> list[dict]:
        script = "\n".join(f"[{l['guid']}] {l['speaker']}: {l['text']}" for l in lines_subset)
        user = f"Annotate every line.\n\n{script}"
        try:
            result = backend(SYSTEM, user, JSON_SCHEMA, model=model)
            return validate(result, lines_subset)
        except BackendError:
            if depth >= 3 or len(lines_subset) <= 2:
                raise
            mid = len(lines_subset) // 2
            return go(lines_subset[:mid], depth + 1) + go(lines_subset[mid:], depth + 1)
    return go(lines)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", default="ollama", choices=list(BACKENDS))
    ap.add_argument("--model", default="qwen3:14b")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--shard", default="0/1", help="i/n - annotate conversations where hash%%n==i")
    ap.add_argument("--merge", action="store_true", help="merge cache into annotations.enGB.json and exit")
    ap.add_argument("--input", default=None, help="override conversations JSON (default data/conversations.enGB.json)")
    ap.add_argument("--cache-dir", default=None, help="override cache dir (default data/annotations/cache)")
    ap.add_argument("--host", default="http://localhost:11434", help="ollama host")
    args = ap.parse_args()

    cache_dir = Path(args.cache_dir) if args.cache_dir else CACHE
    cache_dir.mkdir(parents=True, exist_ok=True)
    convs = json.load(open(args.input or (ROOT / "data/conversations.enGB.json"), encoding="utf-8"))

    if args.merge:
        merged = {}
        for f in cache_dir.glob("*.json"):
            for r in json.load(open(f, encoding="utf-8"))["lines"]:
                merged[r["guid"]] = {k: v for k, v in r.items() if k != "guid"}
        out = ROOT / "data/annotations/annotations.enGB.json"
        out.write_text(json.dumps(merged, ensure_ascii=False, indent=0), encoding="utf-8")
        print(f"merged {len(merged)} annotations from {len(list(cache_dir.glob('*.json')))} conversations -> {out}")
        return

    shard_i, shard_n = (int(x) for x in args.shard.split("/"))
    raw_backend = BACKENDS[args.backend]
    if args.backend == "ollama":
        backend = lambda system, user, schema, model: raw_backend(system, user, schema, model=model, host=args.host)  # noqa: E731
    else:
        backend = raw_backend
    done = failed = 0
    t0 = time.time()
    for conv in convs:
        if int(conv["guid"][:8], 16) % shard_n != shard_i:
            continue
        cache_file = cache_dir / f"{conv['guid']}.json"
        if cache_file.exists():
            continue
        try:
            recs = annotate_conv(conv, backend, args.model)
            cache_file.write_text(json.dumps({"conv": conv["guid"], "model": args.model,
                                              "lines": recs}, ensure_ascii=False), encoding="utf-8")
            done += 1
        except (BackendError, Exception) as e:  # noqa: BLE001 - log and continue
            failed += 1
            print(f"FAIL {conv['guid']} ({conv.get('name')}): {e}", file=sys.stderr)
        if done and done % 10 == 0:
            rate = done / (time.time() - t0) * 3600
            print(f"{done} conversations done ({failed} failed), {rate:.0f}/hour")
        if args.limit and done >= args.limit:
            break
    print(f"finished: {done} done, {failed} failed")


if __name__ == "__main__":
    main()
