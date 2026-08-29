#!/usr/bin/env python3
"""Compare a model's annotation cache against the hand-checked gold set.

Usage: compare_to_gold.py <cache_dir> [--label NAME]

Metrics: emotion exact-match rate, intensity mean-abs-error, pace exact-match,
nonverbal set F1, and a few side-by-side examples of the biggest disagreements.
Appends a row to data/annotations/gold_comparison.md so multiple models/tiers
can be tracked over time.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent


def load_cache(cache_dir: Path) -> dict:
    merged = {}
    for f in cache_dir.glob("*.json"):
        for r in json.load(open(f, encoding="utf-8"))["lines"]:
            merged[r["guid"]] = r
    return merged


def set_f1(a: set, b: set) -> float:
    if not a and not b:
        return 1.0
    if not a or not b:
        return 0.0
    tp = len(a & b)
    p = tp / len(b) if b else 0
    r = tp / len(a) if a else 0
    return 0.0 if (p + r) == 0 else 2 * p * r / (p + r)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir")
    ap.add_argument("--label", default=None)
    args = ap.parse_args()

    gold = json.load(open(ROOT / "data/annotations/gold.json", encoding="utf-8"))
    pred = load_cache(Path(args.cache_dir))
    label = args.label or Path(args.cache_dir).name

    common = [g for g in gold if g in pred]
    missing = [g for g in gold if g not in pred]
    print(f"{label}: {len(common)}/{len(gold)} lines present ({len(missing)} missing)")

    emo_match = sum(1 for g in common if gold[g]["emotion"] == pred[g]["emotion"])
    pace_match = sum(1 for g in common if gold[g]["pace"] == pred[g]["pace"])
    intens_mae = sum(abs(gold[g]["intensity"] - pred[g]["intensity"]) for g in common) / max(1, len(common))
    nv_f1 = sum(set_f1(set(gold[g]["nonverbal"]), set(pred[g].get("nonverbal", []))) for g in common) / max(1, len(common))

    n = len(common) or 1
    stats = {
        "label": label, "n": len(common), "missing": len(missing),
        "emotion_match": round(emo_match / n, 3),
        "pace_match": round(pace_match / n, 3),
        "intensity_mae": round(intens_mae, 3),
        "nonverbal_f1": round(nv_f1, 3),
    }
    print(json.dumps(stats, indent=2))

    disagree = sorted(common, key=lambda g: abs(gold[g]["intensity"] - pred[g]["intensity"]), reverse=True)
    print("\nBiggest disagreements:")
    for g in disagree[:5]:
        print(f"  {g}: gold={gold[g]['emotion']}/{gold[g]['intensity']}  pred={pred[g]['emotion']}/{pred[g]['intensity']}")

    md = ROOT / "data/annotations/gold_comparison.md"
    header = "| label | n | missing | emotion_match | pace_match | intensity_mae | nonverbal_f1 |\n|---|---|---|---|---|---|---|\n"
    row = f"| {stats['label']} | {stats['n']} | {stats['missing']} | {stats['emotion_match']} | {stats['pace_match']} | {stats['intensity_mae']} | {stats['nonverbal_f1']} |\n"
    if not md.exists():
        md.write_text(header, encoding="utf-8")
    with open(md, "a", encoding="utf-8") as f:
        f.write(row)
    print(f"\nappended to {md}")


if __name__ == "__main__":
    main()
