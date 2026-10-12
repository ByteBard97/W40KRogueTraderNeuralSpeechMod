#!/usr/bin/env python3
"""Re-plan cues whose speaker was guessed wrong or left to the fallback voice, using ground truth and the reviewed labels.

  python3 tools/render_corpus/plan_overrides.py [--out data/render/jobs_overrides.jsonl]

Reads data/render/jobs.jsonl (read only). Sources, strongest first:
  1. data/npc_profile/runtime_truth.json: the speaker the game really used at runtime (played.jsonl).
  2. data/npc_profile/human_labels.json: reviewed conversations; a high/medium-confidence line whose reviewer roster entry maps (known.py)
     to a speaker that has a voice bank, or that is NARRATOR.
Only cues currently on the fallback voice (default_speaker / unit_guess) are touched. A cue with {n} narration becomes segment jobs
(plan_mixed.segment_jobs); others stay one job under their own guid. Cues already in jobs_mixed.jsonl are skipped. Never rewrites jobs.jsonl.
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
from plan_mixed import SEP, segment_jobs  # noqa: E402
from roster import conversation_lines  # noqa: E402

PRIORITY = {"emotion_bank": 0, "prompt_bank": 1, "narrator": 2, "fallback": 3}
GOOD = {"high", "medium"}
OVERRIDABLE = {"default_speaker", "unit_guess"}


def override_job(job: dict, speaker: str, ref_fn, narrator_ref: dict) -> dict | None:
    """The job re-pointed at `speaker`, or None when that speaker has no real voice (never trade one fallback for another)."""
    if speaker == "narrator":
        ref, source = dict(narrator_ref, emotion=None), "narrator"
    else:
        ref, source = ref_fn(speaker, (job.get("annotation") or {}).get("emotion"))
        if source not in ("emotion_bank", "prompt_bank"):
            return None
    return {**job, "speaker": speaker, "ref": ref, "voice_source": source, "priority": PRIORITY[source], "routed_from": "override"}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_overrides.jsonl"))
    a = ap.parse_args()
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    convs = json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))
    known = build_known(convs, set(prompts))
    wanted: dict[str, tuple[str, str]] = {}   # guid -> (speaker, source)
    truth_path = ROOT / "data/npc_profile/runtime_truth.json"
    if truth_path.is_file():
        for g, v in json.loads(truth_path.read_text(encoding="utf-8")).items():
            wanted[g] = (v["runtime_speaker"], "runtime")
    labels = json.loads((ROOT / "data/npc_profile/human_labels.json").read_text(encoding="utf-8"))["conversations"]
    for name, v in labels.items():
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
                wanted[g] = (sp, "review")
    libs: dict = {}
    ref_fn = lambda sp, emo: _ref(prompts, libs, ALIASES.get(sp, sp), emo, False)  # noqa: E731
    narrator, stats, rows = _narrator_ref(), Counter(), []
    mixed_path = ROOT / "data/render/jobs_mixed.jsonl"
    in_mixed = {json.loads(ln)["parent"] for ln in mixed_path.read_text(encoding="utf-8").splitlines()} if mixed_path.is_file() else set()
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        if job["guid"] not in wanted:
            continue
        speaker, src = wanted[job["guid"]]
        if job["speaker_kind"] not in OVERRIDABLE or job["voice_source"] != "fallback" or job["guid"] in in_mixed:
            stats["skipped_not_fallback"] += 1
            continue
        new = override_job(job, speaker, ref_fn, narrator)
        if new is None:
            stats["skipped_no_voice"] += 1
            continue
        segs = segment_jobs(new, narrator) if speaker != "narrator" else []
        rows += segs or [new]
        stats[f"{src}_{'segmented' if segs else 'whole'}"] += 1
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(wanted)} wanted overrides -> {len(rows)} jobs in {a.out}: {dict(stats)}")


if __name__ == "__main__":
    main()
