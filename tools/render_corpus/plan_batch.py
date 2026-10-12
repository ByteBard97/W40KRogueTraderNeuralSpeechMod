#!/usr/bin/env python3
"""Turn a re-plan (plan.py output written elsewhere) into queue-ready job files for one overnight batch.

  python3 tools/render_corpus/plan_batch.py --replan data/render/jobs_replan.jsonl --name routed \
      [--extra data/render/jobs_overrides.jsonl] [--base-export export_all_new] [--sources prompt_bank emotion_bank narrator]

Writes data/render/jobs_<name>_whole.jsonl (one job per cue), jobs_<name>_seg.jsonl (segment jobs for cues with {n} narration, via
plan_mixed.segment_jobs) and jobs_<name>.jsonl (both, for queue_server). Rows from --extra win over the re-plan. Cues already in the
base export or in jobs_mixed.jsonl are left out. Every row is forced to voxcpm2 (the Windows box has no qwen3 environment).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from plan import _narrator_ref  # noqa: E402
from plan_mixed import ENGINE, segment_jobs  # noqa: E402


def read(path: Path) -> list[dict]:
    return [json.loads(ln) for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--replan", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--extra", help="rows that override the re-plan for the same parent guid")
    ap.add_argument("--base-export", default="export_all_new")
    ap.add_argument("--skip-jobs", nargs="*", default=[], help="earlier batch job files; their cues are left out")
    ap.add_argument("--sources", nargs="+", default=["prompt_bank", "emotion_bank", "narrator"])
    a = ap.parse_args()
    render = ROOT / "data/render"
    exported = set(json.loads((render / a.base_export / "index.json").read_text(encoding="utf-8")))
    in_mixed = {j["parent"] for j in read(render / "jobs_mixed.jsonl")}
    skip = exported | in_mixed
    for f in a.skip_jobs:
        skip |= {j.get("parent", j["guid"]) for j in read(Path(f))}
    rows: dict[str, list[dict]] = {}
    if a.extra:
        for j in read(Path(a.extra)):
            rows.setdefault(j.get("parent", j["guid"]), []).append(j)
    narrator, stats = _narrator_ref(), Counter()
    for job in read(Path(a.replan)):
        g = job["guid"]
        if g in skip or g in rows or job["voice_source"] not in a.sources:
            continue
        segs = segment_jobs(job, narrator) if job["speaker"] != "narrator" else []
        rows[g] = segs or [job]
    whole, seg = [], []
    for g, js in rows.items():
        if g in skip:
            stats["skipped_already_done"] += 1
            continue
        for j in js:
            j = {**j, "engine": ENGINE}
            (seg if "parent" in j else whole).append(j)
    for suffix, data in (("whole", whole), ("seg", seg), ("", whole + seg)):
        p = render / (f"jobs_{a.name}_{suffix}.jsonl" if suffix else f"jobs_{a.name}.jsonl")
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in data), encoding="utf-8")
    chars = sum(len(j["text"]) for j in whole + seg)
    print(f"{a.name}: {len(whole)} whole-cue jobs, {len(seg)} segment jobs ({len({j['parent'] for j in seg})} cues); "
          f"~{chars / 15 / 3600:.1f} audio-h; skipped {stats['skipped_already_done']} already done")


if __name__ == "__main__":
    main()
