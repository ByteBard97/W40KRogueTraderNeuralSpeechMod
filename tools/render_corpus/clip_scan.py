#!/usr/bin/env python3
"""Clipping scan of rendered wavs: peak, samples at full scale, runs of clipped samples, and a rough flat-top count.

  python3 tools/render_corpus/clip_scan.py data/render/cast-stitched/wav [more dirs ...] [--limit N] [--csv out.csv]

Hard clipping shows up as runs of 3+ samples sitting at the file's own ceiling when that ceiling is near full scale. Only meaningful on
raw renders (data/render/<run>/wav): the stitcher and patch.py scale clips down, which hides the ceiling. Prints a summary per directory.
"""
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import numpy as np
import soundfile as sf

FULL = 0.999          # linear: counts as full scale
RUN = 3               # consecutive samples at the ceiling that count as a clipped run


def scan(path: Path) -> dict:
    x, sr = sf.read(str(path), dtype="float32")
    if x.ndim > 1:
        x = x.mean(axis=1)
    a = np.abs(x)
    pk = float(a.max()) if len(a) else 0.0
    hot = a >= min(FULL, pk * 0.999)                 # at (or within 0.01 % of) the file's own ceiling
    n_hot = int(hot.sum()) if pk >= 0.5 else 0
    runs = 0
    if n_hot:
        h = np.concatenate(([0], hot.astype(np.int8), [0]))
        d = np.diff(h)
        starts, ends = np.where(d == 1)[0], np.where(d == -1)[0]
        runs = int(((ends - starts) >= RUN).sum())
    return {"file": path.name, "sec": round(len(x) / sr, 2), "peak_db": round(20 * np.log10(max(pk, 1e-9)), 2), "at_ceiling": n_hot, "runs": runs,
            "frac_ppm": round(1e6 * n_hot / max(len(x), 1), 1)}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--csv")
    a = ap.parse_args()
    rows = []
    for d in a.dirs:
        files = sorted(Path(d).glob("*.wav"))
        if a.limit:
            files = files[:: max(1, len(files) // a.limit)][: a.limit]
        res = [scan(f) for f in files]
        for r in res:
            r["dir"] = d
        rows += res
        pk = np.array([r["peak_db"] for r in res])
        print(f"{d}: {len(res)} files | peak median {np.median(pk):.1f} dB, p95 {np.percentile(pk, 95):.1f}, max {pk.max():.1f} | "
              f"files with a clipped run: {sum(r['runs'] > 0 for r in res)} ({100 * sum(r['runs'] > 0 for r in res) / len(res):.1f}%) | "
              f"peak above -0.5 dB: {int((pk > -0.5).sum())}")
    if a.csv:
        with open(a.csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0]))
            w.writeheader()
            w.writerows(rows)


if __name__ == "__main__":
    main()
