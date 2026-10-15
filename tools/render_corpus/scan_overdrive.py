#!/usr/bin/env python3
"""Find overdriven or clipped takes in an export directory (what the bank is built from) and write a report.

  python3 tools/render_corpus/scan_overdrive.py [--export export_all_r2] [--out data/render/audit/overdrive_scan.json] [--jobs 8]

Uses the same measures as the render lab and the recipe renderer (recipe_audio.metrics: crest factor of the speech frames under 11 dB =
overdriven, runs of clipped samples = clipped). Read only. Output: one row per flagged clip with speaker, source, seconds and crest, plus totals
by speaker so a re-render can be planned.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "tools/render_corpus"))
import recipe_audio as A  # noqa: E402


def scan_one(path: str) -> dict | None:
    try:
        x, sr = sf.read(path, dtype="float32")
    except Exception:
        return None
    if x.ndim > 1:
        x = x.mean(axis=1)
    m = A.metrics(x, sr)
    return {"seconds": m["seconds"], "crest_db": m["crest_db"], "clip_runs": m["clip_runs"], "flag": m["flag"]}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--export", default="export_all_r2")
    ap.add_argument("--out", default=str(ROOT / "data/render/audit/overdrive_scan.json"))
    ap.add_argument("--jobs", type=int, default=8)
    a = ap.parse_args()
    base = ROOT / "data/render" / a.export
    index = json.loads((base / "index.json").read_text(encoding="utf-8"))
    guids = list(index)
    paths = [str(base / index[g]["wav"]) for g in guids]
    with ProcessPoolExecutor(a.jobs) as ex:
        res = list(ex.map(scan_one, paths, chunksize=64))
    rows, tot = [], Counter()
    by_sp: dict[str, dict] = defaultdict(lambda: {"clips": 0, "flagged": 0, "hours": 0.0, "flagged_hours": 0.0})
    for g, r in zip(guids, res):
        if r is None:
            tot["unreadable"] += 1
            continue
        sp = index[g].get("speaker") or "?"
        s = by_sp[sp]
        s["clips"] += 1
        s["hours"] += r["seconds"] / 3600
        tot["clips"] += 1
        if r["flag"]:
            s["flagged"] += 1
            s["flagged_hours"] += r["seconds"] / 3600
            tot[r["flag"]] += 1
            rows.append({"guid": g, "speaker": sp, "source": index[g].get("voice_source"), "engine": index[g].get("engine"), **r})
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a.out).write_text(json.dumps({"export": a.export, "totals": dict(tot), "by_speaker": by_sp, "flagged": rows}, indent=1), encoding="utf-8")
    fh = sum(r["seconds"] for r in rows) / 3600
    print(f"{tot['clips']} clips scanned: {len(rows)} flagged ({tot['overdriven']} overdriven, {tot['clipped']} clipped), {fh:.1f} audio-hours -> {a.out}")
    for sp, s in sorted(by_sp.items(), key=lambda kv: -kv[1]["flagged_hours"])[:12]:
        print(f"  {sp[:34]:34s} {s['flagged']:5d}/{s['clips']:5d} flagged, {s['flagged_hours']:.2f} h of {s['hours']:.2f} h")


if __name__ == "__main__":
    main()
