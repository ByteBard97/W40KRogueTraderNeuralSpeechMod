#!/usr/bin/env python3
"""Expand the cues in data/render/chorus.json into one render job per voice.

  python3 tools/render_corpus/plan_chorus.py [--spec data/render/chorus.json] [--out data/render/jobs_chorus.jsonl]

Each cue "G" with voices [v0, v1, ...] becomes jobs "G~h0", "G~h1", ... with parent "G": the same text in each voice. Workers render them like any
other job (no worker change). mix_chorus.py then aligns the takes of a parent and sums them into one clip. A mixed cue (speech plus narration) keeps
only its speech text here (print a warning); give an explicit "text" in the spec to choose what the group says.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
sys.path.insert(0, str(ROOT / "tools"))

from jobs import bucket_of  # noqa: E402
from plan import ALIASES, _ref  # noqa: E402
from plan_mixed import ENGINE, SPEECH, segments  # noqa: E402

PRIORITY = {"emotion_bank": 0, "prompt_bank": 1, "narrator": 2, "fallback": 3}


def chorus_jobs(job: dict, voices: list[str], text: str, ref_fn) -> list[dict]:
    out = []
    for k, v in enumerate(voices):
        ref, source = ref_fn(v, None)
        if source not in ("emotion_bank", "prompt_bank"):
            raise SystemExit(f"voice {v!r} has no registered reference clip (prompts.json)")
        out.append({**{f: job[f] for f in ("speaker_kind", "src_text") if f in job},
                    "guid": f"{job['guid']}~h{k}", "parent": job["guid"], "seg_index": k, "seg_count": len(voices), "seg_kind": "speech",
                    "speaker": v, "text": text, "engine": ENGINE, "bucket": bucket_of(job["guid"]), "priority": PRIORITY[source],
                    "voice_source": source, "ref": ref, "annotation": None, "routed_from": "chorus", "chorus": True})
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--spec", default=str(ROOT / "data/render/chorus.json"))
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_chorus.jsonl"))
    a = ap.parse_args()
    spec = json.loads(Path(a.spec).read_text(encoding="utf-8"))
    defaults, cues = spec["defaults"], spec["cues"]
    prompts = json.loads((ROOT / "data/voices/prompts/prompts.json").read_text(encoding="utf-8"))
    libs: dict = {}
    ref_fn = lambda v, e: _ref(prompts, libs, ALIASES.get(v, v), e, False)  # noqa: E731
    wanted, rows = set(cues), []
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        job = json.loads(line)
        if job["guid"] not in wanted:
            continue
        wanted.discard(job["guid"])
        c = cues[job["guid"]]
        text = c.get("text")
        if text is None:
            segs = segments(job["src_text"])
            kinds = {k for k, _ in segs}
            if SPEECH in kinds and len(kinds) > 1:
                print(f"WARNING {job['guid']}: mixed cue, the group says only the speech part (set 'text' to override)")
                text = " ".join(t for k, t in segs if k == SPEECH)
            else:
                text = job["text"]
        rows += chorus_jobs(job, c.get("voices") or defaults["voices"], text, ref_fn)
    if wanted:
        sys.exit(f"not in jobs.jsonl: {sorted(wanted)}")
    Path(a.out).write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(cues)} chorus cues -> {len(rows)} jobs in {a.out}")


if __name__ == "__main__":
    main()
