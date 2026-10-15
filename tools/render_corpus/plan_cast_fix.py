#!/usr/bin/env python3
"""Pieces of the cast render whose speaker contradicts ground truth (runtime_truth.json, reviewed human_labels.json): re-plan them
with the true speaker's own voice, as takes "<piece>@fix" queued into the running cast run (cast_jobs/redo-fix.jsonl); the stitch prefers them over the cast take.

  python3 tools/render_corpus/plan_cast_fix.py [--out data/render/cast_jobs/redo-fix.jsonl]

Only pieces whose speaker equals the cast speaker of a cue the truth attributes to someone else are re-pointed, and only when the true
speaker has a real voice bank (plan_overrides.override_job). takes.pick tries the @fix take first.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools/npc_profile"))

from known import build_known, match  # noqa: E402
from plan import ALIASES, _narrator_ref, _ref  # noqa: E402
from takes import fix_guid  # noqa: E402
from plan_overrides import GOOD, override_job  # noqa: E402


def truth(known: dict) -> dict[str, str]:
    wanted: dict[str, str] = {}
    tp = ROOT / "data/npc_profile/runtime_truth.json"
    if tp.is_file():
        for g, v in json.loads(tp.read_text(encoding="utf-8")).items():
            wanted[g] = v["runtime_speaker"]
    labels = json.loads((ROOT / "data/npc_profile/human_labels.json").read_text(encoding="utf-8"))["conversations"]
    for v in labels.values():
        if v["status"] != "reviewed":
            continue
        who = {}
        for r in v["roster"]:
            m = match(r, known)
            who[r["id"]] = m["name"] if isinstance(m, dict) and "name" in m else (m if isinstance(m, str) else None)
        for g, l in v["lines"].items():
            if g in wanted or l["confidence"] not in GOOD:
                continue
            sp = "narrator" if l["speaker"] == "NARRATOR" else who.get(l["speaker"])
            if sp and (sp == "narrator" or known.get(sp, {}).get("has_bank")):
                wanted[g] = sp
    return wanted


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs_cast_all.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/cast_jobs/redo-fix.jsonl"))
    a = ap.parse_args()
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    wanted = truth(build_known(convs, set(prompts)))
    libs: dict = {}
    ref_fn = lambda sp, emo: _ref(prompts, libs, ALIASES.get(sp, sp), emo, False)  # noqa: E731
    narrator, rows, stats = _narrator_ref(), [], Counter()
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        true = wanted.get(job["parent"])
        if not true or true == job["speaker"] or job.get("seg_kind") != "speech":
            continue
        cue_speakers = {json.loads(x)["speaker"] for x in Path(a.jobs).read_text(encoding="utf-8").splitlines() if json.loads(x)["parent"] == job["parent"]}
        if job["speaker"] == "narrator" and len(cue_speakers) > 1:        # a narration piece of a mixed cue stays narration
            continue
        new = override_job(job, true, ref_fn, narrator)
        if new is None:
            stats["true speaker has no voice"] += 1
            continue
        new.update(routed_from="cast-fix", guid=fix_guid(job["guid"]), fix_of=job["guid"])
        rows.append(new)
        stats[f"{job['speaker']} -> {true}"] += 1
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    # every piece of the fixed cues, with the true speaker on the fixed ones: the job list for the stitch into cast-fix-stitched
    fixed = {r["fix_of"]: r["speaker"] for r in rows}
    cues = {r["parent"] for r in rows}
    whole = [{**j, "speaker": fixed.get(j["guid"], j["speaker"])} for j in map(json.loads, Path(a.jobs).read_text(encoding="utf-8").splitlines()) if j["parent"] in cues]
    (ROOT / "data/render/jobs_cast_fix.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in whole), encoding="utf-8")
    print(f"{len(rows)} pieces -> {a.out}")
    for k, v in stats.most_common():
        print(f"  {v:4d}  {k}")


if __name__ == "__main__":
    main()
