#!/usr/bin/env python3
"""Second pass over a recipe render: re-plan the pieces that came out flagged or misheard, as @fix takes the stitch prefers.

  python3 tools/render_corpus/recipe_followup.py --run cast-r2 --jobs data/render/jobs_cast_r2.jsonl --out-dir data/render/cast_r2_jobs --round 1

A piece is redone when its take is failed, overdriven / clipped, or Whisper heard truncation, extra words or a plain mismatch (not a
proper-name warning). The redo job has the same recipe with a new seed salt and more attempts, and the guid `<piece>@fix` (takes.pick tries
it first), so an accepted original never beats it. Writes <out-dir>/fix-<round>.jsonl, which a queue started with --watch picks up.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from takes import fix_guid

ROOT = Path(__file__).resolve().parents[2]
BAD_FLAGS = {"clipped", "overdriven", "piece_overdriven"}
BAD_ASR = {"asr_truncated", "asr_extra_words", "asr_bad"}
REDO_ATTEMPTS = 6


def lines(p: Path):
    return [json.loads(x) for x in p.read_text(encoding="utf-8").splitlines()] if p.is_file() else []


def flagged(run_dir: Path) -> dict[str, list[str]]:
    why: dict[str, list[str]] = {}
    asr = {a["guid"]: a for a in lines(run_dir / "asr.jsonl")}
    for r in lines(run_dir / "manifest.jsonl"):
        g = r["guid"]
        if g.endswith("@fix"):
            continue
        reasons = ["failed"] if r["status"] != "ok" else [f for f in r.get("flags", []) if f in BAD_FLAGS]
        reasons += [f for f in asr.get(g, {}).get("flags", []) if f in BAD_ASR]
        if reasons:
            why[g] = reasons
    return why


def plan(run_dir: Path, jobs: Path, round_: int) -> list[dict]:
    by_guid = {j["guid"]: j for j in lines(jobs)}
    rows = []
    for g, reasons in flagged(run_dir).items():
        j = by_guid.get(g)
        if not j or fix_guid(g) in {r["guid"] for r in lines(run_dir / "manifest.jsonl")}:
            continue
        recipe = {**j["recipe"], "seed": f"fix{round_}", "qc": {**(j["recipe"].get("qc") or {}), "attempts": REDO_ATTEMPTS}}
        rows.append({**j, "guid": fix_guid(g), "recipe": recipe, "redo_of": g, "redo_reason": reasons})
    return rows


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--round", type=int, default=1)
    a = ap.parse_args()
    rows = plan(ROOT / "data/render" / a.run, Path(a.jobs), a.round)
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    if rows:
        (out / f"fix-{a.round}.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} pieces to redo")
    for r in rows:
        print("  ", r["redo_of"][:12], r["redo_reason"], r["text"][:50])


if __name__ == "__main__":
    main()
