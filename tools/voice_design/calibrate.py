#!/usr/bin/env python3
"""Measure p_us on real game clips (all British VAs) to set the accent gate.

Samples N clips per speaker from data/voices/catalog.json, scores them, writes
data/voice_design/accent_calibration.json with the distribution and the chosen gate
(max of the 95th percentile of real clips and 0.15, so a clip must look at least as non-American
as nearly all real ones).

Run: tools/scorer/.venv-scorer/bin/python tools/voice_design/calibrate.py [--per-speaker 8]
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(Path(__file__).parent))
from accent import AccentScorer  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per-speaker", type=int, default=8)
    args = ap.parse_args()
    cat = json.loads((ROOT / "data/voices/catalog.json").read_text(encoding="utf-8"))
    by = {}
    for v in cat.values():
        if v["speaker"] != "_unattributed" and v["duration"] >= 4:
            by.setdefault(v["speaker"], []).append(v)
    rng = random.Random(1)
    sc = AccentScorer()
    rows = []
    for spk, clips in sorted(by.items()):
        for v in rng.sample(clips, min(args.per_speaker, len(clips))):
            s = sc.summary(str(ROOT / "data/voices" / v["wav"]))
            rows.append({"speaker": spk, "event": v["event"], **s})
        us = [r["p_us"] for r in rows if r["speaker"] == spk]
        print(f"{spk:28s} n={len(us):2d} mean p_us={sum(us)/len(us):.3f} max={max(us):.3f}", flush=True)
    ps = sorted(r["p_us"] for r in rows)
    p95 = ps[int(0.95 * (len(ps) - 1))]
    gate = max(p95, 0.15)
    out = {"n": len(ps), "p_us_median": ps[len(ps) // 2], "p_us_p95": p95, "gate": gate, "rows": rows}
    (ROOT / "data/voice_design/accent_calibration.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"n={len(ps)} median={out['p_us_median']:.3f} p95={p95:.3f} -> gate p_us <= {gate:.3f}")


if __name__ == "__main__":
    main()
