#!/usr/bin/env python3
"""Paired comparison of generation settings using scored takes (same lines, different out-names).

  python tools/scorer/compare_settings.py Abelard Abelard_cfg4.0 [Abelard_cfg3.5 ...]
The first name is the baseline. Only lines present (with gate-passing takes) in every set are used.
Reports per set: gate pass rate, mean voice composite over passing takes, mean of each line's best
take, and the paired difference vs baseline with a bootstrap 95% CI over lines.
"""
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
WER_GATE, MAX_TRAIL = 0.34, 1.5
cal = json.load(open(ROOT / "data/scorer_probe/calibration.json"))


def load(name):
    d = ROOT / "data/bon" / name
    man = [json.loads(x) for x in (d / "manifest.jsonl").read_text().splitlines() if x.strip()]
    sc = {}
    for x in (d / "scores.jsonl").read_text().splitlines():
        r = json.loads(x)
        sc[r["key"]] = r["score"]
    lines, n_all, n_ok = {}, 0, 0
    for m in man:
        s = sc.get(f"{m['guid']}#{m['take']}")
        if not s:
            continue
        n_all += 1
        ok = s.get("wer", 0) <= WER_GATE and not s["clipped"] and s["trail_silence"] <= MAX_TRAIL
        n_ok += ok
        if ok:
            lines.setdefault(m["guid"], []).append(sum(s[f] / cal[f] for f in cal))
    return lines, n_ok / max(n_all, 1)


sets = {n: load(n) for n in sys.argv[1:]}
common = set.intersection(*[set(v[0]) for v in sets.values()])
print(f"{len(common)} lines in common")
base = sys.argv[1]
rng = np.random.default_rng(0)
for n, (lines, pr) in sets.items():
    mean_all = np.mean([np.mean(lines[g]) for g in common])
    best = np.mean([max(lines[g]) for g in common])
    line = f"{n:28s} gate-pass {pr:5.1%}  mean voice {mean_all:6.2f}  mean best-take {best:6.2f}"
    if n != base:
        d = np.array([np.mean(lines[g]) - np.mean(sets[base][0][g]) for g in sorted(common)])
        bs = [rng.choice(d, len(d)).mean() for _ in range(2000)]
        line += f"  paired diff vs {base}: {d.mean():+.2f} [{np.percentile(bs, 2.5):+.2f}, {np.percentile(bs, 97.5):+.2f}]"
    print(line)
