#!/usr/bin/env python3
"""Run the per-line delivery stage (segment.py) with a local llama-server.

  python3 tools/npc_profile/run_segment.py --endpoint http://127.0.0.1:8091 --out data/npc_profile/seg_test.jsonl \
      --texts "planets do not have faces" "Warden Casteglia"           # by text substring (testing)
  python3 tools/npc_profile/run_segment.py --endpoint ... --out ... --priority 3 --min-chars 450   # a real batch

Resumable (one JSON line per line guid). Speaker info comes from the job, or from --roster results when given.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
import segment as S  # noqa: E402
from gather_evidence import clean  # noqa: E402


def make_complete(endpoint: str, temperature: float = 0.2, max_tokens: int = 1200):
    def complete(system: str, user: str, n_sentences: int) -> dict:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature, "max_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {"name": "segments", "schema": S.SCHEMA, "strict": True}},
            "chat_template_kwargs": {"enable_thinking": False}, "logprobs": True, "top_logprobs": 20,
        }
        req = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            choice = json.loads(r.read())["choices"][0]
        out = json.loads(choice["message"]["content"])
        toks = (choice.get("logprobs") or {}).get("content")
        if toks:
            S.attach_confidence(out, S.segment_confidence(toks, n_sentences))
        return out
    return complete


def context_index(convs: list[dict]) -> dict[str, tuple[dict, int]]:
    """text_key -> (conversation, position among its text lines)."""
    idx = {}
    for c in convs:
        pos = 0
        for ln in c["lines"]:
            if ln.get("text") and ln.get("kind") in ("cue", "answer"):
                idx.setdefault(ln["text_key"], (c, pos))
                pos += 1
    return idx


def neighbours(conv: dict, pos: int, before: int = 3, after: int = 1) -> tuple[list[str], list[str]]:
    texts = []
    for ln in conv["lines"]:
        if ln.get("text") and ln.get("kind") in ("cue", "answer"):
            who = "PLAYER" if (ln.get("speaker") or {}).get("kind") == "player" else ((ln.get("speaker") or {}).get("name") or "?")
            texts.append(f"[{who}] {clean(ln['text'])}")
    return texts[max(0, pos - before):pos], texts[pos + 1:pos + 1 + after]


def pick_jobs(jobs: list[dict], args) -> list[dict]:
    sel = [j for j in jobs if '"' in j["src_text"] or "“" in j["src_text"]]
    if getattr(args, "guids_from", None):
        g = json.loads(Path(args.guids_from).read_text(encoding="utf-8"))
        want = set(g if isinstance(g, list) else g.keys())
        sel = [j for j in jobs if j["guid"] in want]
        sel.sort(key=lambda j: j["guid"])
        return sel[: args.limit] if args.limit else sel
    if args.texts:
        sel = [j for j in jobs if any(t in j["text"] for t in args.texts)]
    else:
        sel = [j for j in sel if j["priority"] in args.priority and len(j["text"]) >= args.min_chars]
    sel.sort(key=lambda j: j["guid"])
    return sel[: args.limit] if args.limit else sel


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--texts", nargs="*")
    ap.add_argument("--priority", type=int, nargs="*", default=[3])
    ap.add_argument("--min-chars", type=int, default=S.MIN_LINE_CHARS)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--guids-from", help="JSON file whose keys (or list items) are line guids; bypasses the priority/length filters")
    args = ap.parse_args()

    jobs = [json.loads(ln) for ln in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines()]
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    idx = context_index(convs)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(ln)["guid"] for ln in out.read_text(encoding="utf-8").splitlines()} if out.exists() else set()
    todo = [j for j in pick_jobs(jobs, args) if j["guid"] not in done]
    complete = make_complete(args.endpoint)
    t0 = time.time()
    for i, j in enumerate(todo, 1):
        sents = S.split_sentences(j["text"])
        conv, pos = idx.get(j["guid"], ({"name": "?", "lines": []}, 0))
        before, after = neighbours(conv, pos)
        # the splitting option only exists for long lines; short ones get a single-sentence-group prompt anyway
        user = S.build_prompt(conv["name"], j["speaker"], sents, before, after)
        try:
            raw = complete(S.SYSTEM, user, len(sents))
            segs = S.validate(raw, sents, S.MIN_SEGMENT_CHARS if len(j["text"]) >= S.MIN_LINE_CHARS else 10**9)
        except Exception as e:
            print(f"FAILED {j['guid']}: {e}", file=sys.stderr, flush=True)
            continue
        rec = {"guid": j["guid"], "speaker": j["speaker"], "chars": len(j["text"]), "sentences": len(sents), "old": j["annotation"],
               "segments": segs, "review": S.review_reasons(segs)}
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(todo)}] {j['guid'][:8]} {len(j['text'])}ch -> {len(segs)} segment(s) t={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
