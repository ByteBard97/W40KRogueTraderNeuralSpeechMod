#!/usr/bin/env python3
"""List the segments of a mixed-cue render that need another take.

  /home/geoff/anaconda3/envs/roguetts/bin/python3 tools/render_corpus/redo_mixed.py --run mixed-seg [--jobs data/render/jobs_mixed.jsonl] [--out data/render/jobs_mixed_redo.jsonl]

A segment needs a redo when its render failed or its Whisper check flagged it (asr_bad, asr_truncated, asr_extra_words).
Render the redo file under a new run name, ASR-check it, then stitch with the new run listed first:
  render.py --engine voxcpm2 --name mixed-seg-redo --jobs data/render/jobs_mixed_redo.jsonl
  asr_check.py --run mixed-seg-redo
  stitch_mixed.py --jobs data/render/jobs_mixed.jsonl --runs mixed-seg-redo mixed-seg --out mixed-stitched
Nothing is deleted or overwritten.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

from stitch_mixed import BAD_FLAGS  # noqa: E402


def segments_to_redo(run_dir: Path) -> set[str]:
    bad: set[str] = set()
    for line in (run_dir / "manifest.jsonl").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        if r["status"] != "ok":
            bad.add(r["guid"])
    apath = run_dir / "asr.jsonl"
    if apath.exists():
        for line in apath.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            if BAD_FLAGS & set(r.get("flags", [])):
                bad.add(r["guid"])
    return bad


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--jobs", default=str(ROOT / "data/render/jobs_mixed.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "data/render/jobs_mixed_redo.jsonl"))
    a = ap.parse_args()
    bad = segments_to_redo(ROOT / "data/render" / a.run)
    rows = [l for l in Path(a.jobs).read_text(encoding="utf-8").splitlines() if json.loads(l)["guid"] in bad]
    Path(a.out).write_text("".join(r + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} segments to redo -> {a.out}")


if __name__ == "__main__":
    main()
