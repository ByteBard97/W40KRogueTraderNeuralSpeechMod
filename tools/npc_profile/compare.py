#!/usr/bin/env python3
"""Compare two result files (e.g. 35B vs 122B) and list where they disagree.

  python3 tools/npc_profile/compare.py A.jsonl B.jsonl
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

FIELDS = ("gender", "species", "age")


def ident(entry: dict) -> str:
    """Stable identity for a roster entry across runs: known game speaker, else name, else label, else id."""
    return ((entry.get("known_as") or {}).get("speaker") or entry.get("name") or entry.get("label") or entry["id"]).lower()


def diff(a: dict, b: dict) -> list[str]:
    """Disagreements between two results for the same conversation."""
    out = []
    ra = {ident(r): r for r in a["roster"]}
    rb = {ident(r): r for r in b["roster"]}
    for k in sorted(set(ra) ^ set(rb)):
        out.append(f"character {k!r} only in {'A' if k in ra else 'B'}")
    for k in sorted(set(ra) & set(rb)):
        for f in FIELDS:
            x, y = ra[k][f], rb[k][f]
            if x != y and "unknown" not in (x, y):  # one side unsure is not a conflict, a different answer is
                out.append(f"{k}: {f} {x} vs {y}")
        if ra[k]["fx"] != rb[k]["fx"]:
            out.append(f"{k}: fx {ra[k]['fx']} vs {rb[k]['fx']}")
    ida = {r["id"]: ident(r) for r in a["roster"]}
    idb = {r["id"]: ident(r) for r in b["roster"]}
    la = {l["key"]: ida.get(l["speaker"], l["speaker"]) for l in a["lines"]}
    lb = {l["key"]: idb.get(l["speaker"], l["speaker"]) for l in b["lines"]}
    n = 0
    for key in sorted(set(la) & set(lb)):
        if la[key] != lb[key]:
            n += 1
    if n:
        out.append(f"{n} line(s) assigned to different speakers")
    return out


def compare(rows_a: list[dict], rows_b: list[dict]) -> dict[str, list[str]]:
    b = {r["conversation"]: r for r in rows_b}
    res = {}
    for r in rows_a:
        if r["conversation"] in b:
            d = diff(r, b[r["conversation"]])
            if d:
                res[r["conversation"]] = d
    return res


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    load = lambda p: [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines()]
    a, b = load(sys.argv[1]), load(sys.argv[2])
    res = compare(a, b)
    both = len({r["conversation"] for r in a} & {r["conversation"] for r in b})
    for name, d in res.items():
        print(name)
        for x in d:
            print("   ", x)
    print(f"# {len(res)} of {both} shared conversations disagree", file=sys.stderr)


if __name__ == "__main__":
    main()
