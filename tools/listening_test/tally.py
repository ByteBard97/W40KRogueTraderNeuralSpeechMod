#!/usr/bin/env python3
"""Tally votes from the blind listening test (see serve.py). Un-blinds each vote (the vote log
already records which engine was A/B) and reports win/tie counts overall and per speaker.

Usage: python3 tally.py [votes.jsonl]
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_VOTES = ROOT / "data/bakeoff/listening_votes.jsonl"


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_VOTES
    if not path.exists():
        raise SystemExit(f"no votes file at {path} yet - run the listening test first")

    overall = Counter()
    per_speaker = defaultdict(Counter)
    n = 0
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        v = json.loads(line)
        n += 1
        if v["choice"] == "tie":
            overall["tie"] += 1
            per_speaker[v["speaker"]]["tie"] += 1
            continue
        winner = v["a_engine"] if v["choice"] == "a" else v["b_engine"]
        overall[winner] += 1
        per_speaker[v["speaker"]][winner] += 1

    print(f"{n} votes total\n")
    print("Overall:")
    for engine, count in overall.most_common():
        print(f"  {engine}: {count} ({count / n:.0%})")

    print("\nPer speaker:")
    for speaker in sorted(per_speaker):
        counts = per_speaker[speaker]
        total = sum(counts.values())
        parts = ", ".join(f"{e}={c}" for e, c in counts.most_common())
        print(f"  {speaker} (n={total}): {parts}")


if __name__ == "__main__":
    main()
