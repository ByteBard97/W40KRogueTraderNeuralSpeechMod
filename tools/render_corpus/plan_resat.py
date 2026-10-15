#!/usr/bin/env python3
"""Plan a recipe re-render of every piece whose raw take is saturated (data/render/audit/raw_saturation_scan.json).

  python3 tools/render_corpus/plan_resat.py --recipe resat-r2 [--out data/render/jobs_resat_r2.jsonl]

The overdrive scan on exported clips misses stitched cues (the stitch scales a saturated piece down, which hides the flat tops), so
the scan is run on the raw pieces of each run. Each piece keeps its guid, speaker and reference; the recipe adds sentence splitting,
CFG/seed retries and quality control. Pieces already replaced by a newer run are skipped, and no job may use prompts/narrator/ (Gale).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from plan_recipe import load_recipe

ROOT = Path(__file__).resolve().parents[2]
R = ROOT / "data/render"
JOBS_OF_RUN = {"cast": ["jobs_cast_all.jsonl"], "designed": ["jobs_designed_seg.jsonl", "jobs_designed_whole.jsonl"],
               "narr-real": ["jobs_replan2.jsonl"], "mixed-seg": ["jobs_mixed.jsonl"],
               "routed": ["jobs_routed_seg.jsonl", "jobs_routed_whole.jsonl"]}
NEWER_RUNS = ("cast-r2", "mixed-seg-redo", "night-redo", "q21", "extra-r2")     # a piece one of these already re-rendered is not planned again


def ok_guids(run: str) -> set[str]:
    p = R / run / "manifest.jsonl"
    if not p.is_file():
        return set()
    rows = (json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines())
    return {r["guid"].removesuffix("@fix") for r in rows if r.get("status") == "ok"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--recipe", required=True)
    ap.add_argument("--scan", default=str(R / "audit/raw_saturation_scan.json"))
    ap.add_argument("--out", default=str(R / "jobs_resat_r2.jsonl"))
    a = ap.parse_args()
    recipe = load_recipe(a.recipe, ROOT / "data/studio/lab/recipes.json")
    newer = set().union(*(ok_guids(r) for r in NEWER_RUNS))
    want: dict[str, str] = {}
    for run, guid, _n, _dur in json.loads(Path(a.scan).read_text(encoding="utf-8")):
        if run in JOBS_OF_RUN and guid not in newer:
            want[guid] = run
    rows, seen = [], set()
    for run in sorted(set(want.values())):
        for name in JOBS_OF_RUN[run]:
            for ln in (R / name).read_text(encoding="utf-8").splitlines():
                j = json.loads(ln)
                if want.get(j["guid"]) == run and j["guid"] not in seen:
                    seen.add(j["guid"])
                    rows.append({**j, "recipe": recipe, "respell": False, "routed_from": "recipe:" + recipe["name"]})
    bad = [r["guid"] for r in rows if "prompts/narrator/" in r["ref"]["wav"] or not (ROOT / r["ref"]["wav"]).is_file()]
    if bad:
        raise SystemExit(f"refusing: {len(bad)} jobs with a Gale or missing reference, e.g. {bad[:3]}")
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(want) - len(seen)} planned pieces have no job row (skipped)")
    print(f"{len(want)} saturated pieces to plan, {len(rows)} jobs, {sum(len(r['text']) for r in rows)} chars -> {a.out}")
    print("by run:", {k: sum(1 for g in seen if want[g] == k) for k in sorted(set(want.values()))})


if __name__ == "__main__":
    main()
