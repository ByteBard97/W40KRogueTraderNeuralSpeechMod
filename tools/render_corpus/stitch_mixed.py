#!/usr/bin/env python3
"""Join finished segment renders of mixed cues into one take per cue.

  python3 tools/render_corpus/stitch_mixed.py --jobs data/render/jobs_mixed.jsonl --runs NAME [NAME ...] --out mixed-stitched

Segment wavs come from data/render/<run>/wav/<guid>~<k>.wav (render.py output). A cue is stitched only when every one of its
segments finished ok, has no take problem and no ASR flag (asr_bad, asr_truncated, asr_extra_words in the run's asr.jsonl);
anything else is listed so those segments can be re-rendered. Writes data/render/<out>/wav/<guid>.wav and manifest.jsonl,
which merge.py reads like any other run. Never overwrites or deletes.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))

sys.path.insert(0, str(ROOT / "tools/bnk_patch"))
sys.path.insert(0, str(ROOT / "tools/loudness"))

import numpy as np  # noqa: E402
from jobs import take_problem  # noqa: E402
from stitch import stitch  # noqa: E402
from targets import target_for  # noqa: E402
from wem import linear_gain_db, measure_levels  # noqa: E402

BAD_FLAGS = {"asr_bad", "asr_truncated", "asr_extra_words"}
# runs whose takes were already retried once: a plain "asr_bad" (usually Whisper mishearing a proper name) is accepted there,
# truncated / extra-words takes never are. Set LENIENT_RUNS="night-redo" (space separated) to enable.
LENIENT_RUNS = set(os.environ.get("LENIENT_RUNS", "").split())


def usable_segments(render_root: Path, runs: list[str]) -> dict[str, tuple[Path, dict]]:
    """guid~k -> (wav path, manifest row) for finished, clean segment takes."""
    found: dict[str, tuple[Path, dict]] = {}
    for run in runs:
        mpath = render_root / run / "manifest.jsonl"
        if not mpath.exists():
            continue
        asr = {}
        apath = render_root / run / "asr.jsonl"
        if apath.exists():
            asr = {r["guid"]: r for r in map(json.loads, apath.read_text(encoding="utf-8").splitlines())}
        for line in mpath.read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            wav = render_root / run / "wav" / f"{r['guid']}.wav"
            if r["status"] != "ok" or not wav.is_file() or take_problem(r.get("text", ""), r.get("seconds", 0)):
                continue
            bad = BAD_FLAGS - ({"asr_bad"} if run in LENIENT_RUNS else set())
            if bad & set(asr.get(r["guid"], {}).get("flags", [])):
                continue
            found.setdefault(r["guid"], (wav, r))
    return found


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--runs", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    render_root = ROOT / "data/render"
    by_parent: dict[str, list[dict]] = defaultdict(list)
    for line in Path(a.jobs).read_text(encoding="utf-8").splitlines():
        j = json.loads(line)
        by_parent[j["parent"]].append(j)
    segs = usable_segments(render_root, a.runs)
    out = render_root / a.out
    (out / "wav").mkdir(parents=True, exist_ok=True)
    mpath = out / "manifest.jsonl"
    done = {json.loads(l)["guid"] for l in mpath.read_text(encoding="utf-8").splitlines()} if mpath.exists() else set()
    stitched, waiting = 0, []
    with open(mpath, "a", encoding="utf-8") as mf:
        for parent, jobs in by_parent.items():
            if parent in done:
                continue
            jobs.sort(key=lambda j: j["seg_index"])
            if any(j["guid"] not in segs for j in jobs):
                waiting.append(parent)
                continue
            pieces, sr = [], 24000
            for j in jobs:
                path = segs[j["guid"]][0]
                wav, sr = sf.read(str(path), dtype="float32")
                # each segment goes to its own voice's loudness target (narration -> narrator, speech -> the speaker) and
                # is left there: the stitched take is marked loudness "preset" so patch.py only guards its peak
                lufs, peak = measure_levels(str(path))
                gain = linear_gain_db(lufs, peak, target_for(j["speaker"]))
                pieces.append((wav * 10 ** (gain / 20)).astype(np.float32))
            audio = stitch(pieces, sr, match_levels=False)
            sf.write(str(out / "wav" / f"{parent}.wav"), audio, sr)
            mf.write(json.dumps({"guid": parent, "speaker": next(j["speaker"] for j in jobs if j["seg_kind"] == "speech"),
                                 "engine": "voxcpm2", "text": " ".join(j["text"] for j in jobs), "src_text": jobs[0]["src_text"],
                                 "voice_source": "mixed", "loudness": "preset", "status": "ok", "seconds": round(len(audio) / sr, 2), "flags": [],
                                 "segments": [j["guid"] for j in jobs]}, ensure_ascii=False) + "\n")
            stitched += 1
    print(f"stitched {stitched} cues into {out}; {len(waiting)} cues still waiting on a clean segment")


if __name__ == "__main__":
    main()
