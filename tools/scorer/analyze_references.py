#!/usr/bin/env python3
"""Which reference clips clone well? Aggregates the scored takes per reference clip.

For each reference event: how many lines/takes used it, gate failure rate (bad transcript,
clipping, long trailing silence), mean voice composite, and how far its takes sit from each
line's best take (regret). A reference whose takes fail gates or trail their line's best take
often is a poor anchor.  Usage: python tools/scorer/analyze_references.py [--speaker Abelard] [--min-takes 8]
"""
import argparse
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WER_GATE, MAX_TRAIL = 0.34, 1.5

ap = argparse.ArgumentParser()
ap.add_argument("--speaker", default="Abelard")
ap.add_argument("--min-takes", type=int, default=8)
args = ap.parse_args()
d = ROOT / "data/bon" / args.speaker
manifest = [json.loads(x) for x in (d / "manifest.jsonl").read_text().splitlines() if x.strip()]
scores = {}
for x in (d / "scores.jsonl").read_text().splitlines():
    r = json.loads(x)
    scores[r["key"]] = r["score"]
cal = json.load(open(ROOT / "data/scorer_probe/calibration.json"))
FEATS = list(cal)

rows = []
for m in manifest:
    s = scores.get(f"{m['guid']}#{m['take']}")
    if s:
        v = sum(s[f] / cal[f] for f in FEATS)
        ok = s.get("wer", 0) <= WER_GATE and not s["clipped"] and s["trail_silence"] <= MAX_TRAIL
        rows.append((m["guid"], m["reference"]["event"], m["reference"]["emotion"], v, ok))
print(f"{len(rows)} scored takes over {len({r[0] for r in rows})} lines")

best = defaultdict(lambda: -1e9)
for g, _, _, v, ok in rows:
    if ok:
        best[g] = max(best[g], v)
byref = defaultdict(list)
for g, ev, em, v, ok in rows:
    byref[ev].append((g, em, v, ok))
out = []
for ev, rs in byref.items():
    if len(rs) < args.min_takes:
        continue
    fail = 1 - np.mean([ok for *_, ok in rs])
    reg = np.mean([best[g] - v for g, _, v, ok in rs if ok and best[g] > -1e8])
    out.append((reg, ev, rs[0][1], len({g for g, *_ in rs}), len(rs), fail, np.mean([v for *_, v, _ in rs])))
out.sort()
print(f"\n{'reference event':52s} {'emo':12s} lines takes fail%  voice  regret(lower=better)")
for reg, ev, em, nl, nt, fail, mv in out:
    print(f"{ev[:52]:52s} {str(em)[:12]:12s} {nl:5d} {nt:5d} {fail:5.0%} {mv:6.1f} {reg:6.2f}")
