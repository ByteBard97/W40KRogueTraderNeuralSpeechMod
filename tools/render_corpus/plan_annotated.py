#!/usr/bin/env python3
"""Plan segment jobs for cues annotated in data/npc_profile/segments.json (several speakers in one cue).

  python3 tools/render_corpus/plan_annotated.py [--out data/render/jobs_annotated.jsonl] [--all]

Reads data/render/jobs.jsonl (read only). Annotated cue "G" becomes jobs "G~a0", "G~a1", ...: each segment uses its own speaker's
reference (a bank voice, a pool_<id> slot, or the narrator). Ids differ from plan_mixed's "G~k", so the two plans never collide.
Adjacent segments of one speaker are merged into one job (a short "Fly." take alone is unstable). render.py, asr_check.py and
stitch_mixed.py then run on the file unchanged. A cue where any speaking segment has no real voice is skipped (counted) unless
--all, and a cue whose annotation no longer matches the game text is reported and skipped.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))

from clean_text import clean_for_tts  # noqa: E402
from jobs import bucket_of, decode_binary  # noqa: E402
from plan import _narrator_ref, _ref  # noqa: E402
from plan_mixed import ENGINE, VOICED_SOURCES  # noqa: E402
from segment_annotations import load, validate  # noqa: E402

MIN_SPEECH_CHARS = 20   # shorter takes tend to fail take_problem or sound clipped; warn at plan time
PRIORITY = {"emotion_bank": 0, "prompt_bank": 1, "narrator": 2, "fallback": 3}
SEP = "~a"


def _merge_adjacent(segs: list[dict]) -> list[dict]:
    out: list[dict] = []
    for s in segs:
        if out and out[-1]["speaker"] == s["speaker"] and out[-1]["kind"] == s["kind"] and out[-1].get("voice") == s.get("voice"):
            out[-1] = {**out[-1], "text": f"{out[-1]['text']} {s['text']}"}
        else:
            out.append(dict(s))
    return out


def annotated_jobs(job: dict, entry: dict, narrator_ref: dict, ref_fn) -> list[dict]:
    segs, out = _merge_adjacent(entry["segments"]), []
    for k, s in enumerate(segs):
        narr = s["kind"] == "narration" or s["speaker"] == "narrator"
        if narr:
            speaker, ref, source = "narrator", dict(narrator_ref, emotion=None), "narrator"
        else:
            speaker = s["speaker"]
            emotion = (job.get("annotation") or {}).get("emotion") if speaker == job["speaker"] else None
            ref, source = ref_fn(s.get("voice", speaker), emotion)
        out.append({
            **{f: job[f] for f in ("speaker_kind", "src_text") if f in job},
            "guid": f"{job['guid']}{SEP}{k}", "parent": job["guid"], "seg_index": k, "seg_count": len(segs),
            "seg_kind": "narration" if narr else "speech", "speaker": speaker,
            "text": clean_for_tts(decode_binary(s["text"])), "engine": ENGINE, "bucket": bucket_of(job["guid"]),
            "priority": PRIORITY[source], "voice_source": source, "ref": ref,
            "annotation": (job.get("annotation") if speaker == job["speaker"] else None),
        })
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_annotated.jsonl"))
    ap.add_argument("--all", action="store_true", help="include cues with a speaker that has no real voice yet")
    a = ap.parse_args()
    annotations = load()
    texts = {}
    for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8")):
        for ln in c["lines"]:
            if ln.get("text_key") in annotations and ln.get("text"):
                texts[ln["text_key"]] = ln["text"]
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    libs: dict = {}
    narrator = _narrator_ref()
    stats, rows, planned, seen = Counter(), [], set(), set()
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        entry = annotations.get(job["guid"])
        if entry is None or job["guid"] in seen:
            continue
        seen.add(job["guid"])
        if job["guid"] not in texts:
            print(f"MISSING {job['guid']}: cue text not found in conversations.enGB.json")
            stats["missing"] += 1
            continue
        errors = validate(texts[job["guid"]], entry)
        if errors:
            print(f"STALE {job['guid']}: {errors[0]}")
            stats["stale"] += 1
            continue
        segs = annotated_jobs(job, entry, narrator, lambda sp, emo: _ref(prompts, libs, sp, emo, False))
        if not a.all and any(s["seg_kind"] == "speech" and s["voice_source"] not in VOICED_SOURCES for s in segs):
            stats["skipped_unvoiced"] += 1
            continue
        for s in segs:
            if s["seg_kind"] == "speech" and len(s["text"]) < MIN_SPEECH_CHARS:
                print(f"SHORT {s['guid']} ({s['speaker']}): {s['text']!r}")
        rows += segs
        planned.add(job["guid"])
    mixed_path = ROOT / "data/render/jobs_mixed.jsonl"
    in_mixed = {json.loads(ln)["parent"] for ln in mixed_path.read_text(encoding="utf-8").splitlines()} if mixed_path.is_file() else set()
    print(f"{len(planned & in_mixed)} of these cues are also in jobs_mixed.jsonl (rendered there in one voice; "
          "overlay_export.py: list annotated-stitched AFTER mixed-stitched, later runs win)")
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(planned)} annotated cues -> {len(rows)} segment jobs in {a.out}; skipped {stats['skipped_unvoiced']} unvoiced, "
          f"{stats['stale']} stale, {stats['missing']} missing text, {len(set(annotations) - seen)} not in jobs.jsonl")


if __name__ == "__main__":
    main()
