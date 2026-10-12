#!/usr/bin/env python3
"""Attribute unnamed (default_speaker) lines per conversation with a local llama-server.

Resumable: one JSON line per conversation in --out; conversations already there are skipped.

  python3 tools/npc_profile/run_roster.py --endpoint http://127.0.0.1:8091 --out data/npc_profile/roster_35b.jsonl \
      [--only AliveScout_dialogue ...] [--limit N]
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
from audit import audit  # noqa: E402
from confidence import field_confidence  # noqa: E402
from known import build_known, match  # noqa: E402
from roster import AGES, FX_NAMES, GENDERS, SPECIES, attribute  # noqa: E402

ENUMS = {"gender": GENDERS, "species": SPECIES, "age": AGES, "fx": FX_NAMES}


def make_complete(endpoint: str, temperature: float = 0.2, max_tokens: int = 3000):
    def complete(system: str, user: str, schema: dict) -> dict:
        body = {
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
            "temperature": temperature, "max_tokens": max_tokens,
            "response_format": {"type": "json_schema", "json_schema": {"name": "roster", "schema": schema, "strict": True}},
            "chat_template_kwargs": {"enable_thinking": False},
            "logprobs": True, "top_logprobs": 20,
        }
        req = urllib.request.Request(endpoint.rstrip("/") + "/v1/chat/completions", json.dumps(body).encode(),
                                     {"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=1800) as r:
            choice = json.loads(r.read())["choices"][0]
        out = json.loads(choice["message"]["content"])
        toks = (choice.get("logprobs") or {}).get("content")
        if toks:
            out["_conf"] = field_confidence(toks, ENUMS)
        return out
    return complete


def load_known(convs: list[dict]) -> dict:
    banks = set(json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8")))
    return build_known(convs, banks)


def annotate_known(res: dict, known: dict) -> None:
    for r in res["roster"]:
        m = match(r, known)
        if m:
            r["known_as"] = m


def load_targets() -> set[str]:
    jobs = (json.loads(ln) for ln in (ROOT / "data/render/jobs.jsonl").read_text(encoding="utf-8").splitlines())
    return {j["guid"] for j in jobs if j["speaker"] == "default_speaker"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--endpoint", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--reverse", action="store_true", help="work from the end of the list (a second worker on the same server)")
    ap.add_argument("--also-done", nargs="*", default=[], help="other workers' --out files; their conversations are skipped, re-read each step")
    ap.add_argument("--audit-threshold", type=float, default=0.8, help="field probability below this puts a conversation on the audit list")
    args = ap.parse_args()

    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    targets = load_targets()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(ln)["conversation"] for ln in out.read_text(encoding="utf-8").splitlines()} if out.exists() else set()
    todo = [c for c in convs if c["name"] not in done and any(l.get("text_key") in targets for l in c["lines"])
            and (not args.only or c["name"] in args.only)]
    todo.sort(key=lambda c: c["name"], reverse=args.reverse)
    if args.limit:
        todo = todo[: args.limit]
    known = load_known(convs)
    complete = make_complete(args.endpoint)
    t0 = time.time()
    def finished_elsewhere() -> set[str]:
        names: set[str] = set()
        for f in args.also_done:
            if Path(f).exists():
                names |= {json.loads(ln)["conversation"] for ln in Path(f).read_text(encoding="utf-8").splitlines() if ln.strip()}
        return names

    for i, c in enumerate(todo, 1):
        if c["name"] in finished_elsewhere():
            print(f"[{i}/{len(todo)}] reached work done by another worker; stopping", flush=True)
            break
        try:
            res = attribute(c, targets, complete)
            annotate_known(res, known)
            res["audit"] = audit(res, args.audit_threshold)
        except Exception as e:  # keep the overnight run going; failed conversations are retried on the next run
            print(f"FAILED {c['name']}: {e}", file=sys.stderr, flush=True)
            continue
        with out.open("a", encoding="utf-8") as f:
            f.write(json.dumps(res, ensure_ascii=False) + "\n")
        print(f"[{i}/{len(todo)}] {c['name']} roster={len(res['roster'])} lines={len(res['lines'])} score={res['audit']['score']}"
              f"{' REVIEW' if res['audit']['needs_review'] else ''} t={time.time()-t0:.0f}s", flush=True)


if __name__ == "__main__":
    main()
