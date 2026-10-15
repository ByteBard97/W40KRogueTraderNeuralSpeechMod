#!/usr/bin/env python3
"""Split cues that are too long for one VoxCPM2 generation into sentence chunks, as segment jobs.

  python3 tools/render_corpus/split_long.py --jobs data/render/jobs_extra_vox.jsonl --guids G [G ...] --out data/render/jobs_split.jsonl
  python3 tools/render_corpus/split_long.py --jobs data/render/jobs_extra_vox.jsonl --run extra --out data/render/jobs_split.jsonl

--run picks every job of that run that has no ok take and at least two failed rows (the queue's give-ups). Chunks are named
"<guid>~<k>" with the cue as parent, so render.py/queue_server.py render them unchanged and stitch_mixed.py joins them
(every chunk is seg_kind "speech" in the cue's own voice). Never edits the input job file.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNK_CHARS = 500     # well inside what renders (the longest single takes that worked were ~2,600 chars; a 3,900 one ran out of memory)
SENTENCE = re.compile(r"(?<=[.!?…])\s+|\n+")


def chunks(text: str, limit: int = CHUNK_CHARS) -> list[str]:
    """Greedy sentence packing: never cuts inside a sentence unless that one sentence exceeds the limit (then at a comma/space)."""
    out, cur = [], ""
    for s in (p.strip() for p in SENTENCE.split(text)):
        if not s:
            continue
        while len(s) > limit:
            cut = max(s.rfind(", ", 0, limit), s.rfind(" ", 0, limit))
            cut = cut if cut > 0 else limit
            if cur:
                out.append(cur)
                cur = ""
            out.append(s[:cut].strip())
            s = s[cut:].lstrip(", ")
        if cur and len(cur) + 1 + len(s) > limit:
            out.append(cur)
            cur = s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        out.append(cur)
    return out


def split_job(job: dict, limit: int = CHUNK_CHARS) -> list[dict]:
    parts = chunks(job["text"], limit)
    return [{**{f: job[f] for f in ("speaker_kind", "src_text") if f in job},
             "guid": f"{job['guid']}~{k}", "parent": job["guid"], "seg_index": k, "seg_count": len(parts), "seg_kind": "speech",
             "speaker": job["speaker"], "text": t, "engine": "voxcpm2", "bucket": job.get("bucket", 0),
             "priority": job.get("priority", 2), "voice_source": job["voice_source"], "ref": job["ref"],
             "annotation": job.get("annotation"), "respell": job.get("respell")} for k, t in enumerate(parts)]


def failed_guids(run_dir: Path) -> set[str]:
    ok, fails = set(), {}
    for line in (run_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["status"] == "ok":
            ok.add(r["guid"])
        else:
            fails[r["guid"]] = fails.get(r["guid"], 0) + 1
    return {g for g, n in fails.items() if g not in ok and n >= 2}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--guids", nargs="*", default=[])
    ap.add_argument("--run", help="also take every give-up in data/render/<run>")
    ap.add_argument("--out", required=True)
    ap.add_argument("--chunk-chars", type=int, default=CHUNK_CHARS)
    a = ap.parse_args()
    want = set(a.guids) | (failed_guids(ROOT / "data/render" / a.run) if a.run else set())
    rows = [j for j in map(json.loads, Path(a.jobs).read_text(encoding="utf-8").splitlines()) if j["guid"] in want]
    missing = want - {j["guid"] for j in rows}
    if missing:
        sys.exit(f"not in {a.jobs}: {sorted(missing)}")
    out = [seg for j in rows for seg in split_job(j, a.chunk_chars)]
    Path(a.out).write_text("".join(json.dumps(s, ensure_ascii=False) + "\n" for s in out), encoding="utf-8")
    print(f"{len(rows)} cues -> {len(out)} chunks in {a.out}")


if __name__ == "__main__":
    main()
