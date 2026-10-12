#!/usr/bin/env python3
"""Merge the Claude review (data/npc_profile/review/claude_all.json) into one per-line corrections file.

  python3 tools/npc_profile/merge_review.py [--out data/npc_profile/human_labels.json]

Output: {"conversations": {name: {"roster": [...], "lines": {text_key: {speaker, mixed, confidence, delivery, why}},
"status": "reviewed"|"pending", "question": str}}, "resolved": {...}}. Conversations whose question the user has answered
(RESOLVED below) become "reviewed". The 35B output is never modified; nothing reads this file yet.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from review_dump import load_targets  # noqa: E402
from roster import conversation_lines  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
# Answers the user has given, or facts settled from the wiki / game data (2026-10-11).
RESOLVED = {
    "NewBlueprintDialog": {"jae": {"gender": "female", "known_as": "Jae"}, "note": "user: Jae is a woman and a voiced companion"},
    "AfterlightSecond_SororitasQ2_dialog": {"afterlight": {"gender": "male"}, "note": "Fextralife 'Driven': 'kill him three times'"},
    "OfficersMeeting_dialogue": {"toliman": {"gender": "female", "known_as": "Vox Master Vigdis"}, "note": "Fextralife: Vigdis of the Toliman Dynasty"},
}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "data/npc_profile/human_labels.json"))
    a = ap.parse_args()
    review = json.loads((ROOT / "data/npc_profile/review/claude_all.json").read_text(encoding="utf-8"))
    convs = {c["name"].strip(): c for c in json.loads((ROOT / "data/conversations.enGB.json").read_text(encoding="utf-8"))}
    targets = load_targets()
    out = {}
    for r in review:
        name = r["conversation"]
        lines = {l["n"]: l for l in conversation_lines(convs[name], targets)}
        keyed = {}
        for l in r["lines"]:
            src = lines.get(l["n"])
            if src and src["key"]:
                keyed[src["key"]] = {k: l.get(k) for k in ("speaker", "mixed", "confidence", "delivery", "why")}
        pending = r["needs_human"] and name not in RESOLVED
        out[name] = {"roster": r["roster"], "lines": keyed, "status": "pending" if pending else "reviewed",
                     "question": r["question"] if pending else "", "changes_vs_model": r.get("changes_vs_model", "")}
    Path(a.out).write_text(json.dumps({"conversations": out, "resolved": RESOLVED}, indent=1, ensure_ascii=False), encoding="utf-8")
    pend = [n for n, v in out.items() if v["status"] == "pending"]
    print(f"{len(out)} conversations, {sum(len(v['lines']) for v in out.values())} keyed lines, {len(pend)} pending")


if __name__ == "__main__":
    main()
