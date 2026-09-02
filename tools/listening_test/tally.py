#!/usr/bin/env python3
"""Tally votes from the blind listening test (see serve.py). Each vote records the `order` it was
presented in and a best-to-worst `ranking` (or `tie: true`), so no un-blinding step is needed.
Reports the Borda-count standings (same scoring as the live page), per-speaker breakdown, and
error-tag frequency per engine.

Usage: python3 tally.py [votes.json]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_VOTES = ROOT / "data/bakeoff/listening_votes.json"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_VOTES
    if not path.exists():
        raise SystemExit(f"no votes file at {path} yet - run the listening test first")

    votes = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(votes, dict):
        votes = list(votes.values())

    points = Counter()
    firsts = Counter()
    per_speaker_points = defaultdict(Counter)
    errors_by_engine = defaultdict(Counter)
    ties = 0
    n = 0
    for v in votes:
        n += 1
        if v.get("tie"):
            ties += 1
        else:
            ranking = v.get("ranking") or []
            k = len(ranking)
            for idx, engine in enumerate(ranking):
                pts = k - idx
                points[engine] += pts
                per_speaker_points[v["speaker"]][engine] += pts
                if idx == 0:
                    firsts[engine] += 1
        for entry in v.get("clip_errors", []):
            for tag in entry.get("tags", []):
                errors_by_engine[entry["engine"]][tag] += 1

    print(f"{n} votes total ({ties} ties)\n")
    print("Overall standings (Borda points, rank 1 of k scores k):")
    for engine, pts in points.most_common():
        print(f"  {engine}: {pts} pts ({firsts[engine]} firsts)")

    print("\nPer speaker (points):")
    for speaker in sorted(per_speaker_points):
        counts = per_speaker_points[speaker]
        parts = ", ".join(f"{e}={c}" for e, c in counts.most_common())
        print(f"  {speaker}: {parts}")

    if errors_by_engine:
        print("\nError tags flagged per engine:")
        for engine in sorted(errors_by_engine):
            counts = errors_by_engine[engine]
            parts = ", ".join(f"{tag}={c}" for tag, c in counts.most_common())
            print(f"  {engine}: {parts}")


if __name__ == "__main__":
    main()
