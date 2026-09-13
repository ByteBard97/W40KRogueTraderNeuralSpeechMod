#!/usr/bin/env python3
"""Diffs a re-annotation pilot cache against the shipped annotations.enGB.json, for human
review before deciding whether to --merge it in. Does NOT touch production data.

Usage: diff_cache_vs_production.py <cache_dir> [--out data/annotations/<name>_review.md]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

sys.path.insert(0, str(Path(__file__).parent))
from annotate import merge_cache_dirs  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cache_dir", nargs="+",
                    help="one or more cache directories, later ones taking precedence on "
                         "a guid conflict - same semantics as annotate.py --merge")
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    production = json.loads((ROOT / "data/annotations/annotations.enGB.json").read_text(encoding="utf-8"))
    pilot, _ = merge_cache_dirs([Path(d) for d in args.cache_dir])

    common = [g for g in pilot if g in production]
    new_only = [g for g in pilot if g not in production]
    changed = [g for g in common if production[g]["emotion"] != pilot[g]["emotion"]]
    unchanged = [g for g in common if production[g]["emotion"] == pilot[g]["emotion"]]

    lines = [f"# Pilot review: {'+'.join(Path(d).name for d in args.cache_dir)}", "",
             f"{len(pilot)} lines in pilot cache. {len(common)} also exist in the shipped "
             f"annotations.enGB.json ({len(new_only)} not found there - new guids or a "
             f"different input snapshot). Of the {len(common)} comparable lines, "
             f"{len(changed)} got a different emotion label, {len(unchanged)} matched.",
             "", "## Changed emotion", "",
             "| guid | old emotion (intensity) | new emotion (intensity) | old instruct | new instruct |",
             "|---|---|---|---|---|"]
    for g in sorted(changed, key=lambda g: pilot[g]["emotion"]):
        old, new = production[g], pilot[g]
        lines.append(f"| {g} | {old['emotion']} ({old['intensity']}) | {new['emotion']} ({new['intensity']}) | "
                      f"{old['instruct']} | {new['instruct']} |")

    if new_only:
        lines += ["", "## In pilot but not in shipped annotations.enGB.json", "",
                  "| guid | emotion (intensity) | instruct |", "|---|---|---|"]
        for g in sorted(new_only):
            new = pilot[g]
            lines.append(f"| {g} | {new['emotion']} ({new['intensity']}) | {new['instruct']} |")

    out = Path(args.out) if args.out else ROOT / f"data/annotations/{'_'.join(Path(d).name for d in args.cache_dir)}_review.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"{len(changed)}/{len(common)} comparable lines changed emotion; wrote {out}")


if __name__ == "__main__":
    main()
