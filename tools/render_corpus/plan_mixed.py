#!/usr/bin/env python3
"""Plan segment jobs for mixed cues (speech plus narration): one render job per segment, in the right voice.

  python3 tools/render_corpus/plan_mixed.py [--out data/render/jobs_mixed.jsonl] [--all]

Reads data/render/jobs.jsonl (read only). A mixed cue becomes jobs "<guid>~<k>": speech segments use the cue's own voice and
annotation, narration segments use the BG3 narrator reference and no annotation. render.py runs the file unchanged;
asr_check.py then checks every segment on its own, and stitch_mixed.py joins the finished segments back into one take per cue.
By default only speakers that already have a real voice (emotion_bank / prompt_bank) are planned; --all adds the rest.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from jobs import bucket_of  # noqa: E402
from mixed import NARRATION, SPEECH, segments  # noqa: E402
from plan import _narrator_ref  # noqa: E402

SEP = "~"
VOICED_SOURCES = {"emotion_bank", "prompt_bank"}
ENGINE = "voxcpm2"   # one engine for every segment so speech and narration share a take character (short narrator lines already moved off qwen3)


def segment_jobs(job: dict, narrator_ref: dict) -> list[dict]:
    """Segment jobs for one planned cue job, or [] when the cue is not mixed."""
    segs = segments(job["src_text"])
    if {k for k, _ in segs} != {SPEECH, NARRATION}:
        return []
    out = []
    for k, (kind, text) in enumerate(segs):
        narr = kind == NARRATION
        out.append({
            **{f: job[f] for f in ("speaker_kind", "src_text") if f in job},
            "guid": f"{job['guid']}{SEP}{k}", "parent": job["guid"], "seg_index": k, "seg_count": len(segs), "seg_kind": kind,
            "speaker": "narrator" if narr else job["speaker"], "text": text,
            "engine": ENGINE, "bucket": bucket_of(job["guid"]),
            "priority": 2 if narr else job["priority"], "voice_source": "narrator" if narr else job["voice_source"],
            "ref": dict(narrator_ref, emotion=None) if narr else job["ref"],
            "annotation": None if narr else job.get("annotation"),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_mixed.jsonl"))
    ap.add_argument("--all", action="store_true", help="include speakers without a real voice yet")
    a = ap.parse_args()
    narrator = _narrator_ref()
    stats, rows = Counter(), []
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        if job["speaker"] == "narrator":
            continue
        if not a.all and job["voice_source"] not in VOICED_SOURCES:
            stats["skipped_unvoiced"] += 1
            continue
        segs = segment_jobs(job, narrator)
        if segs:
            rows += segs
            stats["cues"] += 1
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{stats['cues']} mixed cues -> {len(rows)} segment jobs in {a.out} (skipped {stats['skipped_unvoiced']} unvoiced cues)")


if __name__ == "__main__":
    main()
